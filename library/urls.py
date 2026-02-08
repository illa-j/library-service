from django.urls import path, include
from rest_framework import routers

from library.views import AuthorViewSet, BookViewSet, BorrowingViewSet, PaymentViewSet

app_name = "library"

router = routers.DefaultRouter()
router.register("authors", AuthorViewSet)
router.register("books", BookViewSet)
router.register("borrowings", BorrowingViewSet)
router.register("payments", PaymentViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
