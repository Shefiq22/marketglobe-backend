from django.contrib import admin

from .models import AssetNews, EconomicEvent, MarketNews


@admin.register(EconomicEvent)
class EconomicEventAdmin(admin.ModelAdmin):
    list_display = ["title", "importance", "event_date", "actual_value", "source"]
    list_filter = ["importance", "source", "category"]
    search_fields = ["title", "description"]
    readonly_fields = ["fetched_at"]


@admin.register(MarketNews)
class MarketNewsAdmin(admin.ModelAdmin):
    list_display = ["headline", "source_name", "sentiment", "published_at"]
    list_filter = ["source_name", "sentiment"]
    search_fields = ["headline", "summary"]
    readonly_fields = ["fetched_at"]


@admin.register(AssetNews)
class AssetNewsAdmin(admin.ModelAdmin):
    list_display = ["asset", "headline", "source_name", "sentiment", "published_at"]
    list_filter = ["source_name", "sentiment"]
    search_fields = ["asset__symbol", "headline"]
    readonly_fields = ["fetched_at"]
