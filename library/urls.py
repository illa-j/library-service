from django.urls import path, include
from rest_framework import routers

from library.views import AuthorViewSet

app_name = "library"

router = routers.DefaultRouter()
router.register("authors", AuthorViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
