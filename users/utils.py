from __future__ import annotations

import secrets

from typing import Dict, Optional
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google_auth_oauthlib.flow import Flow
from django.conf import settings
from django.contrib.auth import get_user_model

USER = get_user_model()


class GoogleOAuthHandler:
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI

    def get_authorization_url(self) -> tuple[str, str]:
        flow = Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ],
        )

        flow.redirect_uri = self.redirect_uri

        state = secrets.token_urlsafe(32)

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=state,
            prompt="consent",
        )

        return authorization_url, state

    def exchange_code_for_tokens(self, code: str) -> Optional[Dict]:
        flow = Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ],
        )

        flow.redirect_uri = self.redirect_uri

        flow.fetch_token(code=code)

        credentials = flow.credentials

        return self.verify_google_token(credentials.id_token)

    def verify_google_token(self, token: str) -> Optional[Dict]:
        try:
            id_info = id_token.verify_oauth2_token(
                token, google_requests.Request(), self.client_id
            )

            return {
                "email": id_info.get("email"),
                "first_name": id_info.get("given_name", ""),
                "last_name": id_info.get("family_name", ""),
                "google_id": id_info.get("sub"),
                "email_verified": id_info.get("email_verified", False),
            }
        except ValueError:
            return None


def get_or_create_google_user(google_data: Dict) -> tuple[USER, bool]:
    email = google_data.get("email")
    google_id = google_data.get("google_id")

    if google_id:
        try:
            user = get_user_model().objects.get(google_id=google_id)
            return user, False
        except get_user_model().DoesNotExist:
            pass

    try:
        user = get_user_model().objects.get(email=email)

        if not user.google_id:
            user.google_id = google_id
            user.is_active = True
            user.save()

        return user, False
    except get_user_model().DoesNotExist:
        pass

    user = get_user_model().objects.create(
        email=email,
        first_name=google_data.get("first_name", ""),
        last_name=google_data.get("last_name", ""),
        google_id=google_id,
        is_active=True,
    )

    user.set_unusable_password()
    user.save()

    return user, True
