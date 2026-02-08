from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
import json
from django.contrib.auth import get_user_model

from library.models import Payment, Borrowing, Book, Author


class StripeWebhookTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(first_name="Test", last_name="Author")
        cls.user = get_user_model().objects.create_user(
            email="test@test.com",
            password="test1234"
        )
        cls.book = Book.objects.create(
            title="Test Book",
            daily_fee=Decimal("2.0"),
            author=cls.author
        )
        cls.webhook_url = reverse("stripe_webhook")

    def setUp(self):
        self.borrowing = Borrowing.objects.create(
            user=self.user,
            book=self.book,
            expected_return_date=timezone.now() + timedelta(days=7),
            actual_return_date=timezone.now() + timedelta(days=14),
            is_active=True
        )

        self.payment = Payment.objects.create(
            borrowing=self.borrowing,
            stripe_session_id="cs_test_12345",
            status=Payment.StatusChoices.PENDING
        )
        self.payment.amount_to_pay = self.payment.money_to_pay
        self.payment.save()

    @patch("stripe.Webhook.construct_event")
    def test_successful_payment_webhook(self, mock_construct):
        payload = {
            "id": "evt_test_webhook",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_12345",
                    "payment_status": "paid",
                }
            },
        }

        mock_construct.return_value = payload

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=sig",
        )

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.StatusChoices.PAID)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_with_invalid_session_id(self, mock_construct):
        payload = {
            "id": "evt_test_webhook",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_nonexistent",
                    "payment_status": "paid",
                }
            },
        }

        mock_construct.return_value = payload

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=sig",
        )

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.StatusChoices.PENDING)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_signature_verification_fails(self, mock_construct):
        payload = {"type": "checkout.session.completed"}

        import stripe
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid",
        )

        self.assertEqual(response.status_code, 400)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.StatusChoices.PENDING)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_idempotency(self, mock_construct):
        payload = {
            "id": "evt_test_webhook",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_12345",
                    "payment_status": "paid",
                }
            },
        }

        mock_construct.return_value = payload

        response1 = self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=sig",
        )

        response2 = self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=sig",
        )

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.StatusChoices.PAID)

    @patch("stripe.Webhook.construct_event")
    def test_changing_payment_status_to_expired(self, mock_construct):
        payload = {
            "id": "evt_test_webhook_expired",
            "object": "event",
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": "cs_test_12345",
                    "status": "expired",
                }
            },
        }

        timestamp = "1234567890"
        payload_json = json.dumps(payload)

        mock_construct.return_value = payload

        response = self.client.post(
            self.webhook_url,
            data=payload_json,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1=signature",
        )

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.StatusChoices.EXPIRED)

    @patch("stripe.Webhook.construct_event")
    def test_expired_session_with_nonexistent_payment(self, mock_construct):
        payload = {
            "id": "evt_test_webhook_expired_missing",
            "object": "event",
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": "cs_nonexistent_session",
                    "status": "expired",
                }
            },
        }

        timestamp = "1234567890"
        payload_json = json.dumps(payload)

        mock_construct.return_value = payload

        response = self.client.post(
            self.webhook_url,
            data=payload_json,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1=signature",
        )

        self.assertEqual(response.status_code, 200)
