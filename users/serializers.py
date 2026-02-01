from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken


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
        return get_user_model().objects.create_user(**validated_data)


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
