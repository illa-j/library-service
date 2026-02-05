import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import (
    EmailVerificationToken,
    PasswordChangeToken
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "email", "password", "is_staff")
        read_only_fields = ("is_staff",)
        extra_kwargs = {
            "password": {
                "write_only": True,
                "min_length": 5,
                "style": {
                    "input_type": "password"
                }
            }
        }

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data, is_active=False)


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "first_name",
            "last_name",
            "email",
            "is_staff"
            )
        read_only_fields = ("id", "is_staff",)

class TokenBlacklistSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate_refresh_token(self, value):
        try:
            self.token = RefreshToken(value)
        except Exception:
            raise serializers.ValidationError("Invalid refresh token")

    def save(self, **kwargs):
        if self.token:
            try:
                self.token.blacklist()
            except Exception:
                pass


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.UUIDField()

    def validate_token(self, value):
        try:
            token_obj = EmailVerificationToken.objects.get(token=value)
        except EmailVerificationToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token")

        if token_obj.is_expired():
            raise serializers.ValidationError("Token has expired")

        self.token_obj = token_obj
        return value

    def save(self):
        user = self.token_obj.user
        user.is_active = True
        stripe.api_key = settings.STRIPE_SECRET_KEY
        customer = stripe.Customer.create(
            email=user.email,
            name=user.username
        )
        user.stripe_customer_id = customer.id
        user.save(update_fields=["stripe_customer_id", "is_active"])
        self.token_obj.delete()
        return user


class PasswordChangeSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        min_length=5,
        style={"input_type": "password"},
        validators=[validate_password]
    )


class ConfirmPasswordChangeSerializer(serializers.Serializer):
    token = serializers.UUIDField()

    def validate_token(self, value):
        try:
            token_obj = PasswordChangeToken.objects.get(token=value)
        except PasswordChangeToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token")

        if token_obj.is_expired():
            raise serializers.ValidationError("Token has expired")

        self.token_obj = token_obj
        return value

    def save(self):
        user = self.token_obj.user
        user.password = self.token_obj.password_hash
        user.save(update_fields=["password"])

        self.token_obj.delete()
        return user
