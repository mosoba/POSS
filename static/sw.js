// ============================================================
// SERVICE WORKER - PricePoint POS (OFFLINE-FIRST)
// ============================================================

const CACHE_NAME = 'pricepoint-v5';
const OFFLINE_URL = '/offline.html';

// ===== ONLY CACHE STATIC ASSETS THAT EXIST =====
const urlsToCache = [
    '/pos',                    // ← Main POS page (STATIC HTML)
    '/offline.html',           // ← Offline fallback
    '/manifest.json',          // ← Manifest
    '/static/sw.js',           // ← This file
    '/static/icons/icon-72.png',
    '/static/icons/icon-96.png',
    '/static/icons/icon-128.png',
    '/static/icons/icon-144.png',
    '/static/icons/icon-152.png',
    '/static/icons/icon-192.png',
    '/static/icons/icon-384.png',
    '/static/icons/icon-512.png'
];

// ============================================================
// INSTALL - Cache only what exists
// ============================================================

self.addEventListener('install', event => {
    console.log('[SW] 📦 Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching assets...');
                // Use try/catch for each URL to avoid failures
                return Promise.allSettled(
                    urlsToCache.map(url => {
                        return cache.add(url).catch(err => {
                            console.warn('[SW] ⚠️ Failed to cache:', url, err.message);
                            // Don't fail the whole install for one bad URL
                            return Promise.resolve();
                        });
                    })
                );
            })
            .then(() => {
                console.log('[SW] ✅ Installation complete');
                return self.skipWaiting();
            })
    );
});

// ============================================================
// ACTIVATE - Clean old caches
// ============================================================

self.addEventListener('activate', event => {
    console.log('[SW] 🔧 Activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        console.log('[SW] 🗑️ Deleting old cache:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] ✅ Activation complete');
            return self.clients.claim();
        })
    );
});

// ============================================================
// FETCH - OFFLINE-FIRST STRATEGY
// ============================================================

self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        event.respondWith(fetch(request));
        return;
    }
    
    // Skip Supabase/API requests - let them fail gracefully
    if (url.hostname.includes('supabase.co') || url.pathname.startsWith('/admin/api/')) {
        event.respondWith(
            fetch(request).catch(() => {
                return new Response(JSON.stringify({
                    offline: true,
                    message: 'You are offline. Using cached data.'
                }), {
                    status: 503,
                    headers: { 'Content-Type': 'application/json' }
                });
            })
        );
        return;
    }
    
    // ===== HTML PAGES - Network first, fallback to offline.html =====
    if (request.headers.get('Accept')?.includes('text/html')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    if (response && response.status === 200) {
                        const cloned = response.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => cache.put(request, cloned))
                            .catch(() => {});
                    }
                    return response;
                })
                .catch(async () => {
                    // Try cache first
                    const cached = await caches.match(request);
                    if (cached) {
                        console.log('[SW] ✅ Serving cached page:', url.pathname);
                        return cached;
                    }
                    // Fallback to offline page
                    console.log('[SW] 📡 Serving offline page');
                    return caches.match(OFFLINE_URL);
                })
        );
        return;
    }
    
    // ===== STATIC ASSETS - Cache first (OFFLINE-FIRST) =====
    event.respondWith(
        caches.match(request)
            .then(cached => {
                if (cached) {
                    console.log('[SW] ✅ Cache hit:', url.pathname);
                    return cached;
                }
                
                // Try network
                return fetch(request)
                    .then(response => {
                        if (response && response.status === 200) {
                            const clone = response.clone();
                            caches.open(CACHE_NAME)
                                .then(cache => cache.put(request, clone))
                                .catch(() => {});
                        }
                        return response;
                    })
                    .catch(() => {
                        // Return empty response for assets
                        if (url.pathname.match(/\.(css|js|png|jpg|jpeg|svg|ico)$/)) {
                            return new Response('', { status: 404 });
                        }
                        return new Response('Offline', { status: 503 });
                    });
            })
    );
});

// ============================================================
// BACKGROUND SYNC - Auto-sync when online
// ============================================================

self.addEventListener('sync', event => {
    if (event.tag === 'sync-orders') {
        console.log('[SW] 🔄 Background sync triggered');
        event.waitUntil(syncOrders());
    }
});

async function syncOrders() {
    try {
        const clients = await self.clients.matchAll();
        for (const client of clients) {
            client.postMessage({
                type: 'SYNC_ORDERS',
                payload: { timestamp: Date.now() }
            });
        }
        console.log('[SW] ✅ Sync triggered for all clients');
    } catch(e) {
        console.error('[SW] ❌ Sync failed:', e);
    }
}

// ============================================================
// MESSAGE HANDLER
// ============================================================

self.addEventListener('message', event => {
    console.log('[SW] 📨 Message received:', event.data);
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

console.log('[SW] 🚀 Service Worker loaded');
