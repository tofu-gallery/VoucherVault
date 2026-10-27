# Tofu (2026-10-27): this file is Tofu's addition; it is not part of upstream VoucherVault.
#
# What the pages of a Tofu gallery copy read (myproject/tofu_settings.py adds `context` to the templates' context
# processors; see TOFU.md). Under upstream's own settings none of this is used, and the pages read as upstream's.
import os

from django.conf import settings
from django.contrib.auth.models import User


def uploads_enabled():
    """Whether item forms take an attached file. Off on Tofu, where no disk outlives a restart."""
    return getattr(settings, "VOUCHERVAULT_UPLOADS", True)


def admin_password_state():
    """'missing', 'short' or 'saved': the owner's hidden VOUCHERVAULT_ADMIN_PASSWORD, as this process reads it."""
    name = getattr(settings, "TOFU_ADMIN_PASSWORD_SETTING", "")
    if not name:
        return "saved"
    value = os.environ.get(name, "")
    if not value:
        return "missing"
    if len(value) < getattr(settings, "TOFU_ADMIN_PASSWORD_MIN_LENGTH", 8):
        return "short"
    return "saved"


def _no_account():
    # Read only by the sign-in page, which a signed-in person never sees: one query, and only there.
    return not User.objects.exists()


def context(request):
    return {
        "tofu_copy": True,
        "tofu_source_url": getattr(settings, "SOURCE_URL", ""),
        "tofu_uploads": uploads_enabled(),
        "tofu_logo_token": getattr(settings, "LOGO_DEV_TOKEN", ""),
        "tofu_expiry_alerts_off": getattr(settings, "TOFU_EXPIRY_ALERTS_OFF", False),
        # Templates call these when they use them, so other pages run no query for them.
        "tofu_no_account": _no_account,
        "tofu_admin_password_state": admin_password_state,
        "tofu_admin_username": getattr(settings, "TOFU_ADMIN_USERNAME", "admin"),
        "tofu_admin_password_setting": getattr(settings, "TOFU_ADMIN_PASSWORD_SETTING", ""),
        "tofu_admin_password_min_length": getattr(settings, "TOFU_ADMIN_PASSWORD_MIN_LENGTH", 8),
    }
