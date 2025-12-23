from __future__ import annotations

import io
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

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

TOKEN_FILE = "token.pickle"
CREDS_FILE = "credentials.json"

# Keep a cached Drive service/credentials so you don't re-auth and rebuild on every request
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


def get_drive_service() -> Tuple[Optional[Any], Optional[str]]:
    """
    Returns (service, error). service is googleapiclient.discovery.Resource.
    Caches credentials/service for speed.
    """
    global _cached_service, _cached_creds

    with _auth_lock:
        # Fast path: cached and valid
        if _cached_service is not None and _cached_creds is not None and _cached_creds.valid:
            return _cached_service, None

        creds = _cached_creds or _load_creds_from_disk()

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(GoogleAuthRequest())
                except Exception as e:
                    # If refresh fails, force a new login flow
                    creds = None
            if not creds:
                if not os.path.exists(CREDS_FILE):
                    return None, "Missing credentials.json file. Please follow setup instructions."
                flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
                # run_local_server uses an ephemeral localhost port; Desktop OAuth client is required.
                creds = flow.run_local_server(port=0)

            _save_creds_to_disk(creds)

        # Build and cache the Drive service
        _cached_creds = creds
        _cached_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _cached_service, None


def _get_access_token() -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (token, error). Refreshes token if needed.
    """
    global _cached_creds

    with _auth_lock:
        if _cached_creds is None:
            _cached_creds = _load_creds_from_disk()

        if _cached_creds is None:
            return None, "Not authenticated yet. Visit /api/folder/<id> once to trigger authentication."

        if not _cached_creds.valid:
            if _cached_creds.expired and _cached_creds.refresh_token:
                try:
                    _cached_creds.refresh(GoogleAuthRequest())
                    _save_creds_to_disk(_cached_creds)
                except Exception as e:
                    return None, f"Token refresh failed: {e}"
            else:
                return None, "No valid credentials. Re-authentication required."

        return _cached_creds.token, None


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
    """
    Paginates results and returns folders/videos separately.
    """
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
            file = service.files().get(fileId=current_id, fields="id,name,parents").execute()
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


@app.route("/api/video/<file_id>")
def get_video_info(file_id: str):
    service, error = get_drive_service()
    if error:
        return jsonify({"success": False, "error": error})

    try:
        file = (
            service.files()
            .get(fileId=file_id, fields="id,name,mimeType,size,videoMediaMetadata")
            .execute()
        )
        return jsonify({"success": True, "file": file})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/stream/<file_id>")
def stream_video(file_id: str):
    """
    Faster/smoother streaming:
    - Proxy the Drive download endpoint with requests(stream=True)
    - Supports Range requests for seeking without buffering the whole file in memory
    """
    # Ensure we have a valid access token (this also refreshes if needed)
    token, tok_err = _get_access_token()
    if tok_err:
        # Try to trigger auth if not done yet
        service, err = get_drive_service()
        if err:
            return jsonify({"success": False, "error": err}), 500
        token, tok_err = _get_access_token()
        if tok_err:
            return jsonify({"success": False, "error": tok_err}), 500

    service, error = get_drive_service()
    if error:
        return jsonify({"success": False, "error": error}), 500

    try:
        meta = service.files().get(fileId=file_id, fields="name,mimeType,size").execute()
        mime_type = meta.get("mimeType", "video/mp4")

        headers = {"Authorization": f"Bearer {token}"}
        range_header = request.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        # Drive v3 media download endpoint
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        upstream = requests.get(url, headers=headers, stream=True, timeout=60)

        # If token expired mid-flight, try one refresh and retry once
        if upstream.status_code == 401:
            with _auth_lock:
                if _cached_creds and _cached_creds.refresh_token:
                    _cached_creds.refresh(GoogleAuthRequest())
                    _save_creds_to_disk(_cached_creds)
                    headers["Authorization"] = f"Bearer {_cached_creds.token}"
            upstream.close()
            upstream = requests.get(url, headers=headers, stream=True, timeout=60)

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        # Pass through key headers for video players
        resp_headers = {}
        for h in ["Content-Length", "Content-Range", "Accept-Ranges"]:
            if h in upstream.headers:
                resp_headers[h] = upstream.headers[h]

        status_code = upstream.status_code
        return Response(generate(), status=status_code, mimetype=mime_type, headers=resp_headers)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 60)
    print("Google Drive Video Player")
    print("=" * 60)
    print("Starting server on http://localhost:5000")
    print("Make sure you have:")
    print("  1. Created a Google Cloud project")
    print("  2. Enabled Google Drive API")
    print("  3. Downloaded credentials.json to this directory")
    print("First run will open a browser for authentication.")
    print("=" * 60)

    app.run(debug=True, port=5000, threaded=True)
