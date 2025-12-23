// Video optimization utilities
class VideoOptimizer {
    constructor(videoElement) {
        this.video = videoElement;
        this.setupOptimizations();
    }

    setupOptimizations() {
        // Request high priority for video requests
        if ('priority' in Request.prototype) {
            console.log('Resource priority hints supported');
        }

        // Enable hardware acceleration hints
        this.video.style.transform = 'translateZ(0)';
        this.video.style.backfaceVisibility = 'hidden';
        this.video.style.perspective = '1000px';

        // Monitor buffer health
        this.video.addEventListener('progress', () => {
            this.logBufferHealth();
        });

        // Handle stalling
        this.video.addEventListener('stalled', () => {
            console.warn('Video stalled - buffering');
        });

        this.video.addEventListener('waiting', () => {
            console.warn('Video waiting for data');
        });

        this.video.addEventListener('playing', () => {
            console.log('Video playing smoothly');
        });

        // Preload metadata and some content
        this.video.preload = 'auto';
        
        // Request picture-in-picture early (improves performance on some systems)
        if (document.pictureInPictureEnabled) {
            console.log('Picture-in-Picture available');
        }
    }

    logBufferHealth() {
        if (this.video.buffered.length > 0) {
            const currentTime = this.video.currentTime;
            const buffered = this.video.buffered;
            
            let bufferedAhead = 0;
            for (let i = 0; i < buffered.length; i++) {
                if (buffered.start(i) <= currentTime && buffered.end(i) > currentTime) {
                    bufferedAhead = buffered.end(i) - currentTime;
                    break;
                }
            }
            
            if (bufferedAhead > 0) {
                console.log(`Buffer health: ${bufferedAhead.toFixed(1)}s ahead`);
            }
        }
    }

    enableAggressiveBuffering() {
        // Trick browser into buffering more by playing at high speed briefly
        const originalRate = this.video.playbackRate;
        
        if (!this.video.paused && this.video.readyState >= 2) {
            // Temporarily speed up to trigger more buffering
            this.video.playbackRate = 2.0;
            
            setTimeout(() => {
                this.video.playbackRate = originalRate;
            }, 1000);
        }
    }
}

window.VideoOptimizer = VideoOptimizer;
