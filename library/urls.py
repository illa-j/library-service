from django.urls import path, include
from rest_framework import routers

from library.views import (
    AuthorViewSet,
    BookViewSet
)

app_name = "library"

router = routers.DefaultRouter()
router.register("authors", AuthorViewSet)
router.register("books", BookViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
