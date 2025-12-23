// Service Worker for aggressive video caching and buffering
const CACHE_NAME = 'gdrive-video-cache-v1';
const VIDEO_CACHE_SIZE = 500 * 1024 * 1024; // 500MB cache for video chunks

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // Only handle Google Drive API video requests
    if (url.hostname === 'www.googleapis.com' && url.pathname.includes('/drive/v3/files/') && url.searchParams.get('alt') === 'media') {
        event.respondWith(handleVideoRequest(event.request));
    }
});

async function handleVideoRequest(request) {
    const cache = await caches.open(CACHE_NAME);
    const cachedResponse = await cache.match(request);
    
    // Return cached response if available
    if (cachedResponse) {
        // Fetch in background to update cache
        fetchAndCache(request, cache);
        return cachedResponse;
    }
    
    // Fetch and cache
    return fetchAndCache(request, cache);
}

async function fetchAndCache(request, cache) {
    try {
        const response = await fetch(request);
        
        // Only cache successful responses
        if (response.ok) {
            // Clone the response before caching
            cache.put(request, response.clone());
        }
        
        return response;
    } catch (error) {
        console.error('Fetch failed:', error);
        throw error;
    }
}
