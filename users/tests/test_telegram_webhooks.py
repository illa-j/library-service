import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from library.models import Author, Book, Borrowing, Payment
from users.models import TelegramToken
from users.webhooks import SEND_MESSAGE_URL


class TelegramWebhookTestCase(TestCase):
    def setUp(self):
        self.webhook_url = reverse("telegram_webhook")
        self.user = get_user_model().objects.create_user(
            email="test@test.com",
            password="test1234",
            telegram_chat_id="123456789",
            telegram_notifications_enabled=False,
        )

    def _send_webhook(self, payload):
        return self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _payload_for_message(self, text, chat_id="123456789"):
        return {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": int(chat_id), "first_name": "Test"},
                "chat": {"id": int(chat_id), "type": "private"},
                "date": 1234567890,
                "text": text,
            },
        }

    @patch("users.webhooks.requests.post")
    def test_start_command_linked_user(self, mock_post):
        payload = self._payload_for_message("/start")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["chat_id"], 123456789)
        self.assertIn("Welcome to the library service", kwargs["json"]["text"])

    @patch("users.webhooks.requests.post")
    def test_start_command_unlinked_user(self, mock_post):
        payload = self._payload_for_message("/start", chat_id="999999999")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["chat_id"], 999999999)
        self.assertIn("Provide your telegram token", kwargs["json"]["text"])

    @patch("users.webhooks.requests.post")
    def test_enable_notifications_command(self, mock_post):
        payload = self._payload_for_message("/notify")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.telegram_notifications_enabled)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.args[0], SEND_MESSAGE_URL)
        self.assertIn("notification enabled", mock_post.call_args.kwargs["json"]["text"])

    @patch("users.webhooks.requests.post")
    def test_disable_notifications_command(self, mock_post):
        payload = self._payload_for_message("/unnotify")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertFalse(self.user.telegram_notifications_enabled)
        mock_post.assert_called_once()
        self.assertIn(
            "notification disabled",
            mock_post.call_args.kwargs["json"]["text"],
        )

    @patch("users.webhooks.requests.post")
    def test_notify_requires_linked_user(self, mock_post):
        payload = self._payload_for_message("/notify", chat_id="999999999")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn(
            "Provide your telegram token",
            mock_post.call_args.kwargs["json"]["text"],
        )

    @patch("users.webhooks.requests.post")
    def test_unnotify_requires_linked_user(self, mock_post):
        payload = self._payload_for_message("/unnotify", chat_id="999999999")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn(
            "Provide your telegram token",
            mock_post.call_args.kwargs["json"]["text"],
        )

    @patch("users.webhooks.requests.post")
    def test_token_invalid_format(self, mock_post):
        payload = self._payload_for_message("/token")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn("Invalid token format", mock_post.call_args.kwargs["json"]["text"])

    @patch("users.webhooks.requests.post")
    def test_token_invalid_uuid(self, mock_post):
        payload = self._payload_for_message("/token not-a-uuid")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn("Invalid token.", mock_post.call_args.kwargs["json"]["text"])

    @patch("users.webhooks.requests.post")
    def test_token_missing_in_db(self, mock_post):
        payload = self._payload_for_message(f"/token {uuid.uuid4()}")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn("Invalid token.", mock_post.call_args.kwargs["json"]["text"])

    @patch("users.webhooks.requests.post")
    def test_token_user_already_linked(self, mock_post):
        telegram_token = TelegramToken.objects.create(user=self.user)
        payload = self._payload_for_message(f"/token {telegram_token.token}")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn(
            "already linked",
            mock_post.call_args.kwargs["json"]["text"],
        )

    @patch("users.webhooks.requests.post")
    def test_token_happy_path(self, mock_post):
        user = get_user_model().objects.create_user(
            email="unlinked@test.com",
            password="test1234",
            telegram_chat_id="",
        )
        telegram_token = TelegramToken.objects.create(user=user)
        payload = self._payload_for_message(
            f"/token {telegram_token.token}", chat_id="555555555"
        )

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.telegram_chat_id, "555555555")
        self.assertFalse(TelegramToken.objects.filter(id=telegram_token.id).exists())
        mock_post.assert_not_called()

    @patch("users.webhooks.requests.post")
    def test_payments_requires_linked_user(self, mock_post):
        payload = self._payload_for_message("/payments", chat_id="999999999")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn(
            "Provide your telegram token",
            mock_post.call_args.kwargs["json"]["text"],
        )

    @patch("users.webhooks.requests.post")
    def test_payments_no_pending(self, mock_post):
        payload = self._payload_for_message("/payments")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn("no pending payments", mock_post.call_args.kwargs["json"]["text"])

    @patch("users.webhooks.requests.post")
    def test_payments_with_pending(self, mock_post):
        author = Author.objects.create(first_name="John", last_name="Doe")
        book = Book.objects.create(
            title="Test Book",
            author=author,
            inventory=1,
            daily_fee="1.00",
        )
        borrowing = Borrowing.objects.create(
            user=self.user,
            book=book,
            expected_return_date=timezone.now().date() + timedelta(days=7),
        )
        Payment.objects.create(
            borrowing=borrowing,
            status=Payment.StatusChoices.PENDING,
            stripe_session_url="https://example.com/session",
        )
        payload = self._payload_for_message("/payments")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        text = mock_post.call_args.kwargs["json"]["text"]
        self.assertIn("Your pending payments", text)
        self.assertIn("Status: pending", text)

    @patch("users.webhooks.requests.post")
    def test_borrowings_requires_linked_user(self, mock_post):
        payload = self._payload_for_message("/borrowings", chat_id="999999999")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn(
            "Provide your telegram token",
            mock_post.call_args.kwargs["json"]["text"],
        )

    @patch("users.webhooks.requests.post")
    def test_borrowings_no_active(self, mock_post):
        payload = self._payload_for_message("/borrowings")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn("no active borrowings", mock_post.call_args.kwargs["json"]["text"])

    @patch("users.webhooks.requests.post")
    def test_borrowings_with_active(self, mock_post):
        author = Author.objects.create(first_name="Jane", last_name="Roe")
        book = Book.objects.create(
            title="Another Book",
            author=author,
            inventory=1,
            daily_fee="2.00",
        )
        Borrowing.objects.create(
            user=self.user,
            book=book,
            expected_return_date=timezone.now().date() + timedelta(days=7),
        )
        payload = self._payload_for_message("/borrowings")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        text = mock_post.call_args.kwargs["json"]["text"]
        self.assertIn("Your active borrowings", text)
        self.assertIn("Another Book", text)

    @patch("users.webhooks.requests.post")
    def test_unknown_user_command(self, mock_post):
        payload = self._payload_for_message("/notify", chat_id="999999999")

        response = self._send_webhook(payload)
        self.assertEqual(response.status_code, 200)
        mock_post.assert_called_once()
        self.assertIn(
            "Provide your telegram token",
            mock_post.call_args.kwargs["json"]["text"],
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.telegram_notifications_enabled)
