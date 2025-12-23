# Step-by-Step Setup Guide

## Step 1: Install Python Dependencies

Open a terminal in the `gdrive-video-player` directory and run:

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install flask google-api-python-client google-auth-httplib2 google-auth-oauthlib requests flask-cors
```

## Step 2: Set Up Google Cloud Project

### 2.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" at the top
3. Click "NEW PROJECT"
4. Enter a project name (e.g., "GDrive Video Player")
5. Click "CREATE"

### 2.2 Enable Google Drive API

1. In your project, go to "APIs & Services" > "Library"
2. Search for "Google Drive API"
3. Click on it and click "ENABLE"

### 2.3 Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "CREATE CREDENTIALS" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" user type
   - Fill in app name (e.g., "GDrive Video Player")
   - Add your email as support and developer email
   - Click "SAVE AND CONTINUE" through the steps
   - Add scope: `../auth/drive.readonly`
   - Click "SAVE AND CONTINUE"
   - Add yourself as a test user
   - Click "SAVE AND CONTINUE"

4. Back at Create OAuth client ID:
   - Choose "Desktop app" as application type
   - Give it a name (e.g., "Desktop client")
   - Click "CREATE"

5. Click "DOWNLOAD JSON" button
6. Rename the downloaded file to `credentials.json`
7. Place `credentials.json` in the `gdrive-video-player` directory

## Step 3: Run the Application

```bash
python app.py
```

On first run:
- A browser window will open asking you to sign in to Google
- Select your Google account
- Click "Allow" to grant permissions
- The app will save a `token.pickle` file for future use

## Step 4: Use the App

1. Open your browser to `http://localhost:5000`
2. Get a Google Drive folder link:
   - Go to Google Drive
   - Right-click on a folder with videos
   - Click "Share" > "Get link"
   - Make sure it's set to "Anyone with the link can view"
   - Copy the link

3. Paste the link in the app and click "Load Folder"
4. Browse folders and click videos to watch!

## Troubleshooting

### "Missing credentials.json file"
- Make sure you've downloaded the OAuth credentials and renamed it to `credentials.json`
- Place it in the `gdrive-video-player` directory

### "Access denied" or "Permission denied"
- Make sure the Google Drive folder is shared with "Anyone with the link can view"
- Try re-authenticating by deleting `token.pickle` and running the app again

### Video won't play
- Some video formats may not be supported by your browser
- Try a different browser (Chrome usually has the best codec support)
- Check that the video file isn't corrupted in Google Drive

### API Quota Exceeded
- Google Drive API has usage limits
- Wait a few minutes and try again
- For heavy usage, you may need to request a quota increase in Google Cloud Console

## Keyboard Shortcuts (when video is playing)

- **Space**: Play/Pause
- **Arrow Left**: Rewind 5 seconds
- **Arrow Right**: Forward 5 seconds
- **Arrow Up**: Increase volume
- **Arrow Down**: Decrease volume
- **F**: Fullscreen
- **M**: Mute/Unmute
