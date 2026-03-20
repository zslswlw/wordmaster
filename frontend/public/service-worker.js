/**
 * WordMaster Service Worker
 * 实现音频缓存和离线支持
 */

const CACHE_NAME = 'wordmaster-v1';
const AUDIO_CACHE = 'wordmaster-audio-v1';

// 需要预缓存的核心资源
const CORE_ASSETS = [
  '/',
  '/index.html',
  '/assets/index.css',
  '/assets/index.js',
];

// 安装时预缓存核心资源
self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching core assets');
        return cache.addAll(CORE_ASSETS);
      })
      .then(() => {
        console.log('[SW] Install completed');
        return self.skipWaiting();
      })
      .catch((err) => {
        console.error('[SW] Install failed:', err);
      })
  );
});

// 激活时清理旧缓存
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => {
            return name !== CACHE_NAME && name !== AUDIO_CACHE;
          })
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => {
      console.log('[SW] Activation completed');
      return self.clients.claim();
    })
  );
});

// 拦截请求
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // 音频文件特殊处理
  if (url.pathname.startsWith('/audio/')) {
    event.respondWith(handleAudioRequest(request));
    return;
  }
  
  // API 请求不缓存
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(request));
    return;
  }
  
  // 其他资源使用网络优先策略
  event.respondWith(handleCoreRequest(request));
});

/**
 * 处理音频请求 - 缓存优先
 */
async function handleAudioRequest(request) {
  const cache = await caches.open(AUDIO_CACHE);
  
  // 先尝试从缓存读取
  const cached = await cache.match(request);
  if (cached) {
    console.log('[SW] Audio from cache:', request.url);
    return cached;
  }
  
  // 缓存未命中，从网络获取
  try {
    const response = await fetch(request);
    
    if (response.ok) {
      // 保存到缓存
      cache.put(request, response.clone());
      console.log('[SW] Audio cached:', request.url);
    }
    
    return response;
  } catch (error) {
    console.error('[SW] Audio fetch failed:', error);
    // 返回一个空的音频响应，避免报错
    return new Response(null, { status: 404 });
  }
}

/**
 * 处理核心资源请求 - 网络优先，失败时使用缓存
 */
async function handleCoreRequest(request) {
  try {
    // 先尝试网络
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      // 更新缓存
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    // 网络失败，使用缓存
    console.log('[SW] Network failed, using cache:', request.url);
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    
    if (cached) {
      return cached;
    }
    
    // 缓存也没有，返回错误
    return new Response('Network error', { status: 408 });
  }
}

/**
 * 预缓存音频文件
 * 由主应用调用
 */
async function precacheAudio(audioUrls) {
  const cache = await caches.open(AUDIO_CACHE);
  
  for (const url of audioUrls) {
    const exists = await cache.match(url);
    if (!exists) {
      try {
        const response = await fetch(url);
        if (response.ok) {
          await cache.put(url, response);
          console.log('[SW] Precached:', url);
        }
      } catch (error) {
        console.error('[SW] Precache failed:', url, error);
      }
    }
  }
}

// 监听消息
self.addEventListener('message', (event) => {
  if (event.data.type === 'PRECACHE_AUDIO') {
    precacheAudio(event.data.urls);
  }
  
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
