import os
import tempfile

from PIL import Image
from django.contrib.auth import get_user_model
from django.db.models import Value
from django.db.models.functions import Concat
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from library.models import Author, Book
from library.serializers import BookDetailSerializer, BookListSerializer

BOOK_URL = reverse("library:book-list")


def detail_url(book_id):
    return reverse("library:book-detail", args=[book_id])


def image_upload_url(book_id):
    return reverse("library:book-upload-cover-image", args=[book_id])


def sample_author(**params):
    defaults = {"first_name": "Haruki", "last_name": "Murakami"}
    defaults.update(params)
    return Author.objects.create(**defaults)


def sample_book(**params):
    defaults = {
        "title": "Kafka on the Shore",
        "inventory": 3,
        "daily_fee": "1.25",
    }
    defaults.update(params)
    return Book.objects.create(**defaults)


class UnauthenticatedBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(BOOK_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="user@test.com",
            password="testpass123",
        )
        self.client.force_authenticate(self.user)

    def test_list_books(self):
        author = sample_author()
        sample_book(title="Norwegian Wood", author=author)
        sample_book(title="1Q84", author=author)

        res = self.client.get(BOOK_URL)

        books = Book.objects.annotate(
            full_name=Concat("author__first_name", Value(" "), "author__last_name")
        ).order_by("id")
        serializer = BookListSerializer(books, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], serializer.data)

    def test_retrieve_book_detail(self):
        author = sample_author()
        book = sample_book(author=author)

        res = self.client.get(detail_url(book.id))

        serializer = BookDetailSerializer(book)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_book_forbidden(self):
        author = sample_author()
        payload = {
            "title": "Dance Dance Dance",
            "author": author.id,
            "inventory": 2,
            "daily_fee": "1.50",
        }

        res = self.client.post(BOOK_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AdminBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_user(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.client.force_authenticate(self.admin)

    def test_create_book(self):
        author = sample_author()
        payload = {
            "title": "After Dark",
            "author": author.id,
            "inventory": 4,
            "daily_fee": "2.00",
        }

        res = self.client.post(BOOK_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        book = Book.objects.get(id=res.data["id"])
        self.assertEqual(book.title, payload["title"])
        self.assertEqual(book.author, author)
        self.assertEqual(book.inventory, payload["inventory"])

    def test_update_book(self):
        author = sample_author()
        book = sample_book(author=author)
        payload = {"inventory": 10, "daily_fee": "2.50"}

        res = self.client.patch(detail_url(book.id), payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        book.refresh_from_db()
        self.assertEqual(book.inventory, payload["inventory"])
        self.assertEqual(str(book.daily_fee), payload["daily_fee"])

    def test_delete_book(self):
        author = sample_author()
        book = sample_book(author=author)

        res = self.client.delete(detail_url(book.id))

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Book.objects.filter(id=book.id).exists())

    def test_upload_cover_image(self):
        author = sample_author()
        book = sample_book(author=author)
        url = image_upload_url(book.id)

        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            res = self.client.post(url, {"cover_image": ntf}, format="multipart")

        book.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("cover_image", res.data)
        self.assertTrue(os.path.exists(book.cover_image.path))

    def test_upload_cover_image_bad_request(self):
        author = sample_author()
        book = sample_book(author=author)
        url = image_upload_url(book.id)

        res = self.client.post(url, {"cover_image": "not an image"}, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def tearDown(self):
        for book in Book.objects.all():
            if book.cover_image and os.path.exists(book.cover_image.path):
                os.remove(book.cover_image.path)
