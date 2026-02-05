from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from library.webhooks import stripe_webhook


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path("api/library/", include("library.urls")),
    path("webhook/", stripe_webhook, name="webhook"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
