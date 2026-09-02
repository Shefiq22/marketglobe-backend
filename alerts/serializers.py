from rest_framework import serializers

from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    asset_symbol = serializers.CharField(source="asset.symbol", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    asset_class = serializers.CharField(source="asset.asset_class", read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id",
            "asset",
            "asset_symbol",
            "asset_name",
            "asset_class",
            "alert_type",
            "target_value",
            "is_active",
            "triggered",
            "triggered_at",
            "created_at",
        ]
        read_only_fields = ["id", "triggered", "triggered_at", "created_at"]


class AlertCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ["asset", "alert_type", "target_value"]
