import stripe

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from stripe import SignatureVerificationError
from django.http import HttpResponse

from library.models import Payment
from users.tasks import send_telegram_notification


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, SignatureVerificationError) as e:
        return HttpResponse(status=400)

    event_type = event.get("type")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session.get("id")
        if not session_id:
            return HttpResponse(status=400)

        payment = Payment.objects.filter(stripe_session_id=session_id).first()
        if not payment:
            return HttpResponse(status=400)

        if payment.status == payment.StatusChoices.PAID:
            return HttpResponse(status=200)

        payment.status = payment.StatusChoices.PAID
        payment.save()

        if payment.borrowing.user.telegram_notifications_enabled:
            send_telegram_notification.apply_async(
                args=(
                    payment.borrowing.user_id,
                    "Thank you for paying for your borrowing!",
                )
            )

        return HttpResponse(status=200)

    elif event_type == "checkout.session.expired":
        session = event["data"]["object"]
        session_id = session.get("id")
        payment = Payment.objects.filter(stripe_session_id=session_id).first()
        if payment:
            payment.status = payment.StatusChoices.EXPIRED
            payment.save()
        return HttpResponse(status=200)
    return HttpResponse(status=200)
