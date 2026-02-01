from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APITestCase


def user_authentication(client, email, password):
    user = get_user_model().objects.create_user(
        email=email,
        password=password
    )
    user.is_active = True
    user.save()

    login_response = client.post(
        reverse("users:token_obtain_pair"),
        {
            "email": email,
            "password": password
        }
    )

    tokens = login_response.data

    return tokens


class TestUser(APITestCase):
    def test_register_user(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "email": "test@example.com",
                "password": "test_password1234"
            }
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(get_user_model().objects.first().email, "test@example.com")

    def test_update_user(self):
        access_token = user_authentication(
            self.client,
            "test@example.com",
            "test_password1234"
        )["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.put(
            reverse("users:me"),
            {
                "first_name": "Test",
                "last_name": "Test",
                "email": "test@example.com"
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.first().first_name, "Test")
        self.assertEqual(get_user_model().objects.first().last_name, "Test")

    def test_partial_update_user(self):
        access_token = user_authentication(
            self.client,
            "test@example.com",
            "test_password1234"
        )["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.patch(
            reverse("users:me"),
            {
                "first_name": "Test",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.first().first_name, "Test")
        self.assertEqual(get_user_model().objects.first().email, "test@example.com")

    def test_logout_user(self):
        tokens = user_authentication(
            self.client,
            "test@example.com",
            "test_password1234"
        )

        refresh_token = tokens["refresh"]
        access_token = tokens["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response_logout = self.client.post(
            reverse("users:logout"),
            {
                "refresh_token": refresh_token
            }
        )

        response_verify_token = self.client.post(
            reverse("users:token_verify"),
            {
                "token": refresh_token
            }
        )

        self.assertEqual(response_logout.status_code, 200)
        self.assertEqual(response_verify_token.status_code, 400)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class MailSendingTests(TransactionTestCase):
    def test_password_changing(self):
        access_token = user_authentication(
            self.client,
            "test@example.com",
            "test_password1234"
        )["access"]

        response = self.client.post(
            reverse("users:password_change"),
            {"password": "test_password5678"},
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])
        self.assertIn("confirm password change", mail.outbox[0].subject.lower())

    def test_registration(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "email": "test@example.com",
                "password": "test_password1234"
            }
        )

        self.assertEqual(response.status_code, 201)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])
        self.assertIn("verify your email", mail.outbox[0].subject.lower())
