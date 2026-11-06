document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('registrationForm');
  const emailInput = document.getElementById('email');
  const password1Input = document.getElementById('password1');
  const password2Input = document.getElementById('password2');
  const emailError = document.getElementById('emailError');
  const passwordError = document.getElementById('passwordError');
  const confirmPasswordError = document.getElementById('confirmPasswordError');
  const messageBox = document.getElementById('messageBox');

  // Password validation rules
  const passwordRules = {
    length: /.{8,}/,
    uppercase: /[A-Z]/,
    lowercase: /[a-z]/,
    digit: /\d/,
    special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/,
  };

  // Live password validation with strength bar
  password1Input.addEventListener('input', function () {
    const password = password1Input.value;
    
    // Calculate password strength
    let strength = 0;
    let metCriteria = 0;
    
    if (passwordRules.length.test(password)) metCriteria++;
    if (passwordRules.uppercase.test(password)) metCriteria++;
    if (passwordRules.lowercase.test(password)) metCriteria++;
    if (passwordRules.digit.test(password)) metCriteria++;
    if (passwordRules.special.test(password)) metCriteria++;
    
    // Calculate strength percentage and color
    const strengthBar = document.getElementById('strengthBar');
    const strengthText = document.getElementById('strengthText');
    
    if (password.length === 0) {
      strengthBar.style.width = '0%';
      strengthBar.style.backgroundColor = '#ba1a1a'; // red
      strengthText.textContent = 'Weak';
      strengthText.style.color = '#ba1a1a';
    } else if (metCriteria <= 2) {
      strengthBar.style.width = '33%';
      strengthBar.style.backgroundColor = '#ba1a1a'; // red
      strengthText.textContent = 'Weak';
      strengthText.style.color = '#ba1a1a';
    } else if (metCriteria === 3) {
      strengthBar.style.width = '66%';
      strengthBar.style.backgroundColor = '#00bcd4'; // cyan
      strengthText.textContent = 'Medium';
      strengthText.style.color = '#00bcd4';
    } else if (metCriteria >= 4) {
      strengthBar.style.width = '100%';
      strengthBar.style.backgroundColor = '#16a34a'; // green
      strengthText.textContent = 'Strong';
      strengthText.style.color = '#16a34a';
    }
    
    // Clear password error when user starts typing
    if (passwordError.textContent) {
      passwordError.textContent = '';
    }
  });

  // Confirm password validation
  password2Input.addEventListener('input', function () {
    if (password1Input.value !== password2Input.value) {
      confirmPasswordError.textContent = 'Passwords do not match';
      confirmPasswordError.classList.remove('hidden');
    } else {
      confirmPasswordError.textContent = '';
      confirmPasswordError.classList.add('hidden');
    }
  });

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
    if (!validatePassword(password1Input.value)) {
      passwordError.textContent = 'Password must meet all requirements.';
      passwordError.classList.remove('hidden');
      isValid = false;
    } else {
      passwordError.classList.add('hidden');
    }

    // Validate password confirmation
    if (password1Input.value !== password2Input.value) {
      confirmPasswordError.textContent = 'Passwords do not match';
      confirmPasswordError.classList.remove('hidden');
      isValid = false;
    } else {
      confirmPasswordError.classList.add('hidden');
    }

    // Submit form if valid
    if (isValid) {
      // Show loading state
      const signupButton = document.getElementById('signupButton');
      const signupButtonText = document.getElementById('signupButtonText');
      const signupSpinner = document.getElementById('signupSpinner');
      
      signupButton.disabled = true;
      signupButtonText.textContent = 'Creating Account...';
      signupSpinner.classList.remove('hidden');
      
      const formData = new FormData(form);
      fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
          'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
        },
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            showMessage(data.error, 'error');
            // Reset button state
            signupButton.disabled = false;
            signupButtonText.textContent = 'Create Account';
            signupSpinner.classList.add('hidden');
          } else {
            showMessage(data.message || 'Account created! Taking you there...', 'success');
            signupButtonText.textContent = 'Redirecting...';
            form.reset();
            setTimeout(() => {
              window.location.href = data.next || '/';
            }, 1500);
          }
        })
        .catch((error) => {
          showMessage('An error occurred. Please try again.', 'error');
          // Reset button state
          signupButton.disabled = false;
          signupButtonText.textContent = 'Create Account';
          signupSpinner.classList.add('hidden');
        });
    }
  });

  // Helper functions
  function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  function validatePassword(password) {
    return Object.values(passwordRules).every((rule) => rule.test(password));
  }

  function showMessage(message, type) {
    messageBox.textContent = message;
    messageBox.className = `message-box ${type}`;
    messageBox.classList.remove('hidden');
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
      setTimeout(() => {
        messageBox.classList.add('hidden');
      }, 5000);
    }
  }
});