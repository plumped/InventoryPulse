from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication class that bypasses CSRF validation.
    This is useful for testing or when you have other CSRF protection mechanisms.
    For production, ensure proper security measures are in place.
    """
    def enforce_csrf(self, request):
        return  # Do not enforce CSRF