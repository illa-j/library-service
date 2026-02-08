from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from library.models import Author, Book, Borrowing


class BorrowingModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="borrower@test.com",
            password="testpass123",
        )
        self.author = Author.objects.create(first_name="Mary", last_name="Shelley")
        self.book = Book.objects.create(
            title="Frankenstein",
            author=self.author,
            inventory=1,
            daily_fee="2.00",
        )

    def test_borrowing_str(self):
        borrowing = Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=timezone.now().date() + timedelta(days=7),
        )

        self.assertIn("Borrow date:", str(borrowing))
        self.assertIn("Expected return date:", str(borrowing))
        self.assertIn("Book: Frankenstein", str(borrowing))

    def test_expected_return_date_before_borrow_date_invalid(self):
        with self.assertRaises(ValidationError):
            Borrowing.objects.create(
                user=self.user,
                book=self.book,
                expected_return_date=timezone.now().date() - timedelta(days=1),
            )
