# default source as self
CSP_DEFAULT_SRC = ("'self'", )

# style
CSP_STYLE_SRC = ("'self'",)

# scripts from our domain and other domains
CSP_SCRIPT_SRC = ("'self'",)

# images from our domain and other domains
CSP_IMG_SRC = ("'self'",)

# loading manifest, workers, frames, etc
CSP_FONT_SRC = ("'self'", )
CSP_CONNECT_SRC = ("'self'",)
CSP_OBJECT_SRC = ("'self'", )
CSP_BASE_URI = ("'self'", )
CSP_FRAME_ANCESTORS = ("'self'", )
CSP_FORM_ACTION = ("'self'", )
CSP_INCLUDE_NONCE_IN = ('script-src', )
CSP_MANIFEST_SRC = ("'self'", )
CSP_WORKER_SRC = ("'self'", )
CSP_MEDIA_SRC = ("'self'", )

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_SSL_REDIRECT = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 60
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True