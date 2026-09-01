import yfinance as yf
from django.core.management.base import BaseCommand

from assets.models import Asset


# ── Stocks ────────────────────────────────────────────────────────────────────
STOCKS = [
    ("AAPL", "Apple Inc."),
    ("MSFT", "Microsoft Corporation"),
    ("GOOGL", "Alphabet Inc."),
    ("AMZN", "Amazon.com Inc."),
    ("NVDA", "NVIDIA Corporation"),
    ("META", "Meta Platforms Inc."),
    ("TSLA", "Tesla Inc."),
    ("BRK-B", "Berkshire Hathaway Inc."),
    ("JPM", "JPMorgan Chase & Co."),
    ("V", "Visa Inc."),
    ("JNJ", "Johnson & Johnson"),
    ("WMT", "Walmart Inc."),
    ("PG", "Procter & Gamble Co."),
    ("MA", "Mastercard Inc."),
    ("UNH", "UnitedHealth Group Inc."),
    ("HD", "The Home Depot Inc."),
    ("DIS", "The Walt Disney Company"),
    ("BAC", "Bank of America Corp."),
    ("XOM", "Exxon Mobil Corporation"),
    ("PFE", "Pfizer Inc."),
    ("CSCO", "Cisco Systems Inc."),
    ("INTC", "Intel Corporation"),
    ("KO", "The Coca-Cola Company"),
    ("NFLX", "Netflix Inc."),
    ("CRM", "Salesforce Inc."),
    ("ABT", "Abbott Laboratories"),
    ("TMO", "Thermo Fisher Scientific Inc."),
    ("NKE", "Nike Inc."),
    ("MRK", "Merck & Co. Inc."),
    ("ORCL", "Oracle Corporation"),
    ("PEP", "PepsiCo Inc."),
    ("ACN", "Accenture plc"),
    ("LLY", "Eli Lilly and Company"),
    ("COST", "Costco Wholesale Corporation"),
    ("AVGO", "Broadcom Inc."),
    ("ADBE", "Adobe Inc."),
    ("AMD", "Advanced Micro Devices Inc."),
    ("QCOM", "Qualcomm Inc."),
    ("TXN", "Texas Instruments Inc."),
    ("PM", "Philip Morris International Inc."),
    ("NEE", "NextEra Energy Inc."),
    ("BMY", "Bristol-Myers Squibb Co."),
    ("UPS", "United Parcel Service Inc."),
    ("RTX", "RTX Corporation"),
    ("HON", "Honeywell International Inc."),
    ("LOW", "Lowe's Companies Inc."),
    ("AMGN", "Amgen Inc."),
    ("IBM", "International Business Machines Corp."),
    ("CAT", "Caterpillar Inc."),
    ("GE", "General Electric Company"),
    ("GS", "The Goldman Sachs Group Inc."),
    ("BLK", "BlackRock Inc."),
    ("PYPL", "PayPal Holdings Inc."),
    ("BA", "The Boeing Company"),
    ("SPGI", "S&P Global Inc."),
    ("ISRG", "Intuitive Surgical Inc."),
    ("AXP", "American Express Company"),
    ("PLTR", "Palantir Technologies Inc."),
    ("UBER", "Uber Technologies Inc."),
    ("SNOW", "Snowflake Inc."),
    ("XYZ", "Block Inc."),
    ("SOFI", "SoFi Technologies Inc."),
    ("RIVN", "Rivian Automotive Inc."),
    ("NIO", "NIO Inc."),
    ("COIN", "Coinbase Global Inc."),
    ("SHOP", "Shopify Inc."),
    ("SE", "Sea Limited"),
    ("BABA", "Alibaba Group Holding Ltd."),
    ("JD", "JD.com Inc."),
    ("PDD", "PDD Holdings Inc."),
    ("BIDU", "Baidu Inc."),
    ("TSM", "Taiwan Semiconductor"),
    ("ASML", "ASML Holding N.V."),
    ("NVO", "Novo Nordisk A/S"),
    ("AZN", "AstraZeneca PLC"),
    ("SAP", "SAP SE"),
    ("SHEL", "Shell plc"),
    ("BP", "BP plc"),
    ("COP", "ConocoPhillips"),
    ("CVX", "Chevron Corporation"),
    ("T", "AT&T Inc."),
    ("VZ", "Verizon Communications Inc."),
    ("WBD", "Warner Bros. Discovery Inc."),
    ("CMCSA", "Comcast Corporation"),
    ("NFLX", "Netflix Inc."),
    ("ROKU", "Roku Inc."),
    ("TTD", "The Trade Desk Inc."),
    ("SNAP", "Snap Inc."),
    ("PINS", "Pinterest Inc."),
    ("RDDT", "Reddit Inc."),
]

