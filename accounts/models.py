from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model for Pulse Markets."""

    class Meta:
        db_table = "accounts_user"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.username
