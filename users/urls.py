from django.urls import path

from users.views import (
    CreateUserView,
    ManageUserView,
    LogoutView,
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView, VerifyEmailAPIView
)


app_name = "users"


urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("register/", CreateUserView.as_view(), name="register"),
    path("me/", ManageUserView.as_view(), name="me"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("verify-email/", VerifyEmailAPIView.as_view(), name="verify_email"),
]
