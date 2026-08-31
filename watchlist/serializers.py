from rest_framework import serializers

from assets.serializers import AssetSerializer

from .models import Watchlist, WatchlistItem


class WatchlistItemSerializer(serializers.ModelSerializer):
    asset_detail = AssetSerializer(source="asset", read_only=True)

    class Meta:
        model = WatchlistItem
        fields = ["id", "asset", "asset_detail", "notes", "added_at"]
        read_only_fields = ["id", "added_at"]


class WatchlistSerializer(serializers.ModelSerializer):
    items = WatchlistItemSerializer(many=True, read_only=True)
    asset_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Watchlist
        fields = ["id", "name", "items", "asset_count", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class WatchlistCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Watchlist
        fields = ["id", "name"]
        read_only_fields = ["id"]


class WatchlistItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WatchlistItem
        fields = ["id", "asset", "notes"]
        read_only_fields = ["id"]

    def validate_asset(self, value):
        if value.is_delisted:
            raise serializers.ValidationError("Cannot add a delisted asset to a watchlist.")
        return value
