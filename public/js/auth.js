document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');

    const message = document.getElementById(
        'login-message'
    ) || document.getElementById('register-message');

    function showMessage(element, text, type) {
        if (!element) {
            return;
        }

        element.textContent = text;
        element.className = `auth-message show ${type}`;
    }

    function hideMessage(element) {
        if (!element) {
            return;
        }

        element.textContent = '';
        element.className = 'auth-message';
    }

    document.querySelectorAll('.password-toggle').forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.dataset.target;
            const input = document.getElementById(targetId);

            if (!input) {
                return;
            }

            const icon = button.querySelector('.password-icon');

            if (input.type === 'password') {
                input.type = 'text';

                if (icon) {
                    icon.innerHTML = `
                        <svg viewBox="0 0 24 24">
                            <path d="M3 3l18 18"></path>
                            <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"></path>
                            <path d="M9.9 4.2A10.8 10.8 0 0 1 12 4c5.2 0 8.7 4 10 8-0.4 1.2-1.1 2.5-2 3.5"></path>
                            <path d="M6.6 6.6C4.7 7.9 3.5 10 2 12c1.3 4 4.8 8 10 8 1.6 0 3-.4 4.2-1"></path>
                        </svg>
                    `;
                }
            } else {
                input.type = 'password';

                if (icon) {
                    icon.innerHTML = `
                        <svg viewBox="0 0 24 24">
                            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"></path>
                            <circle cx="12" cy="12" r="2.5"></circle>
                        </svg>
                    `;
                }
            }
        });
    });

    if (loginForm) {
        loginForm.addEventListener('submit', async event => {
            event.preventDefault();

            hideMessage(message);

            const email = document.getElementById('email');
            const password = document.getElementById('password');
            const submitButton = loginForm.querySelector('button[type="submit"]');

            if (!email || !password) {
                return;
            }

            if (!email.value.trim() || !password.value) {
                showMessage(
                    message,
                    'Veuillez remplir tous les champs.',
                    'error'
                );
                return;
            }

            if (!email.validity.valid) {
                showMessage(
                    message,
                    'Veuillez saisir une adresse e-mail valide.',
                    'error'
                );
                return;
            }

            const data = {
                email: email.value.trim(),
                password: password.value
            };

            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = 'Connexion...';
            }

            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (!response.ok || !result.success) {
                    showMessage(
                        message,
                        result.message || 'Une erreur est survenue.',
                        'error'
                    );
                    return;
                }

                showMessage(
                    message,
                    result.message || 'Connexion réussie.',
                    'success'
                );

                if (result.redirect) {
                    window.location.href = result.redirect;
                }
            } catch (error) {
                showMessage(
                    message,
                    'Impossible de contacter le serveur.',
                    'error'
                );
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = 'Se connecter';
                }
            }
        });
    }

    if (registerForm) {
        registerForm.addEventListener('submit', async event => {
            event.preventDefault();

            hideMessage(message);

            const lastName = document.getElementById('last_name');
            const firstName = document.getElementById('first_name');
            const email = document.getElementById('email');
            const phone = document.getElementById('phone');
            const password = document.getElementById('password');
            const passwordConfirmation = document.getElementById('password_confirmation');
            const terms = document.getElementById('terms');
            const submitButton = registerForm.querySelector('button[type="submit"]');

            if (
                !lastName ||
                !firstName ||
                !email ||
                !phone ||
                !password ||
                !passwordConfirmation ||
                !terms
            ) {
                return;
            }

            if (
                !lastName.value.trim() ||
                !firstName.value.trim() ||
                !email.value.trim() ||
                !phone.value.trim() ||
                !password.value ||
                !passwordConfirmation.value
            ) {
                showMessage(
                    message,
                    'Veuillez remplir tous les champs.',
                    'error'
                );
                return;
            }

            if (!email.validity.valid) {
                showMessage(
                    message,
                    'Veuillez saisir une adresse e-mail valide.',
                    'error'
                );
                return;
            }

            if (password.value.length < 8) {
                showMessage(
                    message,
                    'Le mot de passe doit contenir au moins 8 caractères.',
                    'error'
                );
                return;
            }

            if (password.value !== passwordConfirmation.value) {
                showMessage(
                    message,
                    'Les mots de passe ne correspondent pas.',
                    'error'
                );
                return;
            }

            if (!terms.checked) {
                showMessage(
                    message,
                    'Vous devez accepter les conditions d’utilisation.',
                    'error'
                );
                return;
            }

            const data = {
                last_name: lastName.value.trim(),
                first_name: firstName.value.trim(),
                email: email.value.trim(),
                phone: phone.value.trim(),
                password: password.value,
                password_confirmation: passwordConfirmation.value,
                terms: terms.checked
            };

            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = 'Création...';
            }

            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (!response.ok || !result.success) {
                    showMessage(
                        message,
                        result.message || 'Une erreur est survenue.',
                        'error'
                    );
                    return;
                }

                showMessage(
                    message,
                    result.message || 'Compte créé avec succès.',
                    'success'
                );

                if (result.redirect) {
                    window.location.href = result.redirect;
                }
            } catch (error) {
                showMessage(
                    message,
                    'Impossible de contacter le serveur.',
                    'error'
                );
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = 'Créer mon compte';
                }
            }
        });
    }
});