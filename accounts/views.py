"""
accounts/views.py
Token-based auth: login → token, logout → delete token.
Includes one-liner DB health-check endpoint.
"""

from django.contrib.auth import authenticate
from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .serializers import UserSerializer


# ── DB health-check ────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """One-liner PostgreSQL verification — SELECT 1."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ok", "db": "connected"})
    except Exception as e:
        return Response({"status": "error", "db": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ── Auth endpoints ─────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """
    POST /api/auth/login/
    Body: { username, password }
    Returns: { token, user: { id, username, role, ... } }
    """
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(username=username, password=password)
    if not user:
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": UserSerializer(user).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """DELETE the user's token — effectively logging them out."""
    request.user.auth_token.delete()
    return Response({"detail": "Logged out."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    """GET /api/auth/me/ — returns the logged-in user's profile."""
    return Response(UserSerializer(request.user).data)
