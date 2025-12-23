// Aggressive prefetching and caching for smooth playback
class PrefetchOptimizer {
    constructor(videoElement) {
        this.video = videoElement;
        this.prefetchCache = new Map();
    }

    // Prefetch upcoming video segments
    async prefetchAhead(fileId, currentTime, duration) {
        if (!duration || duration === 0) return;
        
        // Calculate which segments to prefetch (next 30 seconds)
        const segmentSize = 5 * 1024 * 1024; // 5MB segments
        const prefetchDuration = 30; // seconds ahead
        
        const bytesPerSecond = this.estimateBitrate();
        const startByte = Math.floor((currentTime + 5) * bytesPerSecond);
        const endByte = Math.floor((currentTime + prefetchDuration) * bytesPerSecond);
        
        // Prefetch in background
        this.prefetchRange(fileId, startByte, endByte);
    }

    estimateBitrate() {
        // Estimate based on typical video bitrates
        return 500 * 1024; // 500 KB/s average
    }

    async prefetchRange(fileId, start, end) {
        const cacheKey = `${fileId}-${start}-${end}`;
        
        if (this.prefetchCache.has(cacheKey)) {
            return this.prefetchCache.get(cacheKey);
        }
        
        try {
            const response = await fetch(`/api/stream/${fileId}`, {
                headers: {
                    'Range': `bytes=${start}-${end}`
                }
            });
            
            if (response.ok) {
                const blob = await response.blob();
                this.prefetchCache.set(cacheKey, blob);
                console.log(`Prefetched: ${start}-${end}`);
            }
        } catch (error) {
            console.error('Prefetch failed:', error);
        }
    }
}

window.PrefetchOptimizer = PrefetchOptimizer;
