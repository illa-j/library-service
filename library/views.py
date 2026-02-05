from decimal import Decimal, ROUND_HALF_UP

import stripe
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Concat
from django.urls import reverse
from django.utils import timezone
from rest_framework import status, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet

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
    BookListSerializer,
    BookDetailSerializer,
    BookCoverImageSerializer,
    BorrowingSerializer,
    BorrowingListSerializer,
    BorrowingDetailSerializer,
    BorrowingReturnSerializer,
    PaymentSerializer,
    PaymentDetailSerializer,
    PaymentRenewSerializer,
)

from django.conf import settings


def create_stripe_checkout_session(payment, request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.checkout.Session.create(
        customer=payment.borrowing.user.stripe_customer_id,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(
                        (payment.amount_to_pay * Decimal("100")).quantize(
                            Decimal("1"), rounding=ROUND_HALF_UP
                        )
                    ),
                    "product_data": {
                        "name": "Book Borrowing Payment",
                    },
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=request.build_absolute_uri(reverse("library:payment-success"))
        + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.build_absolute_uri(reverse("library:payment-cancel"))
        + "?session_id={CHECKOUT_SESSION_ID}",
        metadata={"payment_id": str(payment.id)},
    )


class AuthorViewSet(ModelViewSet):
    serializer_class = AuthorSerializer
    queryset = Author.objects.all()
    permission_classes = (
        IsAuthenticated,
        IsAdminOrReadOnly,
    )

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
    permission_classes = (
        IsAuthenticated,
        IsAdminOrReadOnly,
    )

    def get_queryset(self):
        queryset = self.queryset
        if self.action == "list":
            queryset = queryset.annotate(
                full_name=Concat("author__first_name", Value(" "), "author__last_name")
            )
        elif self.action == "retrieve":
            queryset = queryset.select_related("author")
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return BookListSerializer
        if self.action == "retrieve":
            return BookDetailSerializer
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


class BorrowingViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    serializer_class = BorrowingSerializer
    queryset = Borrowing.objects.select_related("user", "book")
    permission_classes = (IsBorrowerOrReadOnly,)

    def perform_create(self, serializer):
        with transaction.atomic():
            borrowing = serializer.save()

            if borrowing.book.inventory <= 0:
                raise ValidationError("This book is out of stock.")

            borrowing.book.inventory -= 1
            borrowing.book.save()

    def get_serializer_class(self):
        if self.action == "list":
            return BorrowingListSerializer
        if self.action == "retrieve":
            return BorrowingDetailSerializer
        if self.action == "return_book":
            return BorrowingReturnSerializer
        return BorrowingSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset

        if user.is_staff:
            user_id = self.request.query_params.get("user_id")
            if user_id:
                try:
                    user_id = int(user_id)
                except ValueError:
                    raise ValidationError("Invalid user id.")
                queryset = queryset.filter(user_id=user_id)

            is_active = self.request.query_params.get("is_active")
            if is_active is not None:
                if is_active.lower() in ("1", "true"):
                    is_active = True
                elif is_active.lower() in ("0", "false"):
                    is_active = False
                else:
                    raise ValidationError(
                        "Invalid is_active value. Use 1 or 0 / true or false."
                    )
                queryset = queryset.filter(is_active=is_active)

            return queryset
        return queryset.filter(user=user)

    @action(
        detail=True,
        methods=["PATCH"],
        url_path="return",
        permission_classes=(IsAdminUser,),
    )
    def return_book(self, request, pk=None):
        with transaction.atomic():
            borrowing = self.get_object()
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            if not borrowing.is_active:
                return Response(
                    {"detail": "Borrowing is already returned."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            borrowing.actual_return_date = (
                    serializer.validated_data.get("actual_return_date")
                    or timezone.now().date()
            )
            borrowing.is_active = False
            borrowing.save()

            borrowing.book.inventory += 1
            borrowing.book.save()

            payment = Payment.objects.create(
                borrowing=borrowing,
            )
            payment.amount_to_pay = payment.money_to_pay

            checkout_session = create_stripe_checkout_session(payment, request)
            payment.stripe_session_id = checkout_session.id
            payment.stripe_session_url = checkout_session.url
            payment.save()

            return Response(
                {
                    "detail": f"Borrowing {borrowing.id} marked as returned. Payment (id: {payment.id}) created automatically."
                },
                status=status.HTTP_200_OK,
            )


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = PaymentSerializer
    queryset = Payment.objects.select_related("borrowing__user", "borrowing__book")
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PaymentDetailSerializer
        if self.action == "renew_payment":
            return PaymentRenewSerializer
        return PaymentSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset

        if user.is_staff:
            book_title = self.request.query_params.get("book_title")
            if book_title:
                queryset = queryset.filter(borrowing__book__title__icontains=book_title)

            user_email = self.request.query_params.get("user_email")
            if user_email:
                queryset = queryset.filter(borrowing__user__email__icontains=user_email)
        else:
            queryset = queryset.filter(borrowing__user=user)

        return queryset

    def _get_payment_from_request(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return None
        return Payment.objects.filter(stripe_session_id=session_id).first()

    @action(detail=True, methods=["POST"], url_path="renew")
    def renew_payment(self, request, pk=None):
        payment_id = request.data.get("payment_id")

        if not payment_id:
            return Response(
                {"detail": "payment_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if request.user != payment.borrowing.user:
            return Response(
                {"detail": "Access denied. You can renew only your own payments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if payment.status == payment.StatusChoices.PAID:
            return Response(
                {"detail": "Payment already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment.status == payment.StatusChoices.PENDING:
            return Response(
                {"detail": "Payment is pending."}, status=status.HTTP_400_BAD_REQUEST
            )

        checkout_session = create_stripe_checkout_session(payment, request)
        payment.stripe_checkout_session_id = checkout_session.id
        payment.stripe_session_url = checkout_session.url
        payment.save()
        return Response(
            {"detail": "Payment renewed successfully."}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["GET"], url_path="success")
    def success(self, request):
        payment = self._get_payment_from_request(request)
        if not payment:
            return Response(
                {"detail": "Invalid session id."}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"detail": "Book returned successfully, payment received."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["GET"], url_path="cancel")
    def cancel(self, request):
        payment = self._get_payment_from_request(request)
        if not payment:
            return Response(
                {"detail": "Invalid session id."}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"detail": "Payment cancelled."}, status=status.HTTP_200_OK)
