from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from library.models import Author


class AuthorSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        date_of_death = attrs.get("date_of_death", None)
        date_of_birth = attrs.get("date_of_birth", None)
        if date_of_death and date_of_birth:
            Author.validate_dates_of_birth_and_death(date_of_birth, date_of_death, ValidationError)
        return attrs

    class Meta:
        model = Author
        fields = (
            "id",
            "photo",
            "first_name",
            "last_name",
            "biography",
            "date_of_birth",
            "date_of_death",
            "country",
            "wikipedia",
            "created_at",
        )
        read_only_fields = (
            "id",
            "photo",
            "created_at",
        )


class AuthorPhotoSerializer(AuthorSerializer):
    class Meta:
        model = Author
        fields = ("id", "photo")
