from rest_framework import serializers

from .models import Asset, PriceSnapshot


class PriceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSnapshot
        fields = ["price", "change_pct", "snapshot_date"]


class AssetSerializer(serializers.ModelSerializer):
    price_snapshots = PriceSnapshotSerializer(many=True, read_only=True)
    change_pct_display = serializers.CharField(read_only=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "symbol",
            "yfinance_symbol",
            "name",
            "asset_class",
            "is_active",
            "is_delisted",
            "delisted_at",
            "delisted_reason",
            "last_price",
            "last_change_pct",
            "change_pct_display",
            "price_snapshots",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_delisted",
            "delisted_at",
            "delisted_reason",
            "last_price",
            "last_change_pct",
            "created_at",
            "updated_at",
        ]


class AssetCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating assets with live yfinance validation."""

    class Meta:
        model = Asset
        fields = ["symbol", "yfinance_symbol", "name", "asset_class"]

    def validate_yfinance_symbol(self, value):
        info = Asset.validate_yfinance_symbol(value)
        if info is None:
            raise serializers.ValidationError(
                f"Ticker '{value}' could not be validated against yfinance. "
                "Check the symbol and try again."
            )
        return value

    def validate(self, attrs):
        if Asset.objects.filter(yfinance_symbol=attrs["yfinance_symbol"]).exists():
            raise serializers.ValidationError(
                {"yfinance_symbol": "An asset with this ticker already exists."}
            )
        return attrs
