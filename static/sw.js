// ============================================================
// SERVICE WORKER - PricePoint POS (FIXED CACHING)
// ============================================================

const CACHE_NAME = 'pricepoint-v8';
const OFFLINE_URL = '/offline.html';

// ===== CACHE STATIC ICONS - CORRECT PATH =====
const urlsToCache = [
    '/offline.html',
    '/manifest.json',
    // Static icons (CORRECT PATH)
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
// INSTALL
// ============================================================

self.addEventListener('install', event => {
    console.log('[SW] 📦 Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching assets...');
                return Promise.allSettled(
                    urlsToCache.map(url => {
                        return cache.add(url)
                            .then(() => console.log('[SW] ✅ Cached:', url))
                            .catch(err => {
                                console.warn('[SW] ⚠️ Failed to cache:', url, err.message);
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
// ACTIVATE
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
// FETCH
// ============================================================

self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    if (request.method !== 'GET') {
        event.respondWith(fetch(request));
        return;
    }
    
    if (url.pathname.startsWith('/admin/api/') || url.pathname.includes('supabase.co')) {
        event.respondWith(
            fetch(request).catch(() => {
                return new Response(JSON.stringify({
                    offline: true,
                    message: 'You are offline.'
                }), {
                    status: 503,
                    headers: { 'Content-Type': 'application/json' }
                });
            })
        );
        return;
    }
    
    if (request.headers.get('Accept')?.includes('text/html')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    if (response && response.status === 200) {
                        const cloned = response.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => {
                                try {
                                    cache.put(request, cloned);
                                    console.log('[SW] 📦 Cached page:', url.pathname);
                                } catch(e) {}
                            });
                    }
                    return response;
                })
                .catch(async () => {
                    const cached = await caches.match(request);
                    if (cached) {
                        console.log('[SW] ✅ Serving cached page:', url.pathname);
                        return cached;
                    }
                    console.log('[SW] 📡 Serving offline page');
                    return caches.match(OFFLINE_URL);
                })
        );
        return;
    }
    
    event.respondWith(
        caches.match(request)
            .then(cached => {
                if (cached) {
                    console.log('[SW] ✅ Cache hit:', url.pathname);
                    return cached;
                }
                return fetch(request)
                    .then(response => {
                        if (response && response.status === 200) {
                            const clone = response.clone();
                            caches.open(CACHE_NAME)
                                .then(cache => {
                                    try {
                                        cache.put(request, clone);
                                    } catch(e) {}
                                })
                                .catch(() => {});
                        }
                        return response;
                    })
                    .catch(() => {
                        if (url.pathname.match(/\.(css|js|png|jpg|jpeg|svg|ico|woff|woff2|ttf)$/)) {
                            return new Response('', { status: 404 });
                        }
                        return new Response('Offline', { status: 503 });
                    });
            })
    );
});

// ============================================================
// BACKGROUND SYNC
// ============================================================

self.addEventListener('sync', event => {
    if (event.tag === 'sync-orders') {
        console.log('[SW] 🔄 Background sync triggered');
        event.waitUntil(
            self.clients.matchAll().then(clients => {
                clients.forEach(client => {
                    client.postMessage({
                        type: 'SYNC_ORDERS',
                        payload: { timestamp: Date.now() }
                    });
                });
            })
        );
    }
});

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
