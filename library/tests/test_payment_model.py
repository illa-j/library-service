from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from library.models import Author, Book, Borrowing, Payment


class PaymentModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="payer@test.com",
            password="testpass123",
        )
        self.author = Author.objects.create(first_name="Neil", last_name="Gaiman")
        self.book = Book.objects.create(
            title="Coraline",
            author=self.author,
            inventory=1,
            daily_fee="1.00",
        )

    def test_money_to_pay_calculation(self):
        today = timezone.now().date()
        borrowing = Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=today + timedelta(days=1),
            actual_return_date=today + timedelta(days=3),
            is_active=False,
        )
        payment = Payment.objects.create(borrowing=borrowing)

        self.assertEqual(payment.money_to_pay, Decimal("6.00"))

    def test_payment_type_fine_when_overdue(self):
        today = timezone.now().date()
        borrowing = Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=today + timedelta(days=1),
            actual_return_date=today + timedelta(days=3),
            is_active=False,
        )
        payment = Payment.objects.create(borrowing=borrowing)

        self.assertEqual(payment.type, Payment.TypeChoices.FINE)

    def test_payment_type_payment_when_not_overdue(self):
        today = timezone.now().date()
        borrowing = Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=today + timedelta(days=3),
            actual_return_date=today + timedelta(days=3),
            is_active=False,
        )
        payment = Payment.objects.create(borrowing=borrowing)

        self.assertEqual(payment.type, Payment.TypeChoices.PAYMENT)
