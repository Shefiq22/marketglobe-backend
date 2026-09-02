from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from alerts.models import Alert
from assets.models import Asset
from predictions.models import Prediction

User = get_user_model()


class AlertCRUDTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bob", email="bob@example.com", password="X1234567x!")
        self.asset = Asset.objects.create(symbol="AAPL", name="Apple", asset_class="stock", yfinance_symbol="AAPL", last_price=Decimal("150.00"))
        self.client.force_authenticate(self.user)

    def test_create_price_above_alert(self):
        resp = self.client.post("/api/alerts/", {"asset": self.asset.id, "alert_type": "price_above", "target_value": "160.00"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["alert_type"], "price_above")
        self.assertFalse(resp.data["triggered"])

    def test_list_alerts(self):
        Alert.objects.create(user=self.user, asset=self.asset, alert_type="price_below", target_value=Decimal("140.00"))
        resp = self.client.get("/api/alerts/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_toggle_alert(self):
        alert = Alert.objects.create(user=self.user, asset=self.asset, alert_type="price_above", target_value=Decimal("160.00"))
        resp = self.client.patch(f"/api/alerts/{alert.id}/", {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        alert.refresh_from_db()
        self.assertFalse(alert.is_active)

    def test_delete_alert(self):
        alert = Alert.objects.create(user=self.user, asset=self.asset, alert_type="price_above", target_value=Decimal("160.00"))
        resp = self.client.delete(f"/api/alerts/{alert.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Alert.objects.filter(id=alert.id).exists())

    def test_user_isolation(self):
        other = User.objects.create_user(username="eve", email="eve@example.com", password="X1234567x!")
        Alert.objects.create(user=other, asset=self.asset, alert_type="price_above", target_value=Decimal("160.00"))
        resp = self.client.get("/api/alerts/")
        self.assertEqual(resp.data["count"], 0)


class AlertCheckTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="carol", email="carol@example.com", password="X1234567x!")
        self.asset = Asset.objects.create(symbol="TSLA", name="Tesla", asset_class="stock", yfinance_symbol="TSLA", last_price=Decimal("200.00"))
        self.client.force_authenticate(self.user)

    def test_price_above_fires(self):
        alert = Alert.objects.create(user=self.user, asset=self.asset, alert_type="price_above", target_value=Decimal("190.00"))
        resp = self.client.post("/api/alerts/check/", format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        alert.refresh_from_db()
        self.assertTrue(alert.triggered)

    def test_price_below_no_fire(self):
        alert = Alert.objects.create(user=self.user, asset=self.asset, alert_type="price_below", target_value=Decimal("180.00"))
        self.client.post("/api/alerts/check/", format="json")
        alert.refresh_from_db()
        self.assertFalse(alert.triggered)

    def test_probability_fires(self):
        Prediction.objects.create(
            asset=self.asset, horizon="1d", probability_up=Decimal("0.75"), probability_down=Decimal("0.25"),
            has_clear_signal=True, call="UP", last_close=Decimal("200.00"), as_of_date=timezone.now().date(), summary="Test",
        )
        alert = Alert.objects.create(user=self.user, asset=self.asset, alert_type="probability_above", target_value=Decimal("70.00"))
        self.client.post("/api/alerts/check/", format="json")
        alert.refresh_from_db()
        self.assertTrue(alert.triggered)

    def test_already_triggered_ignored(self):
        alert = Alert.objects.create(user=self.user, asset=self.asset, alert_type="price_above", target_value=Decimal("190.00"), triggered=True)
        resp = self.client.post("/api/alerts/check/", format="json")
        self.assertEqual(resp.data["count"], 0)
