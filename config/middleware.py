"""
Middleware d'en-têtes de sécurité HTTP pour Arrera Project.

Ajoute une Content-Security-Policy et quelques en-têtes de durcissement à
toutes les réponses. La CSP restreint les origines de scripts/styles aux seuls
CDN utilisés et bloque les plugins, l'encadrement (clickjacking) et le
détournement de <base>.
"""

CSP_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com",
    "font-src 'self' https://fonts.gstatic.com https://unpkg.com data:",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Content-Security-Policy', CSP_POLICY)
        response.setdefault('Referrer-Policy', 'same-origin')
        response.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=(), payment=()',
        )
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        return response
