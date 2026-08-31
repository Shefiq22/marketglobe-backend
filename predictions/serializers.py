from rest_framework import serializers

from .models import ModelMetric, Prediction


class PredictionSerializer(serializers.ModelSerializer):
    confidence = serializers.FloatField(read_only=True)
    is_bullish = serializers.BooleanField(read_only=True)
    asset_symbol = serializers.CharField(source="asset.symbol", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    asset_class = serializers.CharField(source="asset.asset_class", read_only=True)
    yfinance_symbol = serializers.CharField(source="asset.yfinance_symbol", read_only=True)

    class Meta:
        model = Prediction
        fields = [
            "id",
            "asset",
            "asset_symbol",
            "asset_name",
            "asset_class",
            "yfinance_symbol",
            "horizon",
            "probability_up",
            "probability_down",
            "has_clear_signal",
            "call",
            "confidence",
            "is_bullish",
            "last_close",
            "as_of_date",
            "features_used",
            "indicators",
            "summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ModelMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelMetric
        fields = "__all__"
        read_only_fields = [
            "id",
            "metric_name",
            "metric_value",
            "description",
            "measured_at",
            "created_at",
        ]
