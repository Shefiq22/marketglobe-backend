from rest_framework import serializers

from .models import AppNotification


class AppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppNotification
        fields = [
            "id",
            "kind",
            "title",
            "body",
            "source_ref",
            "link_url",
            "image_url",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields