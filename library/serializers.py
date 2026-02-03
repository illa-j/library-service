from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from library.models import (
    Author,
    Book,
    Borrowing
)


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
            "photo"
        )


class AuthorPhotoSerializer(AuthorSerializer):
    class Meta:
        model = Author
        fields = ("id", "photo")


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = (
            "id",
            "cover_image",
            "title",
            "author",
            "cover",
            "inventory",
            "daily_fee",
            "created_at",
        )
        read_only_fields = (
            "id",
            "cover_image",
            "created_at",
        )


class BookCoverImageSerializer(AuthorSerializer):
    class Meta:
        model = Book
        fields = ("id", "cover_image")


class BorrowingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "book",
            "user"
        )
        read_only_fields = (
            "id",
            "actual_return_date",
        )


class BorrowingReturnSerializer(serializers.ModelSerializer):
    class Meta:
        model = Borrowing
        fields = (
            "id",
            "actual_return_date",
        )
        read_only_fields = (
            "id",
        )
