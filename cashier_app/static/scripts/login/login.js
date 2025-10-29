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

    let data;

    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        body: formData
      });
      data = await response.json();

      if (response.status === 401 && data.error === 'invalid_credentials') {
        throw new Error('invalid_credentials')
      }
    
      if (!response.ok) {
        throw new Error('unexpected_error');
      }
    } catch (error) {
      if (error.message === 'invalid_credentials') {
        errorMessageElement.innerHTML = 'Neplatné uživatelské jméno nebo heslo.'
      } else {
        errorMessageElement.innerHTML = 'Při přihlašování nastala chyba. Zkuste to později.';
      }
      errorMessageElement.classList.add('show-error-message');
      return;
    } finally {
      submitButton.disabled = false;
    }
    window.location.href = data.redirect_url;
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