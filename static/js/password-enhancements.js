document.addEventListener('DOMContentLoaded', () => {
  const passwordInput = document.querySelector('[data-password-primary]');
  const confirmInput = document.querySelector('[data-password-confirm]');
  const strength = passwordInput?.closest('.form-group')?.querySelector('.password-strength');
  const strengthLabel = strength?.querySelector('[data-strength-label]');
  const strengthSegments = strength?.querySelectorAll('[data-strength-segment]');
  const requirementItems = document.querySelectorAll('[data-password-requirement]');
  const matchMessage = document.querySelector('[data-password-match]');
  const generatedPassword = document.querySelector('[data-generated-password]');
  const generatedValue = generatedPassword?.querySelector('[data-generated-value]');
  const copyButton = generatedPassword?.querySelector('[data-copy-password]');
  let generatedPasswordTimer;
  let copyButtonTimer;

  document.querySelectorAll('.password-toggle').forEach((button) => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.getAttribute('aria-controls'));
      if (!input) return;

      const showPassword = input.type === 'password';
      input.type = showPassword ? 'text' : 'password';
      button.setAttribute('aria-label', showPassword ? 'Hide password' : 'Show password');
      button.querySelector('[data-eye-open]').hidden = showPassword;
      button.querySelector('[data-eye-closed]').hidden = !showPassword;
    });
  });

  const updatePasswordFeedback = () => {
    if (passwordInput && strength && strengthLabel && strengthSegments) {
      const password = passwordInput.value;
      const checks = {
        length: password.length >= 8,
        case: /[a-z]/.test(password) && /[A-Z]/.test(password),
        number: /\d/.test(password),
        symbol: /[^A-Za-z0-9]/.test(password),
      };

      requirementItems.forEach((item) => {
        item.classList.toggle('is-met', Boolean(checks[item.dataset.passwordRequirement]));
      });

      const score = [
        password.length >= 8,
        password.length >= 12,
        /[a-z]/.test(password),
        /[A-Z]/.test(password),
        /\d/.test(password),
        /[^A-Za-z0-9]/.test(password),
      ].filter(Boolean).length;

      const level = password.length === 0
        ? ''
        : score <= 2
          ? 'weak'
          : score === 3
            ? 'fair'
            : score === 4
              ? 'good'
              : 'strong';
      const labels = { weak: 'Weak', fair: 'Fair', good: 'Good', strong: 'Strong' };
      const filledSegments = { weak: 1, fair: 2, good: 3, strong: 4 }[level] || 0;

      strength.dataset.strength = level;
      strengthLabel.textContent = labels[level] || 'Password strength';
      strengthSegments.forEach((segment, index) => {
        segment.classList.toggle('is-filled', index < filledSegments);
      });
    }

    if (confirmInput && matchMessage) {
      const hasConfirmation = confirmInput.value.length > 0;
      const matches = hasConfirmation && confirmInput.value === passwordInput.value;
      matchMessage.textContent = hasConfirmation
        ? matches ? 'Passwords match' : 'Passwords do not match'
        : '';
      matchMessage.classList.toggle('is-match', matches);
      matchMessage.classList.toggle('is-mismatch', hasConfirmation && !matches);
    }
  };

  passwordInput?.addEventListener('input', updatePasswordFeedback);
  confirmInput?.addEventListener('input', updatePasswordFeedback);
  updatePasswordFeedback();

  const randomIndex = (length) => {
    const values = new Uint32Array(1);
    const limit = Math.floor(0x100000000 / length) * length;
    do {
      window.crypto.getRandomValues(values);
    } while (values[0] >= limit);
    return values[0] % length;
  };

  const chooseCharacter = (characters) => characters[randomIndex(characters.length)];
  const suggestLink = document.querySelector('[data-suggest-password]');

  suggestLink?.addEventListener('click', (event) => {
    event.preventDefault();
    if (!passwordInput || !confirmInput || !generatedPassword || !generatedValue) return;

    const groups = [
      'ABCDEFGHJKLMNPQRSTUVWXYZ',
      'abcdefghijkmnopqrstuvwxyz',
      '23456789',
      '!@#$%^&*?',
    ];
    const allCharacters = groups.join('');
    const characters = groups.map(chooseCharacter);

    while (characters.length < 14) {
      characters.push(chooseCharacter(allCharacters));
    }
    for (let index = characters.length - 1; index > 0; index -= 1) {
      const swapIndex = randomIndex(index + 1);
      [characters[index], characters[swapIndex]] = [characters[swapIndex], characters[index]];
    }

    const suggested = characters.join('');
    passwordInput.value = suggested;
    confirmInput.value = suggested;
    generatedValue.textContent = suggested;
    generatedPassword.hidden = false;
    updatePasswordFeedback();

    window.clearTimeout(generatedPasswordTimer);
    generatedPasswordTimer = window.setTimeout(() => {
      generatedValue.textContent = '';
      generatedPassword.hidden = true;
    }, 10000);
  });

  copyButton?.addEventListener('click', async () => {
    if (!generatedValue?.textContent) return;

    try {
      await navigator.clipboard.writeText(generatedValue.textContent);
      copyButton.textContent = 'Copied';
      window.clearTimeout(copyButtonTimer);
      copyButtonTimer = window.setTimeout(() => {
        copyButton.textContent = 'Copy';
      }, 1500);
    } catch {
      generatedPassword.querySelector('.generated-password-note').textContent =
        'Copy unavailable. Select the password to copy it.';
    }
  });
});
