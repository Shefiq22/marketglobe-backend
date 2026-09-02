from django.conf import settings
from django.db import models


class Alert(models.Model):
    """A user-defined price or probability alert for an asset.

    When a price alert triggers, the asset's price has crossed the target
    threshold (above for price_above, below for price_below). Probability
    alerts fire when the model confidence exceeds the target.
    """

    ALERT_TYPES = [
        ("price_above", "Price above"),
        ("price_below", "Price below"),
        ("probability_above", "Probability above"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alerts")
    asset = models.ForeignKey("assets.Asset", on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    target_value = models.DecimalField(max_digits=12, decimal_places=6)
    is_active = models.BooleanField(default=True)
    triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "alerts_alert"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.alert_type} {self.asset.symbol} @ {self.target_value}"
