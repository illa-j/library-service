import os
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from decimal import Decimal

from django.utils import timezone
from django.utils.text import slugify
from django_countries.fields import CountryField

USER = get_user_model()


def author_image_file_path(instance, filename):
    _, extension = os.path.splitext(filename)
    filename = f"{slugify(f"{instance.first_name} {instance.last_name}")}-{uuid.uuid4()}{extension}"

    return os.path.join("uploads/authors_pictures/", filename)


def book_image_file_path(instance, filename):
    _, extension = os.path.splitext(filename)
    filename = f"{slugify(instance.title)}-{uuid.uuid4()}{extension}"

    return os.path.join("uploads/books_pictures/", filename)


class Author(models.Model):
    photo = models.ImageField(upload_to=author_image_file_path, null=True, blank=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    biography = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_death = models.DateField(null=True, blank=True)

    country = CountryField(blank=True)

    wikipedia = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def validate_dates_of_birth_and_death(date_of_birth, date_of_death, error_to_raise):
        if date_of_birth and date_of_death and date_of_birth > date_of_death:
            raise error_to_raise("Date of death should be after date of birth")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("first_name", "last_name")

    def clean(self):
        Author.validate_dates_of_birth_and_death(
            self.date_of_birth, self.date_of_death, ValidationError
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super(Author, self).save(*args, **kwargs)


class Book(models.Model):
    class CoverChoices(models.TextChoices):
        HARD = "hard", "Hard"
        SOFT = "soft", "Soft"

    cover_image = models.ImageField(
        upload_to=book_image_file_path, blank=True, null=True
    )
    title = models.CharField(max_length=100, unique=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    cover = models.CharField(
        max_length=10, choices=CoverChoices.choices, default=CoverChoices.SOFT
    )
    inventory = models.PositiveIntegerField(default=0)
    daily_fee = models.DecimalField(max_digits=3, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} by {self.author}"


class Borrowing(models.Model):
    borrow_date = models.DateField(auto_now_add=True)
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(blank=True, null=True)
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="borrowings")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="borrowings")
    is_active = models.BooleanField(default=True)

    @staticmethod
    def validate_expected_and_actual_date_after_borrowed(
        error_to_raise,
        borrowed_date,
        expected_return_date=None,
        actual_return_date=None,
    ):
        if expected_return_date and expected_return_date <= borrowed_date:
            raise error_to_raise(
                "Expected return date cannot be earlier than borrow date."
            )
        if actual_return_date and actual_return_date <= borrowed_date:
            raise error_to_raise(
                "Actual return date cannot be earlier than borrow date."
            )

    def clean(self):
        Borrowing.validate_expected_and_actual_date_after_borrowed(
            ValidationError,
            self.borrow_date or timezone.now().date(),
            self.expected_return_date,
            self.actual_return_date,
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super(Borrowing, self).save(*args, **kwargs)

    def __str__(self):
        return (
            f"Borrow date: {self.borrow_date}\n"
            f"Expected return date: {self.expected_return_date}\n"
            f"Book: {self.book}"
        )


class Payment(models.Model):
    class StatusChoices(models.TextChoices):
        PAID = "paid", "Paid"
        PENDING = "pending", "Pending"
        EXPIRED = "expired", "Expired"

    class TypeChoices(models.TextChoices):
        PAYMENT = "payment", "Payment"
        FINE = "fine", "Fine"

    status = models.CharField(
        max_length=10, choices=StatusChoices.choices, default=StatusChoices.PENDING
    )
    type = models.CharField(
        max_length=10, choices=TypeChoices.choices, default=TypeChoices.PAYMENT
    )
    borrowing = models.ForeignKey(
        Borrowing, on_delete=models.PROTECT, related_name="payments"
    )
    stripe_session_url = models.URLField(blank=True, null=True, max_length=500)
    stripe_session_id = models.TextField(blank=True, null=True)
    amount_to_pay = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
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

    def save(self, *args, **kwargs):
        borrowing = self.borrowing

        if borrowing.actual_return_date and borrowing.expected_return_date:
            overdue_days = max(
                (borrowing.actual_return_date - borrowing.expected_return_date).days, 0
            )
            if overdue_days > 0:
                self.type = Payment.TypeChoices.FINE
            else:
                self.type = Payment.TypeChoices.PAYMENT

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Status: {self.status}\n"
            f"Type: {self.type}\n"
            f"Stripe Session URL: {self.stripe_session_url}"
        )
