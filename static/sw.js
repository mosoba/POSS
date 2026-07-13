// ============================================================
// SERVICE WORKER - PricePoint POS (Complete Offline Solution)
// ============================================================

const CACHE_NAME = 'pricepoint-v4';
const OFFLINE_URL = '/offline.html';

// ===== PAGES TO CACHE =====
const urlsToCache = [
    '/',
    '/admin',
    '/admin/pos',
    '/login',
    '/offline.html',
    '/manifest.json',
];

// ============================================================
// INSTALL
// ============================================================

self.addEventListener('install', event => {
    console.log('[SW] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching assets...');
                return Promise.allSettled(
                    urlsToCache.map(url => {
                        return cache.add(url).catch(err => {
                            console.log('[SW] Failed to cache:', url);
                        });
                    })
                );
            })
            .then(() => {
                console.log('[SW] Installation complete');
                return self.skipWaiting();
            })
    );
});

// ============================================================
// ACTIVATE
// ============================================================

self.addEventListener('activate', event => {
    console.log('[SW] Activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        console.log('[SW] Deleting old cache:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] Activation complete');
            return self.clients.claim();
        })
    );
});

// ============================================================
// FETCH - Smart offline strategy
// ============================================================

self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        event.respondWith(fetch(request));
        return;
    }
    
    // Skip Supabase requests - handled by IndexedDB
    if (url.hostname.includes('supabase.co')) {
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
    
    // API requests - try network, fallback to cache
    if (url.pathname.startsWith('/admin/api/') || url.pathname.startsWith('/api/')) {
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
                .catch(() => {
                    return caches.match(request)
                        .then(cached => {
                            if (cached) {
                                console.log('[SW] Serving cached API:', url.pathname);
                                return cached;
                            }
                            return new Response(JSON.stringify({
                                offline: true,
                                message: 'You are offline.'
                            }), {
                                status: 503,
                                headers: { 'Content-Type': 'application/json' }
                            });
                        });
                })
        );
        return;
    }
    
    // HTML pages - Network first
    const isHTML = request.headers.get('Accept')?.includes('text/html');
    
    if (isHTML) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    if (response && response.status === 200) {
                        const cloned = response.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => cache.put(request, cloned));
                    }
                    return response;
                })
                .catch(() => {
                    return caches.match(request)
                        .then(cached => {
                            if (cached) return cached;
                            return caches.match(OFFLINE_URL);
                        });
                })
        );
        return;
    }
    
    // Assets - Cache first
    event.respondWith(
        caches.match(request)
            .then(response => {
                if (response) {
                    return response;
                }
                return fetch(request)
                    .then(networkResponse => {
                        if (!networkResponse || networkResponse.status !== 200) {
                            return networkResponse;
                        }
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => cache.put(request, responseToCache))
                            .catch(() => {});
                        return networkResponse;
                    });
            })
    );
});

self.addEventListener('message', event => {
    console.log('[SW] Message received:', event.data);
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

console.log('[SW] Service Worker loaded');
