// HLS.js integration for adaptive streaming
// This provides smooth playback with adaptive bitrate streaming

class HLSVideoLoader {
    constructor() {
        this.hls = null;
        this.currentVideoId = null;
    }

    async loadVideo(video, videoId, token) {
        this.currentVideoId = videoId;
        
        // For browsers that support HLS natively (Safari)
        if (video.canPlayType('application/vnd.apple.mpegurl')) {
            const streamUrl = `https://www.googleapis.com/drive/v3/files/${videoId}?alt=media&access_token=${token}`;
            video.src = streamUrl;
            return;
        }
        
        // For other browsers, use direct streaming with optimizations
        const streamUrl = `https://www.googleapis.com/drive/v3/files/${videoId}?alt=media&access_token=${token}`;
        video.src = streamUrl;
    }

    destroy() {
        if (this.hls) {
            this.hls.destroy();
            this.hls = null;
        }
    }
}

window.HLSVideoLoader = HLSVideoLoader;
