import json
import uuid

import requests
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from library.models import Payment
from users.models import TelegramToken

SEND_MESSAGE_URL = (
    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
)


def is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def get_user_by_telegram_chat_id(chat_id):
    return get_user_model().objects.filter(telegram_chat_id=chat_id).first()


@csrf_exempt
def telegram_webhook(request):
    body = json.loads(request.body)
    message_text = body["message"]["text"].split(" ")
    user = get_user_by_telegram_chat_id(chat_id=body["message"]["chat"]["id"])
    match message_text[0]:
        case "/start":
            if not user:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Provide your telegram token first with /token command.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            payload = {
                "chat_id": body["message"]["chat"]["id"],
                "text": (
                    "*Welcome to the library service!*\n\n"
                    "_Commands:_\n"
                    "/borrowings - see your active borrowings\n"
                    "/payments - see your pending payments\n"
                    "/notify - enable notifications about overdue borrowings, new borrowings, and successful payments\n"
                    "/unnotify - disable notifications\n"
                ),
                "parse_mode": "Markdown",
            }
            requests.post(SEND_MESSAGE_URL, json=payload)
        case "/token":
            if len(message_text) != 2:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Invalid token format. Use /token <token>.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            token = message_text[1]
            if not is_valid_uuid(token):
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Invalid token.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            telegram_token = TelegramToken.objects.filter(token=token).first()
            if not telegram_token:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Invalid token.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            user = telegram_token.user
            if user.telegram_chat_id:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Your account is already linked to a Telegram chat.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            user.telegram_chat_id = body["message"]["chat"]["id"]
            user.save()
            telegram_token.delete()
        case "/payments":
            if not user:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Provide your telegram token first with /token command.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            payments = Payment.objects.filter(
                borrowing__user=user, status=Payment.StatusChoices.PENDING
            )
            if not payments:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "You have no pending payments.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            payload = {
                "chat_id": body["message"]["chat"]["id"],
                "text": f"Your pending payments:\n{'\n'.join([str(payment) for payment in payments])}",
            }
            requests.post(SEND_MESSAGE_URL, json=payload)
        case "/borrowings":
            if not user:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Provide your telegram token first with /token command.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            borrowings = user.borrowings.filter(is_active=True)
            if not borrowings:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "You have no active borrowings.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)

            payload = {
                "chat_id": body["message"]["chat"]["id"],
                "text": f"Your active borrowings:\n{'\n'.join([str(borrowing) for borrowing in borrowings])}",
            }
            requests.post(SEND_MESSAGE_URL, json=payload)
        case "/notify":
            if not user:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Provide your telegram token first with /token command.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)
            user.telegram_notifications_enabled = True
            user.save()
            payload = {
                "chat_id": body["message"]["chat"]["id"],
                "text": "Your notification enabled.",
            }
            requests.post(SEND_MESSAGE_URL, json=payload)
        case "/unnotify":
            if not user:
                payload = {
                    "chat_id": body["message"]["chat"]["id"],
                    "text": "Provide your telegram token first with /token command.",
                }
                requests.post(SEND_MESSAGE_URL, json=payload)
                return HttpResponse(status=200)
            user.telegram_notifications_enabled = False
            user.save()
            payload = {
                "chat_id": body["message"]["chat"]["id"],
                "text": "Your notification disabled.",
            }
            requests.post(SEND_MESSAGE_URL, json=payload)
    return HttpResponse(status=200)
