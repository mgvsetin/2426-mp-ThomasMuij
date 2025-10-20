const form = document.querySelector('#login-form');
const errorMessageElement = document.querySelector('.error-message');
const submitButton = document.querySelector('#submit-button');
// make required

if (form) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorMessageElement.classList.remove('show-error-message');
    errorMessageElement.innerHTML = '';
    submitButton.disabled = true;

    const formData = new FormData(event.target);

    formData.set('username-email', formData.get('username-email').trim())

    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
    
      if (response.ok) {
        window.location.href = data.redirect_url;
        return;
      }

      if (data && data.error === 'invalid_credentials' && response.status === 401) {
        errorMessageElement.innerHTML = 'Neplatné uživatelské jméno nebo heslo.';
      } else {
        errorMessageElement.innerHTML = 'Při přihlašování nastala chyba. Zkuste to později.';
      }
      errorMessageElement.classList.add('show-error-message');

    } catch (error) {
      errorMessageElement.innerHTML = 'Při přihlašování nastala chyba. Zkuste to později.';
      errorMessageElement.classList.add('show-error-message');
    } finally {
      submitButton.disabled = false;
    }
  });
}

// if ('serviceWorker' in navigator) {
//   navigator.serviceWorker
//     .register(
//       '/static/scripts/login/service_worker.js'
//     ).then(() => {
//       console.log('service worker registered')
//     })
// }