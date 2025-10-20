// self.addEventListener('install', (e) => {
//   console.log('here')
//     e.waitUntill(
//       caches
//         .open('login-store')
//         .then((cache) => {
//           cache.addAll([
//             '/static/styles/general.css',
//             '/static/styles/login/login.css',
//             '/static/scripts/login/login.js',
//             '/static/login/login.html'
//           ])
//           console.log('here')
//         })
//     )
// });

// self.addEventListener('fetch', (e) => {
//   console.log('here')
//   console.log(e.request.url);
//   e.respondWith(
//     cache.match(e.request).then((response) => {
//       response || fetch(e.request)
//     })
//   )
// })

// client.navigate() or clients.openWindow()