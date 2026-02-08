from django.contrib import admin

from django.contrib.auth import get_user_model

from users.models import EmailVerificationToken, PasswordChangeToken, TelegramToken

admin.site.register(get_user_model())
admin.site.register(EmailVerificationToken)
admin.site.register(PasswordChangeToken)
admin.site.register(TelegramToken)
