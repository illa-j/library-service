from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from library.models import Borrowing


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
    retry_backoff=True,
)
def send_verification_email(self, verify_link, user_email):
    send_mail(
        subject="Verify your email",
        message=f"Click to verify: {verify_link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
    retry_backoff=True,
)
def send_password_change_confirmation_email(self, confirm_link, user_email):
    send_mail(
        subject="Confirm password change",
        message=f"Click to confirm: {confirm_link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={
        "max_retries": 3,
    },
    retry_backoff=True,
)
def send_telegram_notification(self, user_id, text):
    try:
        user = get_user_model().objects.get(id=user_id)

        if not user.telegram_notifications_enabled or not user.telegram_chat_id:
            return

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": user.telegram_chat_id,
            "text": text,
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@shared_task
def check_overdue_borrowings():
    due_soon_date = timezone.now().date() + timedelta(days=1)
    overdue_borrowings = Borrowing.objects.filter(
        is_active=True,
        expected_return_date__lte=due_soon_date,
    )

    for borrowing in overdue_borrowings:
        if (
            not borrowing.user.telegram_notifications_enabled
            or not borrowing.user.telegram_chat_id
        ):
            continue
        send_telegram_notification.apply_async(
            args=(borrowing.user_id, "Your borrowing is overdue!")
        )
