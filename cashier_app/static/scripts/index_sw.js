// self.addEventListener('install', (event) => {
//   console.log('here')
//     event.waitUntill(
//       caches
//         .open('index-store')
//         .then((cache) => {
//           cache.addAll([
//             '/static/styles/general.css',
//             '/static/styles/login/index.css',
//             '/static/scripts/index.js',
//             '/static/index.html'
//           ])
//           console.log('here')
//         })
//     )
// });

// self.addEventListener('fetch', (event) => {
//   console.log('here')
//   console.log(event.request.url);
//   event.respondWith((async () => {
//     const resp = await fetch(event.request);
//     data = await resp.json()
//     const navTo = data.redirect_url;
//     if (navTo) {
//       const all = await clients.matchAll({ type: 'window', includeUncontrolled: true });
//       if (all && all[0]) {
//         // navigate the first client (the controlled page)
//         await all[0].navigate(navTo);
//       } else {
//         // fallback: open a new window/tab
//         await clients.openWindow(navTo);
//       }
//       return new Response({success: false}, { status: 204 }); // return something to the fetch() call
//     }
//     return resp; // no navigation header, just return the real response
//   })());
// });

//   event.respondWith(
//     cache.match(event.request).then((response) => {
//       response || fetch(event.request)
//     })
//   )
// })

// client.navigate() or clients.openWindow()