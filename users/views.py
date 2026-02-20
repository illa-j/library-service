from datetime import timedelta
import traceback

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from rest_framework import generics, serializers, status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework.exceptions import ValidationError
from users.models import EmailVerificationToken, PasswordChangeToken, TelegramToken
from users.serializers import (
    GoogleAuthSerializer,
    GoogleTokenSerializer,
    UserSerializer,
    TokenBlacklistSerializer,
    VerifyEmailSerializer,
    PasswordChangeSerializer,
    ConfirmPasswordChangeSerializer,
    UserDetailSerializer,
    TelegramTokenSerializer,
)
from users.tasks import send_verification_email, send_password_change_confirmation_email
from users.utils import GoogleOAuthHandler, get_or_create_google_user


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


class GoogleAuthURLView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        summary="Get Google OAuth authorization URL",
        responses={
            200: inline_serializer(
                name="GoogleAuthURLResponse",
                fields={
                    "authorization_url": serializers.URLField(),
                    "state": serializers.CharField(),
                },
            )
        },
    )
    def get(self, request):
        handler = GoogleOAuthHandler()
        auth_url, state = handler.get_authorization_url()

        request.session["oauth_state"] = state

        return Response({"authorization_url": auth_url, "state": state})


class GoogleAuthView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = GoogleAuthSerializer

    @extend_schema(summary="Authenticate with Google OAuth authorization code")
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]

        try:
            handler = GoogleOAuthHandler()
            google_data = handler.exchange_code_for_tokens(code)

            user, created = get_or_create_google_user(google_data)

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "is_active": user.is_active,
                    },
                    "created": created,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": "Failed to authenticate with Google", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class GoogleAuthCallbackView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        summary="Google OAuth callback (exchange code for JWT tokens)",
        parameters=[
            OpenApiParameter(
                name="code",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
            ),
            OpenApiParameter(
                name="state",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
            ),
            OpenApiParameter(
                name="error",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
            ),
        ],
        responses={
            200: inline_serializer(
                name="GoogleAuthCallbackResponse",
                fields={
                    "access_token": serializers.CharField(),
                    "refresh_token": serializers.CharField(),
                    "user": inline_serializer(
                        name="GoogleAuthCallbackUser",
                        fields={
                            "id": serializers.CharField(),
                            "email": serializers.EmailField(),
                            "first_name": serializers.CharField(),
                            "last_name": serializers.CharField(),
                            "is_active": serializers.BooleanField(),
                            "created": serializers.BooleanField(),
                        },
                    ),
                },
            )
        },
    )
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        error = request.GET.get("error")

        if error:
            raise ValidationError(f"Google authentication error: {error}")

        if not code:
            raise ValidationError("Authorization code not provided by Google")

        stored_state = request.session.get("oauth_state")
        if stored_state and state != stored_state:
            raise ValidationError("Invalid state parameter in Google callback")

        handler = GoogleOAuthHandler()
        google_data = handler.exchange_code_for_tokens(code)
        user, created = get_or_create_google_user(google_data)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        return Response(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_active": user.is_active,
                    "created": created,
                },
            },
            status=status.HTTP_200_OK,
        )


class GoogleTokenAuthView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = GoogleTokenSerializer

    @extend_schema(summary="Authenticate with Google ID token")
    def post(self, request):
        serializer = GoogleTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]

        try:
            handler = GoogleOAuthHandler()
            google_data = handler.verify_google_token(token)

            if not google_data:
                return Response(
                    {"error": "Invalid Google token"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user, created = get_or_create_google_user(google_data)

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "is_active": user.is_active,
                    },
                    "created": created,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": "Failed to authenticate with Google", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class TokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"


class TokenVerifyView(TokenVerifyView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_verification"