# ── Forex ─────────────────────────────────────────────────────────────────────
FOREX = [
    ("EUR/USD", "EURUSD=X", "Euro / US Dollar"),
    ("GBP/USD", "GBPUSD=X", "British Pound / US Dollar"),
    ("USD/JPY", "USDJPY=X", "US Dollar / Japanese Yen"),
    ("USD/CHF", "USDCHF=X", "US Dollar / Swiss Franc"),
    ("AUD/USD", "AUDUSD=X", "Australian Dollar / US Dollar"),
    ("NZD/USD", "NZDUSD=X", "New Zealand Dollar / US Dollar"),
    ("USD/CAD", "USDCAD=X", "US Dollar / Canadian Dollar"),
    ("EUR/GBP", "EURGBP=X", "Euro / British Pound"),
    ("EUR/JPY", "EURJPY=X", "Euro / Japanese Yen"),
    ("GBP/JPY", "GBPJPY=X", "British Pound / Japanese Yen"),
    ("AUD/JPY", "AUDJPY=X", "Australian Dollar / Japanese Yen"),
    ("CHF/JPY", "CHFJPY=X", "Swiss Franc / Japanese Yen"),
    ("EUR/CHF", "EURCHF=X", "Euro / Swiss Franc"),
    ("EUR/AUD", "EURAUD=X", "Euro / Australian Dollar"),
    ("GBP/AUD", "GBPAUD=X", "British Pound / Australian Dollar"),
    ("USD/CNY", "USDCNY=X", "US Dollar / Chinese Yuan"),
    ("USD/HKD", "USDHKD=X", "US Dollar / Hong Kong Dollar"),
    ("USD/SGD", "USDSGD=X", "US Dollar / Singapore Dollar"),
    ("USD/INR", "USDINR=X", "US Dollar / Indian Rupee"),
    ("USD/MXN", "USDMXN=X", "US Dollar / Mexican Peso"),
    ("USD/BRL", "USDBRL=X", "US Dollar / Brazilian Real"),
    ("USD/ZAR", "USDZAR=X", "US Dollar / South African Rand"),
    ("USD/TRY", "USDTRY=X", "US Dollar / Turkish Lira"),
    ("USD/SEK", "USDSEK=X", "US Dollar / Swedish Krona"),
    ("USD/NOK", "USDNOK=X", "US Dollar / Norwegian Krone"),
    ("USD/DKK", "USDDKK=X", "US Dollar / Danish Krone"),
    ("USD/PLN", "USDPLN=X", "US Dollar / Polish Zloty"),
    ("USD/CZK", "USDCZK=X", "US Dollar / Czech Koruna"),
    ("USD/HUF", "USDHUF=X", "US Dollar / Hungarian Forint"),
    ("USD/THB", "USDTHB=X", "US Dollar / Thai Baht"),
]

# ── Crypto ────────────────────────────────────────────────────────────────────
CRYPTO = [
    ("BTC", "BTC-USD", "Bitcoin"),
    ("ETH", "ETH-USD", "Ethereum"),
    ("BNB", "BNB-USD", "Binance Coin"),
    ("SOL", "SOL-USD", "Solana"),
    ("XRP", "XRP-USD", "Ripple"),
    ("ADA", "ADA-USD", "Cardano"),
    ("DOGE", "DOGE-USD", "Dogecoin"),
    ("AVAX", "AVAX-USD", "Avalanche"),
    ("DOT", "DOT-USD", "Polkadot"),
    ("LINK", "LINK-USD", "Chainlink"),
    ("MATIC", "MATIC-USD", "Polygon"),
    ("SHIB", "SHIB-USD", "Shiba Inu"),
    ("LTC", "LTC-USD", "Litecoin"),
    ("UNI", "UNI-USD", "Uniswap"),
    ("ATOM", "ATOM-USD", "Cosmos"),
    ("FIL", "FIL-USD", "Filecoin"),
    ("APT", "APT-USD", "Aptos"),
    ("ARB", "ARB-USD", "Arbitrum"),
    ("OP", "OP-USD", "Optimism"),
    ("NEAR", "NEAR-USD", "NEAR Protocol"),
    ("PEPE", "PEPE-USD", "Pepe"),
    ("SUI", "SUI-USD", "Sui"),
    ("SEI", "SEI-USD", "Sei"),
    ("INJ", "INJ-USD", "Injective"),
    ("TIA", "TIA-USD", "Celestia"),
    ("JUP", "JUP-USD", "Jupiter"),
    ("WIF", "WIF-USD", "dogwifhat"),
    ("RENDER", "RENDER-USD", "Render"),
    ("FET", "FET-USD", "Fetch.ai"),
    ("GRT", "GRT-USD", "The Graph"),
]


def _make_yfinance_symbol(display_symbol: str, asset_class: str) -> str:
    """Convert display symbol to yfinance ticker format."""
    if asset_class == "forex":
        return display_symbol.replace("/", "")
    if asset_class == "crypto":
        return f"{display_symbol}-USD"
    return display_symbol


class Command(BaseCommand):
    help = "Seed the database with stocks, forex pairs, and crypto assets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print assets without saving to DB.",
        )
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            help="Skip yfinance validation (faster).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_validation = options["skip_validation"]
        created_count = 0
        updated_count = 0
        skipped_count = 0

        all_assets = []

        for symbol, name in STOCKS:
            all_assets.append((symbol, symbol, name, "stock"))

        for symbol, yf_symbol, name in FOREX:
            all_assets.append((symbol, yf_symbol, name, "forex"))

        for symbol, yf_symbol, name in CRYPTO:
            all_assets.append((symbol, yf_symbol, name, "crypto"))

        self.stdout.write(f"Processing {len(all_assets)} assets...")

        for display_symbol, yf_symbol, name, asset_class in all_assets:
            if dry_run:
                self.stdout.write(f"  [DRY RUN] {display_symbol} ({yf_symbol}) — {name}")
                continue

            # Validate ticker unless skipping
            if not skip_validation:
                try:
                    ticker = yf.Ticker(yf_symbol)
                    info = ticker.fast_info
                    if info is None or info.get("lastPrice", 0) == 0:
                        self.stdout.write(
                            self.style.WARNING(f"  SKIP (invalid ticker): {yf_symbol}")
                        )
                        skipped_count += 1
                        continue
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"  SKIP (error validating {yf_symbol}): {e}")
                    )
                    skipped_count += 1
                    continue

            asset, created = Asset.objects.update_or_create(
                yfinance_symbol=yf_symbol,
                defaults={
                    "symbol": display_symbol,
                    "name": name,
                    "asset_class": asset_class,
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"  CREATED: {display_symbol}")
            else:
                updated_count += 1
                self.stdout.write(f"  UPDATED: {display_symbol}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}"
            )
        )
