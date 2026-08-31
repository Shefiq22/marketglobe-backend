"""
WSGI config for config project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

# Apply any pending schema migrations on boot so the deployed DB stays in sync
# with model changes (no manual management needed after a deploy). Best-effort:
# never block app startup.
from django.core.management import call_command

try:
    call_command("migrate", verbosity=0, interactive=False)
except Exception:
    pass

# In production (DEBUG=False) whitenoise serves static files from the
# collected manifest. Ensure static files are collected on every boot so the
# Django admin and Swagger UI work without a separate build step or manual
# shell access. Best-effort: never block app startup on this.
try:
    call_command("collectstatic", "--noinput", verbosity=0)
except Exception:
    pass

# Auto-create a superuser from environment variables (used to access /admin/).
# Set DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD / DJANGO_SUPERUSER_EMAIL
# in the deployment environment. Only creates when missing, so existing admins
# are never clobbered.
try:
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()
    if username and password:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip() or None,
                password=password,
            )
except Exception:
    pass

# Seed (or refresh) model performance metrics from the ML walk-forward
# evaluation so /api/predictions/metrics/ always serves real numbers on the
# deployed Postgres DB. Best-effort + idempotent (update_or_create), so it is
# safe to run on every boot and never clobbers newer values.
try:
    call_command("seed_metrics", verbosity=0)
except Exception:
    pass

application = get_wsgi_application()
