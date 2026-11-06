// Add this function at the top level
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('loginForm');
  const emailInput = document.getElementById('email');
  const passwordInput = document.getElementById('password');
  const emailError = document.getElementById('emailError');
  const passwordError = document.getElementById('passwordError');
  const messageBox = document.getElementById('messageBox');

  // Form submission handler
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    let isValid = true;

    // Validate email
    if (!validateEmail(emailInput.value)) {
      emailError.textContent = 'Please enter a valid email address.';
      emailError.classList.remove('hidden');
      isValid = false;
    } else {
      emailError.classList.add('hidden');
    }

    // Validate password
    if (!passwordInput.value) {
      passwordError.textContent = 'Password is required.';
      passwordError.classList.remove('hidden');
      isValid = false;
    } else {
      passwordError.classList.add('hidden');
    }

    // Submit form if valid
    if (isValid) {
      // Show loading state
      const loginButton = document.getElementById('loginButton');
      const loginButtonText = document.getElementById('loginButtonText');
      const loginSpinner = document.getElementById('loginSpinner');
      
      loginButton.disabled = true;
      loginButtonText.textContent = 'Logging in...';
      loginSpinner.classList.remove('hidden');
      
      const formData = new FormData(form);
      fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
          'X-CSRFToken': getCookie('csrftoken')
        },
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            showMessage(data.error, 'error');
            // Reset button state
            loginButton.disabled = false;
            loginButtonText.textContent = 'Login';
            loginSpinner.classList.add('hidden');
          } else {
            showMessage(data.message, 'success');
            loginButtonText.textContent = 'Redirecting...';
            const next = new URLSearchParams(window.location.search).get('next') || '/';
            setTimeout(() => {
              window.location.href = next;
            }, 1500);
          }
        })
        .catch(() => {
          showMessage('An error occurred. Please try again.', 'error');
          // Reset button state
          loginButton.disabled = false;
          loginButtonText.textContent = 'Login';
          loginSpinner.classList.add('hidden');
        });
    }
  });

  // Helper functions
  function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  function showMessage(message, type) {
    messageBox.textContent = message;
    messageBox.className = `message-box ${type}`;
    messageBox.classList.remove('hidden');
  }
});