import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
BASE_DIR=Path(__file__).resolve().parents[1]
DEMO_MODE=os.environ.get("DEMO_MODE","1")=="1"
DEBUG=os.environ.get("DJANGO_DEBUG","0")=="1"
SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY","local-demo-only-not-for-deployment")
if not DEMO_MODE and SECRET_KEY=="local-demo-only-not-for-deployment":
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY before deploying.")
ALLOWED_HOSTS=os.environ.get("DJANGO_ALLOWED_HOSTS","localhost,127.0.0.1,testserver,*,onrender.com,.onrender.com").split(",")
INSTALLED_APPS=["django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","corsheaders","rest_framework","core"]
MIDDLEWARE=["django.middleware.security.SecurityMiddleware","corsheaders.middleware.CorsMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF="ascension.urls"
WSGI_APPLICATION="ascension.wsgi.application"
if os.environ.get("DATABASE_URL"):
    import urllib.parse
    u=urllib.parse.urlparse(os.environ["DATABASE_URL"])
    DATABASES={"default":{"ENGINE":"django.db.backends.postgresql","NAME":u.path.lstrip("/"),
      "USER":u.username,"PASSWORD":urllib.parse.unquote(u.password) if u.password else "",
      "HOST":u.hostname,"PORT":u.port or 5432,"OPTIONS":{"sslmode":os.environ.get("POSTGRES_SSLMODE","require")}}}
elif os.environ.get("POSTGRES_HOST"):
    DATABASES={"default":{"ENGINE":"django.db.backends.postgresql","NAME":os.environ.get("POSTGRES_DB","ascension"),
      "USER":os.environ.get("POSTGRES_USER","ascension"),"PASSWORD":os.environ["POSTGRES_PASSWORD"],
      "HOST":os.environ["POSTGRES_HOST"],"PORT":os.environ.get("POSTGRES_PORT","5432"),
      "OPTIONS":{"sslmode":os.environ.get("POSTGRES_SSLMODE","require")}}}
else:
    if not DEMO_MODE: raise ImproperlyConfigured("PostgreSQL is required outside local demo mode.")
    DATABASES={"default":{"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"db.sqlite3","OPTIONS":{"timeout":30}}}
TIME_ZONE="Asia/Kolkata"
USE_TZ=True
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
CORS_ALLOW_ALL_ORIGINS=True
_raw_cors=os.environ.get("CORS_ALLOWED_ORIGINS","http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:5785,http://127.0.0.1:5785,http://localhost:9000,http://127.0.0.1:9000")
CORS_ALLOWED_ORIGINS=[o.strip().rstrip("/") for o in _raw_cors.split(",") if o.strip()]
REST_FRAMEWORK={"DEFAULT_PERMISSION_CLASSES":["core.permissions.LocalDemoOrAuthenticated"],
                "DEFAULT_AUTHENTICATION_CLASSES":["rest_framework.authentication.SessionAuthentication"],
                "DEFAULT_PARSER_CLASSES":["rest_framework.parsers.JSONParser","rest_framework.parsers.MultiPartParser","rest_framework.parsers.FormParser"],
                "DEFAULT_THROTTLE_CLASSES":["rest_framework.throttling.AnonRateThrottle","rest_framework.throttling.UserRateThrottle"],
                "DEFAULT_THROTTLE_RATES":{"anon":"120/min","user":"300/min"}}
DATA_UPLOAD_MAX_MEMORY_SIZE=5*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE=5*1024*1024
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SECURE=not DEMO_MODE
CSRF_COOKIE_SECURE=not DEMO_MODE
SECURE_SSL_REDIRECT=not DEMO_MODE
SECURE_HSTS_SECONDS=31536000 if not DEMO_MODE else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS=not DEMO_MODE
SECURE_HSTS_PRELOAD=not DEMO_MODE

CORS_ALLOW_CREDENTIALS=True
