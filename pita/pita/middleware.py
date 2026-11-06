class SecurityHeadersMiddleware:
    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https://lh3.googleusercontent.com https://*.googleusercontent.com https://res.cloudinary.com; "
        "frame-src 'self' blob: data:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self';"
    )
    PERMISSIONS_POLICY = "geolocation=(), microphone=(), camera=(), payment=()"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.CSP)
        response.setdefault("Permissions-Policy", self.PERMISSIONS_POLICY)
        return response
