from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from library.models import Author, Book, Borrowing, Payment
from users.serializers import UserDetailSerializer


class AuthorSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        date_of_death = attrs.get("date_of_death", None)
        date_of_birth = attrs.get("date_of_birth", None)
        if date_of_death and date_of_birth:
            Author.validate_dates_of_birth_and_death(
                date_of_birth, date_of_death, ValidationError
            )
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
        read_only_fields = ("id", "photo")


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


class BookListSerializer(BookSerializer):
    author = serializers.CharField(source="full_name", read_only=True)


class BookDetailSerializer(BookSerializer):
    author = AuthorSerializer(many=False, read_only=True)


class BookCoverImageSerializer(AuthorSerializer):
    class Meta:
        model = Book
        fields = ("id", "cover_image")


class BorrowingSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        borrow_date = (
            self.instance.borrow_date if self.instance else timezone.now().date()
        )
        Borrowing.validate_expected_and_actual_date_after_borrowed(
            error_to_raise=ValidationError,
            borrowed_date=borrow_date,
            expected_return_date=attrs.get("expected_return_date", None),
            actual_return_date=attrs.get("actual_return_date", None),
        )
        return attrs

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "book",
            "user",
            "is_active",
        )
        read_only_fields = (
            "id",
            "actual_return_date",
            "is_active",
        )


class BorrowingListSerializer(BorrowingSerializer):
    book = serializers.SlugRelatedField(slug_field="title", many=False, read_only=True)
    user = serializers.SlugRelatedField(slug_field="email", many=False, read_only=True)


class BorrowingDetailSerializer(BorrowingSerializer):
    user = UserDetailSerializer(many=False, read_only=True)
    book = BookSerializer(many=False, read_only=True)


class BorrowingReturnSerializer(BorrowingSerializer):
    actual_return_date = serializers.DateField(
        required=False, allow_null=True, input_formats=["%Y-%m-%d", "%d-%m-%Y"]
    )

    class Meta:
        model = Borrowing
        fields = ("actual_return_date",)


class PaymentSerializer(serializers.ModelSerializer):
    borrowing_book_title = serializers.CharField(
        source="borrowing.book.title", read_only=True
    )
    borrowing_user_email = serializers.CharField(
        source="borrowing.user.email", read_only=True
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "status",
            "type",
            "borrowing_book_title",
            "borrowing_user_email",
            "stripe_session_url",
            "stripe_session_id",
            "amount_to_pay",
        )
        read_only_fields = (
            "id",
            "status",
            "type",
            "borrowing_book_title",
            "borrowing_user_email",
            "amount_to_pay",
        )


class PaymentDetailSerializer(serializers.ModelSerializer):
    borrowing = BorrowingDetailSerializer(many=False, read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "status",
            "type",
            "borrowing",
            "stripe_session_url",
            "stripe_session_id",
            "amount_to_pay",
        )
        read_only_fields = (
            "id",
            "status",
            "type",
            "borrowing",
            "stripe_session_url",
            "stripe_session_id",
            "amount_to_pay",
        )


class PaymentRenewSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
