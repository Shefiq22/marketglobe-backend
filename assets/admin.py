from django.contrib import admin

from .models import Asset, PriceSnapshot


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        "symbol",
        "name",
        "asset_class",
        "yfinance_symbol",
        "is_active",
        "is_delisted",
        "last_price",
        "last_change_pct",
    ]
    list_filter = ["asset_class", "is_active", "is_delisted"]
    search_fields = ["symbol", "name", "yfinance_symbol"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    list_display = ["asset", "price", "change_pct", "snapshot_date"]
    list_filter = ["snapshot_date"]
    search_fields = ["asset__symbol"]
