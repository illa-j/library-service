from django.test import TestCase

from library.models import Author, Book


class BookModelTests(TestCase):
    def test_book_str(self):
        author = Author.objects.create(first_name="Terry", last_name="Pratchett")
        book = Book.objects.create(
            title="Small Gods",
            author=author,
            inventory=1,
            daily_fee="1.50",
        )

        self.assertEqual(str(book), "Small Gods by Terry Pratchett")
