from datetime import timedelta
from unittest.mock import patch, Mock

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from library.models import Author, Book, Borrowing
from users.tasks import (
    send_verification_email,
    send_password_change_confirmation_email,
    send_telegram_notification,
    check_overdue_borrowings,
)


def sample_author(**params):
    defaults = {"first_name": "Mary", "last_name": "Shelley"}
    defaults.update(params)
    return Author.objects.create(**defaults)


def sample_book(**params):
    defaults = {
        "title": "Frankenstein",
        "inventory": 1,
        "daily_fee": "1.00",
    }
    defaults.update(params)
    return Book.objects.create(**defaults)


class CeleryTasksTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@test.com",
            password="testpass123",
            telegram_chat_id="123456789",
            telegram_notifications_enabled=True,
        )
        self.author = sample_author()
        self.book = sample_book(author=self.author)

    @patch("users.tasks.send_mail")
    def test_send_verification_email_sends_mail(self, mock_send_mail):
        verify_link = "https://example.com/verify"

        send_verification_email.run(verify_link, self.user.email)

        mock_send_mail.assert_called_once_with(
            subject="Verify your email",
            message=f"Click to verify: {verify_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.user.email],
        )

    @patch("users.tasks.send_mail")
    def test_send_password_change_confirmation_email_sends_mail(
        self, mock_send_mail
    ):
        confirm_link = "https://example.com/confirm"

        send_password_change_confirmation_email.run(confirm_link, self.user.email)

        mock_send_mail.assert_called_once_with(
            subject="Confirm password change",
            message=f"Click to confirm: {confirm_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.user.email],
        )

    @patch("users.tasks.requests.post")
    def test_send_telegram_notification_posts_when_enabled(self, mock_post):
        mock_response = Mock()
        mock_post.return_value = mock_response

        send_telegram_notification.run(self.user.id, "Hello")

        mock_post.assert_called_once_with(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": self.user.telegram_chat_id, "text": "Hello"},
        )
        mock_response.raise_for_status.assert_called_once()

    @patch("users.tasks.requests.post")
    def test_send_telegram_notification_skips_when_disabled(self, mock_post):
        self.user.telegram_notifications_enabled = False
        self.user.save()

        send_telegram_notification.run(self.user.id, "Hello")

        mock_post.assert_not_called()

    @patch("users.tasks.requests.post")
    def test_send_telegram_notification_skips_when_no_chat_id(self, mock_post):
        self.user.telegram_chat_id = ""
        self.user.save()

        send_telegram_notification.run(self.user.id, "Hello")

        mock_post.assert_not_called()

    @patch("users.tasks.requests.post", side_effect=requests.RequestException("boom"))
    def test_send_telegram_notification_retries_on_error(self, _mock_post):
        with patch.object(
            send_telegram_notification, "retry", side_effect=Exception("retry")
        ) as mock_retry:
            with self.assertRaises(Exception):
                send_telegram_notification.run(self.user.id, "Hello")

            self.assertGreaterEqual(mock_retry.call_count, 1)
            first_call = mock_retry.call_args_list[0]
            self.assertEqual(first_call.kwargs.get("countdown"), 10)

    @patch("users.tasks.send_telegram_notification.apply_async")
    def test_check_overdue_borrowings_sends_notifications(self, mock_apply_async):
        Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=timezone.now().date() + timedelta(days=1),
        )

        check_overdue_borrowings()

        mock_apply_async.assert_called_once_with(
            args=(self.user.id, "Your borrowing is overdue!")
        )

    @patch("users.tasks.send_telegram_notification.apply_async")
    def test_check_overdue_borrowings_skips_when_notifications_disabled(
        self, mock_apply_async
    ):
        self.user.telegram_notifications_enabled = False
        self.user.save()
        Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=timezone.now().date() + timedelta(days=1),
        )

        check_overdue_borrowings()

        mock_apply_async.assert_not_called()
