"""
API аутентификации: вход по логину/паролю, данные текущего пользователя.
"""
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class LoginAPIView(APIView):
    """
    Вход по логину и паролю. Возвращает токен и данные пользователя.
    POST /api/auth/login/
    Body: { "username": "...", "password": "..." }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username") or request.data.get("email", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"error": "Укажите username и password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"error": "Неверный логин или пароль."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "Учётная запись отключена."},
                status=status.HTTP_403_FORBIDDEN,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user": {
                "id": user.pk,
                "username": user.username,
                "is_staff": user.is_staff,
            },
        })


class CurrentUserAPIView(APIView):
    """
    Данные текущего пользователя (по заголовку Authorization: Token ...).
    GET /api/auth/me/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.pk,
            "username": user.username,
            "is_staff": user.is_staff,
        })
