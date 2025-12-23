from __future__ import annotations

import os
import pickle
import re
import threading
from typing import Any, Dict, Optional, Tuple

import requests
from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# Increase performance with larger buffer sizes
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 7200  # 2 hours cache

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_FILE = "token.pickle"
CREDS_FILE = "credentials.json"

_auth_lock = threading.Lock()
_cached_service = None
_cached_creds: Optional[Credentials] = None


def _load_creds_from_disk() -> Optional[Credentials]:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            return pickle.load(f)
    return None


def _save_creds_to_disk(creds: Credentials) -> None:
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)


def _ensure_creds() -> Tuple[Optional[Credentials], Optional[str]]:
    global _cached_creds

    with _auth_lock:
        creds = _cached_creds or _load_creds_from_disk()

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(GoogleAuthRequest())
                except Exception:
                    creds = None

            if not creds:
                if not os.path.exists(CREDS_FILE):
                    return None, "Missing credentials.json file. Please follow setup instructions."
                flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)

            _save_creds_to_disk(creds)

        _cached_creds = creds
        return creds, None


def _get_access_token() -> Tuple[Optional[str], Optional[str]]:
    creds, err = _ensure_creds()
    if err:
        return None, err

    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        _save_creds_to_disk(creds)

    return creds.token, None


def get_drive_service() -> Tuple[Optional[Any], Optional[str]]:
    global _cached_service

    creds, err = _ensure_creds()
    if err:
        return None, err

    with _auth_lock:
        if _cached_service is None:
            _cached_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _cached_service, None


