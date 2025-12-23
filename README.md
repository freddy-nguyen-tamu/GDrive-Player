# Google Drive Video Player

A YouTube-like interface for watching videos from shared Google Drive folders without downloading them.

## Features
- Browse nested folder structures
- Stream videos directly from Google Drive
- Proper video controls (seek, volume, playback speed)
- Responsive design
- No need to clone or download videos
- Works with shared Google Drive links

## Setup

### Prerequisites
- Python 3.8+
- Google Cloud Project with Drive API enabled
- pip (Python package manager)

### Installation

1. **Install dependencies:**
```bash
pip install flask google-api-python-client google-auth-httplib2 google-auth-oauthlib requests flask-cors
```

2. **Set up Google Drive API:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google Drive API
   - Create credentials (OAuth 2.0 Client ID for Desktop application)
   - Download the credentials JSON file and save as `credentials.json` in the project root

3. **Run the application:**
```bash
python app.py
```

4. **Open in browser:**
   - Navigate to `http://localhost:5000`
   - Paste your shared Google Drive folder link
   - Start watching!

## Usage

1. Get a shared Google Drive folder link (make sure it's set to "Anyone with the link can view")
2. Paste the link in the input field on the homepage
3. Browse through folders and click on videos to watch
4. Use standard video controls (play, pause, seek, volume, speed)

## How It Works

- The app extracts the folder ID from the shared link
- Uses Google Drive API to fetch folder contents without requiring ownership
- Streams videos directly using Google Drive's export URLs
- No files are downloaded to your computer

## Notes

- First time you run the app, it will open a browser for Google authentication
- The token is saved locally for future use
- Only works with publicly shared or "anyone with link" folders
- Supports common video formats (mp4, webm, avi, mov, mkv, etc.)
