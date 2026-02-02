from django.contrib.auth import get_user_model
from django.db import models
from decimal import Decimal


USER = get_user_model()


class Author(models.Model):
    pseudonym = models.CharField(max_length=100, unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)


class Book(models.Model):
    class CoverChoices(models.TextChoices):
        HARD = "hard", "Hard"
        SOFT = "soft", "Soft"
    title = models.CharField(max_length=100, unique=True)
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name="books"
    )
    cover = models.CharField(
        max_length=10,
        choices=CoverChoices.choices,
        default=CoverChoices.SOFT
    )
    inventory = models.PositiveIntegerField(default=0)
    daily_fee = models.DecimalField(max_digits=10, decimal_places=2)


class Borrowing(models.Model):
    borrow_date = models.DateField(auto_now_add=True)
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(blank=True, null=True)
    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name="borrowings"
    )
    user = models.ForeignKey(
        USER,
        on_delete=models.CASCADE,
        related_name="borrowings"
    )
    is_active = models.BooleanField(default=True)


class Payment(models.Model):
    class StatusChoices(models.TextChoices):
        PAID = "paid", "Paid"
        PENDING = "pending", "Pending"

    class TypeChoices(models.TextChoices):
        PAYMENT = "payment", "Payment"
        FINE = "fine", "Fine"

    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    type = models.CharField(
        max_length=10,
        choices=TypeChoices.choices,
        default=TypeChoices.PAYMENT
    )
    borrowing = models.ForeignKey(
        Borrowing,
        on_delete=models.PROTECT,
        related_name="payments"
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    @property
    def money_to_pay(self) -> Decimal:
        borrowing = self.borrowing

        borrow_date = borrowing.borrow_date
        actual_return_date = borrowing.actual_return_date
        expected_return_date = borrowing.expected_return_date
        daily_fee = borrowing.book.daily_fee

        total_days = max((actual_return_date - borrow_date).days, 1)

        overdue_days = max((actual_return_date - expected_return_date).days, 0)

        base_amount = Decimal(total_days) * daily_fee
        overdue_amount = Decimal(overdue_days) * daily_fee * Decimal("1.5")

        return base_amount + overdue_amount
