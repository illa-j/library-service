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
from library.serializers import BorrowingListSerializer

BORROWING_URL = reverse("library:borrowing-list")


def detail_url(borrowing_id):
    return reverse("library:borrowing-detail", args=[borrowing_id])


def return_url(borrowing_id):
    return reverse("library:borrowing-return", args=[borrowing_id])


def sample_author(**params):
    defaults = {"first_name": "Octavia", "last_name": "Butler"}
    defaults.update(params)
    return Author.objects.create(**defaults)


def sample_book(**params):
    defaults = {
        "title": "Kindred",
        "inventory": 2,
        "daily_fee": "1.00",
    }
    defaults.update(params)
    return Book.objects.create(**defaults)


def sample_borrowing(**params):
    defaults = {
        "expected_return_date": timezone.now().date() + timedelta(days=7),
    }
    defaults.update(params)
    return Borrowing.objects.create(**defaults)


class UnauthenticatedBorrowingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(BORROWING_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedBorrowingApiTests(TestCase):
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

    def test_list_borrowings_limited_to_user(self):
        author = sample_author()
        book = sample_book(author=author)
        borrowing = sample_borrowing(user=self.user, book=book)
        sample_borrowing(user=self.other_user, book=book)

        res = self.client.get(BORROWING_URL)

        serializer = BorrowingListSerializer([borrowing], many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], serializer.data)

    def test_create_borrowing_forbidden(self):
        author = sample_author()
        book = sample_book(author=author)
        payload = {
            "book": book.id,
            "user": self.user.id,
            "expected_return_date": (timezone.now().date() + timedelta(days=5)).isoformat(),
        }

        res = self.client.post(BORROWING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AdminBorrowingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_user(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.user = get_user_model().objects.create_user(
            email="user@test.com",
            password="testpass123",
        )
        self.client.force_authenticate(self.admin)

    def test_list_borrowings_filter_by_user_id(self):
        author = sample_author()
        book = sample_book(author=author)
        borrowing = sample_borrowing(user=self.user, book=book)
        other_user = get_user_model().objects.create_user(
            email="other@test.com",
            password="testpass123",
        )
        sample_borrowing(user=other_user, book=book)

        res = self.client.get(BORROWING_URL, {"user_id": self.user.id})

        serializer = BorrowingListSerializer([borrowing], many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], serializer.data)

    def test_create_borrowing_decrements_inventory(self):
        author = sample_author()
        book = sample_book(author=author, inventory=2)
        payload = {
            "book": book.id,
            "user": self.user.id,
            "expected_return_date": (timezone.now().date() + timedelta(days=5)).isoformat(),
        }

        res = self.client.post(BORROWING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        book.refresh_from_db()
        self.assertEqual(book.inventory, 1)

    def test_create_borrowing_out_of_stock(self):
        author = sample_author()
        book = sample_book(author=author, inventory=0)
        payload = {
            "book": book.id,
            "user": self.user.id,
            "expected_return_date": (timezone.now().date() + timedelta(days=5)).isoformat(),
        }

        res = self.client.post(BORROWING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("library.views.create_stripe_checkout_session")
    def test_return_borrowing_creates_payment(self, mock_checkout):
        author = sample_author()
        book = sample_book(author=author, inventory=1)
        borrowing = sample_borrowing(user=self.user, book=book)
        mock_checkout.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://stripe.test/checkout",
        )

        res = self.client.patch(return_url(borrowing.id), {})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        borrowing.refresh_from_db()
        book.refresh_from_db()
        self.assertFalse(borrowing.is_active)
        self.assertIsNotNone(borrowing.actual_return_date)
        self.assertEqual(book.inventory, 2)
        payment = Payment.objects.get(borrowing=borrowing)
        self.assertEqual(payment.stripe_session_id, "cs_test_123")
        self.assertEqual(payment.stripe_session_url, "https://stripe.test/checkout")
