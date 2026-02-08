from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from library.models import Author, Book, Borrowing, Payment
from library.serializers import PaymentDetailSerializer, PaymentSerializer

PAYMENT_URL = reverse("library:payment-list")
PAYMENT_RENEW_URL = reverse("library:payment-renew")
PAYMENT_SUCCESS_URL = reverse("library:payment-success")
PAYMENT_CANCEL_URL = reverse("library:payment-cancel")


def detail_url(payment_id):
    return reverse("library:payment-detail", args=[payment_id])


def sample_author(**params):
    defaults = {"first_name": "Kazuo", "last_name": "Ishiguro"}
    defaults.update(params)
    return Author.objects.create(**defaults)


def sample_book(**params):
    defaults = {
        "title": "Never Let Me Go",
        "inventory": 1,
        "daily_fee": "1.00",
    }
    defaults.update(params)
    return Book.objects.create(**defaults)


def sample_borrowing(**params):
    defaults = {
        "expected_return_date": timezone.now().date() + timedelta(days=7),
        "actual_return_date": timezone.now().date() + timedelta(days=7),
        "is_active": False,
    }
    defaults.update(params)
    return Borrowing.objects.create(**defaults)


def sample_payment(**params):
    defaults = {
        "status": Payment.StatusChoices.PENDING,
        "stripe_session_id": "cs_test_123",
        "stripe_session_url": "https://stripe.test/checkout",
    }
    defaults.update(params)
    payment = Payment.objects.create(**defaults)
    payment.amount_to_pay = payment.money_to_pay
    payment.save()
    return payment


class UnauthenticatedPaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(PAYMENT_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedPaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="user@test.com",
            password="testpass123",
        )
        self.other_user = get_user_model().objects.create_user(
            email="other@test.com",
            password="testpass123",
        )
        self.client.force_authenticate(self.user)

    def test_list_payments_limited_to_user(self):
        author = sample_author()
        book = sample_book(author=author)
        borrowing = sample_borrowing(user=self.user, book=book)
        payment = sample_payment(borrowing=borrowing)

        other_borrowing = sample_borrowing(user=self.other_user, book=book)
        sample_payment(borrowing=other_borrowing, stripe_session_id="cs_test_456")

        res = self.client.get(PAYMENT_URL)

        serializer = PaymentSerializer([payment], many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], serializer.data)

    def test_retrieve_payment_detail(self):
        author = sample_author()
        book = sample_book(author=author)
        borrowing = sample_borrowing(user=self.user, book=book)
        payment = sample_payment(borrowing=borrowing)

        res = self.client.get(detail_url(payment.id))

        serializer = PaymentDetailSerializer(payment)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_renew_payment_requires_id(self):
        res = self.client.post(PAYMENT_RENEW_URL, {})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("library.views.create_stripe_checkout_session")
    @patch("stripe.checkout.Session.retrieve")
    def test_renew_payment_expired_session(self, mock_retrieve, mock_create):
        author = sample_author()
        book = sample_book(author=author)
        borrowing = sample_borrowing(user=self.user, book=book)
        payment = sample_payment(borrowing=borrowing)
        mock_retrieve.return_value = SimpleNamespace(status="expired")
        mock_create.return_value = SimpleNamespace(
            id="cs_test_999",
            url="https://stripe.test/renewed",
        )

        res = self.client.post(PAYMENT_RENEW_URL, {"payment_id": payment.id})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.stripe_session_id, "cs_test_999")
        self.assertEqual(payment.stripe_session_url, "https://stripe.test/renewed")

    def test_success_endpoint_invalid_session(self):
        res = self.client.get(PAYMENT_SUCCESS_URL, {"session_id": "missing"})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_endpoint_invalid_session(self):
        res = self.client.get(PAYMENT_CANCEL_URL, {"session_id": "missing"})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_success_endpoint_valid_session(self):
        author = sample_author()
        book = sample_book(author=author)
        borrowing = sample_borrowing(user=self.user, book=book)
        payment = sample_payment(borrowing=borrowing)

        res = self.client.get(PAYMENT_SUCCESS_URL, {"session_id": payment.stripe_session_id})

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_cancel_endpoint_valid_session(self):
        author = sample_author()
        book = sample_book(author=author)
        borrowing = sample_borrowing(user=self.user, book=book)
        payment = sample_payment(borrowing=borrowing)

        res = self.client.get(PAYMENT_CANCEL_URL, {"session_id": payment.stripe_session_id})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
