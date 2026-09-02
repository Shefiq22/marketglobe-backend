from rest_framework import serializers

from .models import AssetNews, EconomicEvent, MarketNews


class EconomicEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EconomicEvent
        fields = [
            "id",
            "title",
            "description",
            "category",
            "currency",
            "importance",
            "event_date",
            "actual_value",
            "forecast_value",
            "previous_value",
            "source",
            "source_url",
            "fetched_at",
        ]
        read_only_fields = fields


class MarketNewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketNews
        fields = [
            "id",
            "headline",
            "summary",
            "source_name",
            "source_url",
            "image_url",
            "related_symbols",
            "sentiment",
            "published_at",
            "fetched_at",
        ]
        read_only_fields = fields


class AssetNewsSerializer(serializers.ModelSerializer):
    asset_symbol = serializers.CharField(source="asset.symbol", read_only=True)

    class Meta:
        model = AssetNews
        fields = [
            "id",
            "asset",
            "asset_symbol",
            "headline",
            "summary",
            "source_name",
            "source_url",
            "sentiment",
            "published_at",
            "fetched_at",
        ]
        read_only_fields = fields
