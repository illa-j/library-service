from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from library.models import (
    Author,
    Book,
    Borrowing,
    Payment
)
from library.permissions import (
    IsAdminOrReadOnly,
    IsBorrowerOrReadOnly,
)
from library.serializers import (
    AuthorSerializer,
    AuthorPhotoSerializer,
    BookSerializer,
    BookCoverImageSerializer,
    BorrowingSerializer,
    BorrowingReturnSerializer,
)


class AuthorViewSet(ModelViewSet):
    serializer_class = AuthorSerializer
    queryset = Author.objects.all()
    permission_classes = (IsAuthenticated, IsAdminOrReadOnly,)

    def get_serializer_class(self):
        if self.action == "upload_photo":
            return AuthorPhotoSerializer
        return AuthorSerializer

    @action(
        methods=["POST"],
        detail=True,
        url_path="upload-photo",
    )
    def upload_photo(self, request, pk=None):
        author = self.get_object()
        serializer = self.get_serializer(author, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookViewSet(ModelViewSet):
    serializer_class = BookSerializer
    queryset = Book.objects.all()
    permission_classes = (IsAuthenticated, IsAdminOrReadOnly,)

    def get_serializer_class(self):
        if self.action == "upload_cover_image":
            return BookCoverImageSerializer
        return BookSerializer

    @action(
        methods=["POST"],
        detail=True,
        url_path="upload-cover-image",
    )
    def upload_cover_image(self, request, pk=None):
        author = self.get_object()
        serializer = self.get_serializer(author, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BorrowingViewSet(ModelViewSet):
    serializer_class = BorrowingSerializer
    queryset = Borrowing.objects.all()
    permission_classes = (IsBorrowerOrReadOnly,)

    def perform_create(self, serializer):
        with transaction.atomic():
            borrowing = serializer.save()

            if borrowing.book.inventory <= 0:
                raise ValidationError("This book is out of stock.")

            borrowing.book.inventory -= 1
            borrowing.book.save()

    def get_serializer_class(self):
        if self.action == "return_book":
            return BorrowingReturnSerializer
        return BorrowingSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Borrowing.objects.all()
        return Borrowing.objects.filter(user=user)

    @action(
        detail=True,
        methods=["PATCH"],
        url_path="return",
        permission_classes=(IsAdminUser,)
    )
    def return_book(self, request, pk=None):
        with transaction.atomic():
            borrowing = self.get_object()
            actual_return_date = request.data.get("actual_return_date")

            if not borrowing.is_active:
                return Response(
                    {"detail": "Borrowing is already returned."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not actual_return_date:
                borrowing.actual_return_date = timezone.now().date()
            else:
                try:
                    borrowing.actual_return_date = timezone.datetime.fromisoformat(actual_return_date).date()
                except ValueError:
                    return Response(
                        {"detail": "Invalid date format. Use ISO format."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            borrowing.is_active = False
            borrowing.save()

            borrowing.book.inventory += 1
            borrowing.book.save()

            payment = Payment.objects.create(
                borrowing=borrowing,
            )
            payment.amount_paid = payment.money_to_pay
            payment.save()

            return Response(
                {
                    "detail": f"Borrowing {borrowing.id} marked as returned. Payment (id: {payment.id}) created automatically."
                },
                status=status.HTTP_200_OK
            )
