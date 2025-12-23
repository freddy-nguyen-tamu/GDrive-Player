from flask import Flask, render_template, jsonify, request, send_file, Response
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os
import pickle
import re
import requests
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    """Get authenticated Google Drive service."""
    creds = None
    
    # Token file stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                return None, "Missing credentials.json file. Please follow setup instructions."
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    service = build('drive', 'v3', credentials=creds)
    return service, None

def extract_folder_id(url):
    """Extract folder ID from Google Drive URL."""
    patterns = [
        r'folders/([a-zA-Z0-9-_]+)',
        r'id=([a-zA-Z0-9-_]+)',
        r'open\?id=([a-zA-Z0-9-_]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # If no pattern matches, assume the input is already a folder ID
    return url.strip()

def get_folder_contents(service, folder_id):
    """Get all files and folders in a Google Drive folder."""
    try:
        # Query for all items in the folder
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, size, videoMediaMetadata, thumbnailLink)",
            orderBy="folder,name"
        ).execute()
        
        items = results.get('files', [])
        
        folders = []
        videos = []
        
        for item in items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                folders.append({
                    'id': item['id'],
                    'name': item['name'],
                    'type': 'folder'
                })
            elif item['mimeType'].startswith('video/'):
                video_info = {
                    'id': item['id'],
                    'name': item['name'],
                    'type': 'video',
                    'size': item.get('size', 'Unknown'),
                    'thumbnail': item.get('thumbnailLink', '')
                }
                
                if 'videoMediaMetadata' in item:
                    video_info['duration'] = item['videoMediaMetadata'].get('durationMillis', 0)
                    video_info['width'] = item['videoMediaMetadata'].get('width', 0)
                    video_info['height'] = item['videoMediaMetadata'].get('height', 0)
                
                videos.append(video_info)
        
        return {'folders': folders, 'videos': videos}, None
    except Exception as e:
        return None, str(e)

def get_folder_path(service, folder_id):
    """Get the full path of breadcrumbs for a folder."""
    path = []
    current_id = folder_id
    
    try:
        while current_id:
            file = service.files().get(fileId=current_id, fields="id, name, parents").execute()
            path.insert(0, {'id': file['id'], 'name': file['name']})
            
            parents = file.get('parents', [])
            current_id = parents[0] if parents else None
            
            # Limit depth to prevent infinite loops
            if len(path) > 20:
                break
        
        return path, None
    except Exception as e:
        return None, str(e)

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')

@app.route('/api/parse-link', methods=['POST'])
def parse_link():
    """Extract folder ID from Google Drive link."""
    data = request.get_json()
    url = data.get('url', '')
    
    folder_id = extract_folder_id(url)
    if folder_id:
        return jsonify({'success': True, 'folder_id': folder_id})
    else:
        return jsonify({'success': False, 'error': 'Invalid Google Drive URL'})

@app.route('/api/folder/<folder_id>')
def get_folder(folder_id):
    """Get contents of a folder."""
    service, error = get_drive_service()
    if error:
        return jsonify({'success': False, 'error': error})
    
    contents, error = get_folder_contents(service, folder_id)
    if error:
        return jsonify({'success': False, 'error': error})
    
    path, _ = get_folder_path(service, folder_id)
    
    return jsonify({
        'success': True,
        'contents': contents,
        'path': path or []
    })

@app.route('/api/video/<file_id>')
def get_video_info(file_id):
    """Get video information."""
    service, error = get_drive_service()
    if error:
        return jsonify({'success': False, 'error': error})
    
    try:
        file = service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, size, videoMediaMetadata"
        ).execute()
        
        return jsonify({'success': True, 'file': file})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stream/<file_id>')
def stream_video(file_id):
    """Stream video file."""
    service, error = get_drive_service()
    if error:
        return jsonify({'success': False, 'error': error}), 500
    
    try:
        # Get file metadata
        file_metadata = service.files().get(fileId=file_id, fields="name, mimeType, size").execute()
        file_size = int(file_metadata.get('size', 0))
        mime_type = file_metadata.get('mimeType', 'video/mp4')
        
        # Handle range requests for seeking
        range_header = request.headers.get('Range')
        
        if range_header:
            # Parse range header
            byte_range = range_header.strip().split('=')[1]
            start, end = byte_range.split('-')
            start = int(start)
            end = int(end) if end else file_size - 1
            length = end - start + 1
            
            # Request partial content
            request_obj = service.files().get_media(fileId=file_id)
            request_obj.headers['Range'] = f'bytes={start}-{end}'
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request_obj)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            fh.seek(0)
            data = fh.read()
            
            response = Response(data, 206, mimetype=mime_type)
            response.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
            response.headers.add('Accept-Ranges', 'bytes')
            response.headers.add('Content-Length', str(length))
            return response
        else:
            # Full file request
            request_obj = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request_obj)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            fh.seek(0)
            
            response = Response(fh.read(), mimetype=mime_type)
            response.headers.add('Content-Length', str(file_size))
            response.headers.add('Accept-Ranges', 'bytes')
            return response
            
    except Exception as e:
        print(f"Error streaming video: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("Google Drive Video Player")
    print("=" * 60)
    print("\nStarting server on http://localhost:5000")
    print("\nMake sure you have:")
    print("  1. Created a Google Cloud project")
    print("  2. Enabled Google Drive API")
    print("  3. Downloaded credentials.json to this directory")
    print("\nFirst run will open a browser for authentication.")
    print("=" * 60)
    
    app.run(debug=True, port=5000, threaded=True)
