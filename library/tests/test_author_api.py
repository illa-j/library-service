import os
import tempfile

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from library.models import Author
from library.serializers import AuthorSerializer

AUTHOR_URL = reverse("library:author-list")


def detail_url(author_id):
    return reverse("library:author-detail", args=[author_id])


def image_upload_url(author_id):
    return reverse("library:author-upload-photo", args=[author_id])


def sample_author(**params):
    defaults = {
        "first_name": "Agatha",
        "last_name": "Christie",
    }
    defaults.update(params)
    return Author.objects.create(**defaults)


class UnauthenticatedAuthorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(AUTHOR_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedAuthorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="user@test.com",
            password="testpass123",
        )
        self.client.force_authenticate(self.user)

    def test_list_authors(self):
        sample_author(first_name="Leo", last_name="Tolstoy")
        sample_author(first_name="Virginia", last_name="Woolf")

        res = self.client.get(AUTHOR_URL)

        authors = Author.objects.order_by("-created_at")
        serializer = AuthorSerializer(authors, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], serializer.data)

    def test_retrieve_author_detail(self):
        author = sample_author(first_name="Ursula", last_name="Le Guin")

        res = self.client.get(detail_url(author.id))

        serializer = AuthorSerializer(author)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_author_forbidden(self):
        payload = {"first_name": "Toni", "last_name": "Morrison"}

        res = self.client.post(AUTHOR_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AdminAuthorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_user(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.client.force_authenticate(self.admin)

    def test_create_author(self):
        payload = {"first_name": "Toni", "last_name": "Morrison"}

        res = self.client.post(AUTHOR_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        author = Author.objects.get(id=res.data["id"])
        self.assertEqual(author.first_name, payload["first_name"])
        self.assertEqual(author.last_name, payload["last_name"])

    def test_update_author(self):
        author = sample_author(first_name="George", last_name="Orwell")
        payload = {"first_name": "Eric", "last_name": "Blair"}

        res = self.client.patch(detail_url(author.id), payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        author.refresh_from_db()
        self.assertEqual(author.first_name, payload["first_name"])
        self.assertEqual(author.last_name, payload["last_name"])

    def test_delete_author(self):
        author = sample_author()

        res = self.client.delete(detail_url(author.id))

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Author.objects.filter(id=author.id).exists())

    def test_upload_photo(self):
        author = sample_author()
        url = image_upload_url(author.id)

        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            res = self.client.post(url, {"photo": ntf}, format="multipart")

        author.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("photo", res.data)
        self.assertTrue(os.path.exists(author.photo.path))

    def test_upload_photo_bad_request(self):
        author = sample_author()
        url = image_upload_url(author.id)

        res = self.client.post(url, {"photo": "not an image"}, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def tearDown(self):
        for author in Author.objects.all():
            if author.photo and os.path.exists(author.photo.path):
                os.remove(author.photo.path)
