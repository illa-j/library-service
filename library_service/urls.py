from debug_toolbar.toolbar import debug_toolbar_urls
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from library.webhooks import stripe_webhook
from users.webhooks import telegram_webhook


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path("api/library/", include("library.urls")),
    path("stripe-webhook/", stripe_webhook, name="stripe_webhook"),
    path("telegram-webhook/", telegram_webhook, name="telegram_webhook"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + debug_toolbar_urls()
