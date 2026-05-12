/**
 * @file Přihlašovací formulář a přesměrování přihlášeného uživatele.
 */
import { order } from "../index/order.js";
import { saveSelectedCategory } from "../index/products.js";


const form = document.querySelector('#login-form');
const errorMessageElement = document.querySelector('.error-message');
const submitButton = document.querySelector('#submit-button');
const showPassword = document.querySelector('.pw-eye');
const passwordInput = document.querySelector('#password');


/**
 * Zkontroluje, zda je uživatel již přihlášen, a případně ho přesměruje na hlavní stránku.
 * @returns {Promise<void>}
 */
async function redirectLoggedIn() {
  try {
    const response = await fetch('/api/session');

    if (!response.ok) {
      return;
    }

    const data = await response.json();

    if (data.employee) {
      window.location.href = '/';
    }
  } catch (error) {
    return;
  }
}

redirectLoggedIn();

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
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        body: formData
      });
      data = await response.json();

      if (response.status === 401 && data.error === 'invalid_credentials') {
        throw new Error('invalid_credentials')
      }

      if (response.status === 429) {
        throw new Error('too_many_requests');
      }

      if (!response.ok) {
        throw new Error('unexpected_error');
      }
    } catch (error) {
      if (error.message === 'invalid_credentials') {
        errorMessageElement.innerHTML = 'Neplatné uživatelské jméno nebo heslo.'
      } else if (error.message === 'too_many_requests') {
        errorMessageElement.innerHTML = 'Příliš mnoho pokusů o přihlášení. Zkuste to znovu za pár minut.';
      } else {
        errorMessageElement.innerHTML = 'Při přihlašování nastala chyba. Zkuste to později.';
      }
      errorMessageElement.classList.add('show-error-message');
      return;
    } finally {
      submitButton.disabled = false;
    }
    // sessionStorage.clear();
    order.reset();
    saveSelectedCategory(null);
    localStorage.removeItem('copied');
    window.location.href = data.redirect_url;
  });
}

showPassword.addEventListener('click', () => {
  if (showPassword.classList.contains('state-show')) {
    passwordInput.setAttribute('type', 'password');
  } else {
    passwordInput.setAttribute('type', 'text');
  }

  const isShow = showPassword.classList.toggle('state-hide');
  showPassword.classList.toggle('state-show', !isShow);
  showPassword.classList.toggle('state-hide', isShow);
});
