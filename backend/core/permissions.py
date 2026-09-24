from django.conf import settings
from rest_framework.permissions import BasePermission
class LocalDemoOrAuthenticated(BasePermission):
    def has_permission(self,request,view):
        origin=request.META.get("HTTP_ORIGIN")
        if not getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False):
            if request.method not in ("GET","HEAD","OPTIONS") and origin and origin not in settings.CORS_ALLOWED_ORIGINS:
                return False
        if request.user and request.user.is_authenticated:
            return request.method in ("GET","HEAD","OPTIONS") or request.user.groups.filter(name="HSE").exists() or request.user.is_staff
        return bool(settings.DEMO_MODE) or request.META.get("REMOTE_ADDR") in ("127.0.0.1","::1")
