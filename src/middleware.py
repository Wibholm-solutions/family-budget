"""Middleware for Family Budget."""

import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting for login attempts."""

    def __init__(self, app, max_attempts: int = 5, window_seconds: int = 300):
        super().__init__(app)
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Only rate limit login POST requests
        if request.url.path == "/budget/login" and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()

            # Clean old attempts for this IP
            self.attempts[client_ip] = [
                t for t in self.attempts[client_ip]
                if now - t < self.window_seconds
            ]

            # Remove IP key entirely if no recent attempts (prevents memory leak)
            if not self.attempts[client_ip]:
                del self.attempts[client_ip]
            else:
                # Check if rate limited
                if len(self.attempts[client_ip]) >= self.max_attempts:
                    return HTMLResponse(
                        content="For mange login forsøg. Prøv igen om 5 minutter.",
                        status_code=429
                    )

            # Record this attempt
            self.attempts[client_ip].append(now)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self';"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
