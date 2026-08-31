from django.contrib import admin

from .models import Watchlist, WatchlistItem


class WatchlistItemInline(admin.TabularInline):
    model = WatchlistItem
    extra = 0
    fields = ["asset", "notes", "added_at"]
    readonly_fields = ["added_at"]


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "asset_count", "created_at", "updated_at"]
    list_filter = ["user"]
    search_fields = ["user__username", "name"]
    inlines = [WatchlistItemInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ["watchlist", "asset", "notes", "added_at"]
    search_fields = ["watchlist__name", "asset__symbol"]
    readonly_fields = ["added_at"]
