from unittest import mock

from django.test import TestCase

from . import services
from .sentiment import extract_related_symbols, score_sentiment
from assets.models import Asset


class SentimentScoreTests(TestCase):
    def test_positive_headline(self):
        result = score_sentiment("Apple stock surges to record high after earnings beat")
        self.assertEqual(result["label"], "positive")

    def test_negative_headline(self):
        result = score_sentiment("Company plunges after downgrade and weak guidance")
        self.assertEqual(result["label"], "negative")

    def test_neutral_headline(self):
        result = score_sentiment("Firm announces date for annual shareholder meeting")
        self.assertEqual(result["label"], "neutral")

    def test_negation_flips_bullish(self):
        result = score_sentiment("Sales did not beat expectations, stock guidance weak")
        # "not beat" should offset towards neutral/negative rather than positive.
        self.assertNotEqual(result["label"], "positive")


class ExtractRelatedSymbolsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Asset.objects.create(
            symbol="AAPL",
            yfinance_symbol="AAPL",
            name="Apple Inc",
            asset_class="stock",
        )
        Asset.objects.create(
            symbol="TSLA",
            yfinance_symbol="TSLA",
            name="Tesla",
            asset_class="stock",
        )

    def test_extracts_ticker_from_headline(self):
        symbols = extract_related_symbols("Tesla hits fresh record on production")
        self.assertIn("TSLA", symbols)

    def test_excludes_current_asset(self):
        asset = Asset.objects.get(yfinance_symbol="AAPL")
        symbols = extract_related_symbols("Apple announces new quarter results")
        self.assertNotIn("AAPL", symbols)


class XoomarEventTests(TestCase):
    def test_as_text(self):
        self.assertEqual(services._as_text(None), "")
        self.assertEqual(services._as_text("2.1%"), "2.1%")
        self.assertEqual(services._as_text("205K"), "205K")

    @mock.patch.object(services, "requests")
    def test_fetch_parses_and_upserts(self, mock_req):
        mock_req.get.return_value.raise_for_status.return_value = None
        mock_req.get.return_value.json.return_value = {
            "data": [
                {
                    "eventName": "Nonfarm Payrolls (Employment Situation)",
                    "scheduledAt": "2026-09-04T12:30:00.000Z",
                    "importance": "high",
                    "previous": "205K",
                    "actual": "210K",
                    "forecast": None,
                },
                {
                    "eventName": "FOMC Rate Decision",
                    "scheduledAt": "2026-09-17",
                    "importance": "HIGH",
                    "actual": None,
                },
            ]
        }

        count = services.fetch_xoomar_events()

        self.assertEqual(count, 2)
        from .models import EconomicEvent

        nfp = EconomicEvent.objects.get(title="Nonfarm Payrolls (Employment Situation)")
        self.assertEqual(nfp.currency, "USD")
        self.assertEqual(nfp.importance, "high")
        self.assertEqual(nfp.actual_value, "210K")
        self.assertEqual(nfp.previous_value, "205K")
        self.assertEqual(nfp.forecast_value, "")
        self.assertEqual(nfp.source, "XOOMAR")

        fomc = EconomicEvent.objects.get(title="FOMC Rate Decision")
        self.assertEqual(fomc.importance, "high")
