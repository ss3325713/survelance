// PySURVEILLANCE Service Worker
// Enables Native Device & OS Notification Center integration (Android Drawer / Desktop OS)

const CACHE_NAME = 'pysurveillance-sw-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Handle incoming Web Push notifications
self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { body: event.data.text() };
    }
  }

  const cat = data.category || 'Surveillance Alert';
  const title = data.title || `🚨 PySURVEILLANCE: ${cat}`;
  const options = {
    body: data.body || data.label || 'Motion detected in monitored zone',
    icon: '/static/favicon.svg',
    badge: '/static/favicon.svg',
    vibrate: [200, 100, 200, 100, 200],
    tag: data.tag || `pysurv-${data.id || Date.now()}`,
    renotify: true,
    data: {
      url: data.url || '/#incidents',
      id: data.id || null,
    },
    actions: [
      { action: 'inspect', title: '🔍 Inspect Event' },
      { action: 'dismiss', title: 'Dismiss' },
    ],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// Handle notification interaction (clicking the notification in system tray)
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = (event.notification.data && event.notification.data.url) || '/#incidents';
  const eventId = event.notification.data && event.notification.data.id;

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.focus();
          client.postMessage({
            type: 'NOTIFICATION_NAVIGATE',
            view: 'incidents',
            eventId: eventId,
          });
          return;
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
