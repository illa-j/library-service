from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from users.models import EmailVerificationToken, PasswordChangeToken, TelegramToken
from users.serializers import (
    UserSerializer,
    TokenBlacklistSerializer,
    VerifyEmailSerializer,
    PasswordChangeSerializer,
    ConfirmPasswordChangeSerializer,
    UserDetailSerializer,
    TelegramTokenSerializer,
)
from users.tasks import send_verification_email, send_password_change_confirmation_email


@extend_schema_view(
    post=extend_schema(summary="Register user and send verification email")
)
class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                "message": "verification email sent.",
                "user": serializer.data,
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        user = serializer.save()

        token = EmailVerificationToken.objects.create(user=user)

        verify_link = (
            self.request.build_absolute_uri(reverse("users:verify_email"))
            + f"?token={token.token}"
        )

        transaction.on_commit(
            lambda: send_verification_email.apply_async(args=(verify_link, user.email))
        )


@extend_schema_view(
    post=extend_schema(summary="Request password change (sends confirmation email)")
)
class PasswordChangeView(CreateAPIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    serializer_class = PasswordChangeSerializer
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        user = self.request.user

        serializer.is_valid(raise_exception=True)

        token = PasswordChangeToken.objects.create(
            user=user,
            password_hash=make_password(serializer.validated_data["password"]),
        )

        confirm_link = (
            self.request.build_absolute_uri(reverse("users:confirm_password_change"))
            + f"?token={token.token}"
        )

        transaction.on_commit(
            lambda: send_password_change_confirmation_email.apply_async(
                args=(confirm_link, user.email)
            )
        )

        return Response(
            {"message": "confirmation email sent."}, status=status.HTTP_200_OK
        )


@extend_schema_view(
    get=extend_schema(summary="Confirm password change by token")
)
class ConfirmPasswordChangeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_verification"

    def get(self, request):
        serializer = ConfirmPasswordChangeSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(
            {"detail": "Password changed successfully"}, status=status.HTTP_200_OK
        )


@extend_schema_view(
    get=extend_schema(summary="Verify email by token")
)
class VerifyEmailAPIView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_verification"

    def get(self, request):
        serializer = VerifyEmailSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(
            {"detail": "Email verified successfully"}, status=status.HTTP_200_OK
        )


@extend_schema_view(
    post=extend_schema(summary="Logout and blacklist refresh token")
)
class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TokenBlacklistSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Successfully logged out."}, status=status.HTTP_200_OK
        )


@extend_schema_view(
    get=extend_schema(summary="Get current user profile"),
    patch=extend_schema(summary="Update current user profile"),
)
class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = (IsAuthenticated,)
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


@extend_schema_view(
    get=extend_schema(summary="Get or create a Telegram linking token")
)
class TelegramTokenAPIView(APIView):
    serializer_class = TelegramTokenSerializer
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        telegram_token = TelegramToken.objects.filter(user=request.user).first()
        if telegram_token:
            serializer = TelegramTokenSerializer(telegram_token)
            if (
                telegram_token.created_at
                + timedelta(minutes=settings.TELEGRAM_TOKEN_LIFETIME_MINUTES)
            ) > timezone.now():
                return Response(serializer.data, status=status.HTTP_200_OK)
            telegram_token.delete()

        telegram_token = TelegramToken.objects.create(user=request.user)
        serializer = TelegramTokenSerializer(telegram_token)
        return Response(serializer, status=status.HTTP_200_OK)


class TokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class TokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"


class TokenVerifyView(TokenVerifyView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_verification"
