from django.contrib import admin

from .models import ModelMetric, Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = [
        "asset",
        "horizon",
        "call",
        "probability_up",
        "probability_down",
        "has_clear_signal",
        "as_of_date",
    ]
    list_filter = ["horizon", "call", "has_clear_signal", "asset__asset_class"]
    search_fields = ["asset__symbol", "asset__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ModelMetric)
class ModelMetricAdmin(admin.ModelAdmin):
    list_display = ["metric_name", "metric_value", "measured_at"]
    list_filter = ["metric_name"]
    readonly_fields = ["created_at"]
