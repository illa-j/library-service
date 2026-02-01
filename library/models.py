from django.db import models


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
    price = models.DecimalField(max_digits=10, decimal_places=2)
