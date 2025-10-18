async function displayLoginError() {
  response = await fetch('/session/login-error')
  display_error = await response.json()

  if (display_error) {
    document.querySelector('#login-form')
      .classList.add('show-error-message')
  }
}

displayLoginError()