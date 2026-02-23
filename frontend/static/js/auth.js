document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const logoutBtn = document.getElementById("logoutBtn");

    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;
            const errorDiv = document.getElementById("authError");
            const submitBtn = loginForm.querySelector('button[type="submit"]');

            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="ri-loader-4-line spin"></i> Authenticating...';
            errorDiv.style.display = "none";

            try {
                const res = await fetch("/api/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password })
                });

                const data = await res.json();
                if (res.ok) {
                    window.location.href = "/dashboard";
                } else {
                    errorDiv.textContent = data.detail || "Login failed";
                    errorDiv.style.display = "block";
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="ri-login-circle-line"></i> Login';
                }
            } catch (err) {
                errorDiv.textContent = "Network error occurred";
                errorDiv.style.display = "block";
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="ri-login-circle-line"></i> Login';
            }
        });
    }

    if (registerForm) {
        registerForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;
            const confirmPassword = document.getElementById("confirmPassword").value;
            const errorDiv = document.getElementById("authError");
            const submitBtn = registerForm.querySelector('button[type="submit"]');

            if (password !== confirmPassword) {
                errorDiv.textContent = "Passwords do not match";
                errorDiv.style.display = "block";
                return;
            }

            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="ri-loader-4-line spin"></i> Registering...';
            errorDiv.style.display = "none";

            try {
                const res = await fetch("/api/auth/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password })
                });

                const data = await res.json();
                if (res.ok) {
                    errorDiv.style.color = "var(--success)";
                    errorDiv.style.background = "rgba(46, 204, 113, 0.1)";
                    errorDiv.style.border = "1px solid rgba(46, 204, 113, 0.2)";
                    errorDiv.textContent = "Registration successful! Redirecting to login...";
                    errorDiv.style.display = "block";

                    setTimeout(() => {
                        window.location.href = "/login";
                    }, 1500);
                } else {
                    errorDiv.style.color = "var(--danger)";
                    errorDiv.style.background = "rgba(231, 76, 60, 0.1)";
                    errorDiv.style.border = "1px solid rgba(231, 76, 60, 0.2)";
                    errorDiv.textContent = data.detail || "Registration failed";
                    errorDiv.style.display = "block";
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="ri-user-add-line"></i> Create Account';
                }
            } catch (err) {
                errorDiv.textContent = "Network error occurred";
                errorDiv.style.display = "block";
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="ri-user-add-line"></i> Create Account';
            }
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            logoutBtn.innerHTML = '<i class="ri-loader-4-line spin"></i> Signing Out...';
            try {
                const res = await fetch("/api/auth/logout", { method: "POST" });
                if (res.ok) {
                    window.location.href = "/login";
                }
            } catch (e) {
                console.error("Logout failed", e);
                window.location.href = "/login"; // fallback
            }
        });
    }
});
