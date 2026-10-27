# Tofu (2026-10-27): this file is Tofu's addition; it is not part of upstream VoucherVault.
#
# The URLs of a Tofu copy (ROOT_URLCONF in myproject/tofu_settings.py): upstream's myproject/urls.py, unchanged, after
# one page of the copy's own. Upstream includes django.contrib.auth's URLs, and with them Django's password-reset page
# (/<language>/accounts/password_reset/, which no page links to), whose email links to the address the request named
# in its Host header. A copy answers any Host header (ALLOWED_HOSTS in tofu_settings.py), so here the email names the
# copy's own address, the first of DOMAIN's, instead. A copy sends no email at all (upstream configures none), so
# nothing a person sees changes: no link is built from a request's Host header.
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib.auth import views as auth_views
from django.urls import path

from .urls import urlpatterns as upstream_urlpatterns

urlpatterns = i18n_patterns(
    path(
        "accounts/password_reset/",
        auth_views.PasswordResetView.as_view(extra_email_context=settings.TOFU_EMAIL_ADDRESS),
        name="password_reset",
    ),
) + upstream_urlpatterns
