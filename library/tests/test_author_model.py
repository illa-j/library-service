from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from library.models import Author


class AuthorModelTests(TestCase):
    def test_author_str(self):
        author = Author.objects.create(first_name="Jane", last_name="Austen")

        self.assertEqual(str(author), "Jane Austen")

    def test_author_birth_and_death_validation(self):
        with self.assertRaises(ValidationError):
            Author.objects.create(
                first_name="Bad",
                last_name="Dates",
                date_of_birth=date(2000, 1, 1),
                date_of_death=date(1999, 1, 1),
            )
