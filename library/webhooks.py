import stripe
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from stripe import SignatureVerificationError
from django.http import HttpResponse

from library.models import Payment
from users.tasks import send_telegram_notification

logger = logging.getLogger(__name__)


@csrf_exempt
def stripe_webhook(request: HttpResponse) -> HttpResponse:
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, SignatureVerificationError) as e:
        logger.error(f"Webhook signature verification failed: {str(e)}")
        return HttpResponse(status=400)

    event_type = event.get("type")
    event_id = event.get("id")

    logger.info(f"Received webhook event: {event_type} (ID: {event_id})")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session.get("id")
        if not session_id:
            logger.warning(f"No session_id in event {event_id}")
            return HttpResponse(status=200)

        try:
            payment = Payment.objects.select_related('borrowing__user').get(
                stripe_session_id=session_id
            )
        except Payment.DoesNotExist:
            logger.warning(f"Payment not found for session {session_id}")
            return HttpResponse(status=200)

        if payment.status == payment.StatusChoices.PAID:
            logger.info(f"Payment {payment.id} already marked as PAID")
            return HttpResponse(status=200)

        payment.status = payment.StatusChoices.PAID
        payment.save()

        logger.info(f"Payment {payment.id} marked as PAID (session: {session_id})")

        if payment.borrowing.user.telegram_notifications_enabled:
            send_telegram_notification.apply_async(
                args=(
                    payment.borrowing.user_id,
                    "Thank you for paying for your borrowing!",
                )
            )
            logger.info(f"Notification queued for user {payment.borrowing.user_id}")

        return HttpResponse(status=200)

    elif event_type == "checkout.session.expired":
        session = event["data"]["object"]
        session_id = session.get("id")
        payment = Payment.objects.filter(stripe_session_id=session_id).first()
        if payment:
            payment.status = payment.StatusChoices.EXPIRED
            payment.save()
            logger.info(f"Payment {payment.id} marked as EXPIRED (session: {session_id})")
        else:
            logger.warning(f"Payment not found for expired session {session_id}")
        return HttpResponse(status=200)
    return HttpResponse(status=200)