def extract_folder_id(url: str) -> str:
    patterns = [
        r"folders/([a-zA-Z0-9-_]+)",
        r"id=([a-zA-Z0-9-_]+)",
        r"open\?id=([a-zA-Z0-9-_]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return url.strip()


def get_folder_contents(service: Any, folder_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        folders = []
        videos = []

        page_token = None
        query = f"'{folder_id}' in parents and trashed=false"
        fields = "nextPageToken, files(id,name,mimeType,size,videoMediaMetadata,thumbnailLink)"

        while True:
            resp = (
                service.files()
                .list(
                    q=query,
                    fields=fields,
                    orderBy="folder,name",
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )

            for item in resp.get("files", []):
                mime = item.get("mimeType", "")
                if mime == "application/vnd.google-apps.folder":
                    folders.append({"id": item["id"], "name": item["name"], "type": "folder"})
                elif mime.startswith("video/"):
                    vm = item.get("videoMediaMetadata") or {}
                    videos.append(
                        {
                            "id": item["id"],
                            "name": item["name"],
                            "type": "video",
                            "size": item.get("size", "Unknown"),
                            "thumbnail": item.get("thumbnailLink", ""),
                            "duration": vm.get("durationMillis", 0),
                            "width": vm.get("width", 0),
                            "height": vm.get("height", 0),
                        }
                    )

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return {"folders": folders, "videos": videos}, None
    except Exception as e:
        return None, str(e)


def get_folder_path(service: Any, folder_id: str) -> Tuple[Optional[list], Optional[str]]:
    path = []
    current_id = folder_id
    try:
        for _ in range(20):
            file = (
                service.files()
                .get(fileId=current_id, fields="id,name,parents", supportsAllDrives=True)
                .execute()
            )
            path.insert(0, {"id": file["id"], "name": file["name"]})
            parents = file.get("parents", [])
            if not parents:
                break
            current_id = parents[0]
        return path, None
    except Exception as e:
        return None, str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/parse-link", methods=["POST"])
def parse_link():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    folder_id = extract_folder_id(url)
    if folder_id:
        return jsonify({"success": True, "folder_id": folder_id})
    return jsonify({"success": False, "error": "Invalid Google Drive URL"})


@app.route("/api/folder/<folder_id>")
def get_folder(folder_id: str):
    service, error = get_drive_service()
    if error:
        return jsonify({"success": False, "error": error})

    contents, error = get_folder_contents(service, folder_id)
    if error:
        return jsonify({"success": False, "error": error})

    path, _ = get_folder_path(service, folder_id)
    return jsonify({"success": True, "contents": contents, "path": path or []})


@app.route("/api/stream/<file_id>")
def stream_video(file_id: str):
    token, err = _get_access_token()
    if err:
        return jsonify({"success": False, "error": err}), 500

    # Get metadata (size + mime type) for correct headers and range handling
    service, error = get_drive_service()
    if error:
        return jsonify({"success": False, "error": error}), 500

    try:
        meta = (
            service.files()
            .get(fileId=file_id, fields="size,mimeType", supportsAllDrives=True)
            .execute()
        )
        file_size = int(meta.get("size", 0))
        mime_type = meta.get("mimeType", "video/mp4")
    except Exception:
        file_size = 0
        mime_type = "video/mp4"

    headers = {"Authorization": f"Bearer {token}"}

    range_header = request.headers.get("Range")
    if range_header:
        headers["Range"] = range_header
    else:
        # For non-range requests, request a large initial chunk for faster start
        # Request first 10MB to enable quick playback start
        if file_size > 0:
            headers["Range"] = f"bytes=0-{min(10 * 1024 * 1024, file_size - 1)}"

    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

    # Increase timeout and disable verify for faster connection
    upstream = requests.get(url, headers=headers, stream=True, timeout=30)

    # If token was stale, refresh once and retry
    if upstream.status_code == 401:
        upstream.close()
        token, err = _get_access_token()
        if err:
            return jsonify({"success": False, "error": err}), 500
        headers["Authorization"] = f"Bearer {token}"
        upstream = requests.get(url, headers=headers, stream=True, timeout=30)

    if upstream.status_code not in (200, 206):
        # Return upstream error body for debugging (short)
        text = ""
        try:
            text = upstream.text[:500]
        except Exception:
            pass
        upstream.close()
        return jsonify(
            {"success": False, "error": f"Upstream error {upstream.status_code}", "details": text}
        ), 500

    def generate():
        try:
            # Use 4MB chunks for even better buffering and fewer requests
            for chunk in upstream.iter_content(chunk_size=1024 * 1024 * 4):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    resp_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=7200",  # Cache for 2 hours
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
    }

    # Prefer upstream headers if present
    for h in ["Content-Length", "Content-Range", "Accept-Ranges"]:
        if h in upstream.headers:
            resp_headers[h] = upstream.headers[h]

    # If upstream didn't give length, but we know size and it's a full response
    if "Content-Length" not in resp_headers and file_size and upstream.status_code == 200:
        resp_headers["Content-Length"] = str(file_size)

    return Response(generate(), status=upstream.status_code, mimetype=mime_type, headers=resp_headers)


@app.route("/api/token")
def token():
    creds, err = _ensure_creds()
    if err:
        return jsonify({"success": False, "error": err}), 500

    # Refresh if needed
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        _save_creds_to_disk(creds)

    return jsonify({"success": True, "access_token": creds.token})


@app.route("/api/thumbnail/<file_id>")
def get_thumbnail(file_id: str):
    """Proxy thumbnail requests to avoid CORS issues"""
    token, err = _get_access_token()
    if err:
        return "", 404

    # Get thumbnail link from Drive API
    service, error = get_drive_service()
    if error:
        return "", 404

    try:
        meta = service.files().get(fileId=file_id, fields="thumbnailLink", supportsAllDrives=True).execute()
        thumbnail_url = meta.get("thumbnailLink", "")
        
        if not thumbnail_url:
            return "", 404
        
        # Fetch and proxy the thumbnail with retry logic
        headers = {"Authorization": f"Bearer {token}"}
        
        for attempt in range(2):
            try:
                resp = requests.get(thumbnail_url, headers=headers, timeout=10)
                
                if resp.status_code == 401 and attempt == 0:
                    # Token expired, refresh and retry
                    token, err = _get_access_token()
                    if err:
                        return "", 404
                    headers["Authorization"] = f"Bearer {token}"
                    continue
                
                if resp.status_code == 200:
                    from flask import Response
                    # Detect actual content type
                    content_type = resp.headers.get('Content-Type', 'image/jpeg')
                    return Response(resp.content, mimetype=content_type, headers={
                        "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                        "Access-Control-Allow-Origin": "*"
                    })
                break
            except requests.exceptions.Timeout:
                if attempt == 1:
                    return "", 404
    except Exception as e:
        print(f"Thumbnail error for {file_id}: {e}")
    
    return "", 404

@app.route("/static/<path:path>")
def send_static(path):
    from flask import send_from_directory
    return send_from_directory("static", path)


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
