// Enhanced video streaming with better buffering
class VideoStreamLoader {
    constructor(videoElement) {
        this.video = videoElement;
        this.tokenRefreshInterval = 55 * 60 * 1000; // 55 minutes
        this.lastTokenTime = 0;
        this.currentToken = null;
        this.currentVideoId = null;
    }

    async getToken() {
        const now = Date.now();
        if (this.currentToken && (now - this.lastTokenTime) < this.tokenRefreshInterval) {
            return this.currentToken;
        }

        const res = await fetch('/api/token');
        const data = await res.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to get access token');
        }
        
        this.currentToken = data.access_token;
        this.lastTokenTime = now;
        return this.currentToken;
    }

    async loadVideo(videoId) {
        this.currentVideoId = videoId;
        const token = await this.getToken();
        
        // Direct streaming URL with token
        const streamUrl = `https://www.googleapis.com/drive/v3/files/${videoId}?alt=media&access_token=${token}`;
        
        // Clear previous source
        this.video.pause();
        this.video.removeAttribute('src');
        this.video.load();
        
        // Set new source with optimizations
        this.video.preload = 'auto';
        this.video.src = streamUrl;
        
        // Setup token refresh before expiry
        this.setupTokenRefresh();
        
        return streamUrl;
    }

    setupTokenRefresh() {
        // Refresh token before it expires to ensure smooth playback
        setTimeout(async () => {
            if (this.video.src && !this.video.paused) {
                try {
                    const currentTime = this.video.currentTime;
                    const wasPaused = this.video.paused;
                    
                    // Get new token and update source
                    const token = await this.getToken();
                    const newUrl = `https://www.googleapis.com/drive/v3/files/${this.currentVideoId}?alt=media&access_token=${token}`;
                    
                    this.video.src = newUrl;
                    this.video.currentTime = currentTime;
                    
                    if (!wasPaused) {
                        await this.video.play();
                    }
                    
                    // Schedule next refresh
                    this.setupTokenRefresh();
                } catch (error) {
                    console.error('Token refresh failed:', error);
                }
            }
        }, this.tokenRefreshInterval);
    }
}

// Export for use in main script
window.VideoStreamLoader = VideoStreamLoader;
