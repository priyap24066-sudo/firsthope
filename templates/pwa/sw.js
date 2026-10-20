self.addEventListener('install', function () {
  self.skipWaiting();
});
self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});
self.addEventListener('fetch', function (event) {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(function () {
        return new Response(
          '<h2 style="font-family:Arial;text-align:center;margin-top:40px">You are offline. Please check your internet connection.</h2>',
          { headers: { 'Content-Type': 'text/html' } }
        );
      })
    );
  }
});
