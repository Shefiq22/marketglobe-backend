from django.db import models

from assets.models import Asset


class Prediction(models.Model):
    HORIZON_CHOICES = [
        ("1d", "1 Day"),
        ("5d", "5 Days"),
        ("1mo", "1 Month"),
        ("3mo", "3 Months"),
        ("1y", "1 Year"),
    ]

    CALL_CHOICES = [
        ("UP", "Up"),
        ("DOWN", "Down"),
        ("NO CLEAR SIGNAL", "No Clear Signal"),
    ]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="predictions")
    horizon = models.CharField(max_length=5, choices=HORIZON_CHOICES)
    probability_up = models.FloatField()
    probability_down = models.FloatField()
    has_clear_signal = models.BooleanField(default=False)
    call = models.CharField(max_length=20, choices=CALL_CHOICES)
    last_close = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    as_of_date = models.DateField()
    features_used = models.JSONField(default=dict, blank=True)
    indicators = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "predictions_prediction"
        unique_together = ["asset", "horizon"]
        ordering = ["-as_of_date", "asset__symbol"]

    def __str__(self):
        return f"{self.asset.symbol} {self.horizon}: {self.call} (UP={self.probability_up:.2%})"

    @property
    def confidence(self):
        """Absolute signal strength (0.5 to 1.0)."""
        return max(self.probability_up, self.probability_down)

    @property
    def is_bullish(self):
        return self.call == "UP"

    @property
    def to_frontend_format(self):
        """Map to Flutter frontend Asset prediction fields."""
        return {
            "confidence": self.confidence,
            "bullish": self.is_bullish,
            "hasSignal": self.has_clear_signal,
            "call": self.call,
            "probabilityUp": self.probability_up,
            "probabilityDown": self.probability_down,
            "indicators": self.indicators,
            "summary": self.summary,
        }


class ModelMetric(models.Model):
    """Track model performance metrics over time."""

    metric_name = models.CharField(max_length=100)
    metric_value = models.FloatField()
    description = models.TextField(blank=True, default="")
    measured_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "predictions_model_metric"
        ordering = ["-measured_at"]

    def __str__(self):
        return f"{self.metric_name}: {self.metric_value:.4f} @ {self.measured_at}"
