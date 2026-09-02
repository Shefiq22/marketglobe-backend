"""Lightweight lexicon-based news sentiment + related-symbol extraction.

No external ML/NLP dependency: we score headlines/summaries against a small
financial word list and classify as positive/negative/neutral. This keeps the
app self-contained while giving the frontend a useful sentiment signal and
letting news items point at related tickers.
"""
import re

BULLISH_WORDS = {
    "beat", "beats", "surge", "surges", "surged", "rally", "rallies", "rallying",
    "gain", "gains", "gained", "jump", "jumps", "jumped", "soar", "soars", "soared",
    "record", "boom", "rising", "rise", "rises", "rose", "outperform", "upgrade",
    "upgrades", "upgraded", "bullish", "buy", "buying", "strong", "stronger",
    "growth", "growing", "profit", "profits", "profitability", "positive",
    "higher", "top", "outlook", "optimistic", "momentum", "rocket", "breakout",
    "breakthrough", "adoption", "expand", "expansion", "expansionary", "boost",
    "boosts", "boosting", "win", "wins", "winner", "recovery", "rebound",
    "upgraded", "initiate", "initiates", "outperform", "overweight", "dividend",
    "dividends", "buyback", "stock buyback", "earnings beat", "revenue beat",
    "guidance", "raised guidance", "partnership",
}

BEARISH_WORDS = {
    "plunge", "plunges", "plunged", "crash", "crashes", "crashed", "slump",
    "slumps", "slumped", "drop", "drops", "dropped", "decline", "declines",
    "declined", "fall", "falls", "fell", "downgrade", "downgrades", "downgraded",
    "bearish", "sell", "selling", "weak", "weaker", "loss", "losses", "negative",
    "lower", "concern", "concerns", "worries", "fear", "fears", "selloff",
    "sell-off", "correction", "recession", "inflation", "rate hike", "layoffs",
    "lay off", "lawsuit", "legal action", "fine", "penalty", "halts", "halt",
    "suspend", "suspension", "fraud", "investigation", "probe", "warn", "warns",
    "warning", "cut", "cuts", "cutting", "miss", "misses", "missed", "slashes",
    "slashed", "underperform", "underweight", "neutral", "caution", "bearish",
    "downturn", "slowdown", "slowing", "default", "bankruptcy", "bankrupt",
    "recall", "recalls", "shortfall", "avert", "risk", "risks", "volatility",
}

NEGATION_WORDS = {"not", "no", "never", "without", "unlikely", "warns against"}


def _tokens(text):
    return re.findall(r"[a-z][a-z'-]*", (text or "").lower())


def score_sentiment(text):
    """Return a dict with sentiment label and scores for the given text."""
    words = _tokens(text)
    bullish = 0
    bearish = 0

    bullish_phrases = {"earnings beat", "revenue beat", "raised guidance", "stock buyback"}
    bearish_phrases = {"rate hike", "lay off", "legal action", "sell-off"}

    lowered = (text or "").lower()
    for phrase in bullish_phrases:
        if phrase in lowered:
            bullish += 2
    for phrase in bearish_phrases:
        if phrase in lowered:
            bearish += 2

    idx = 0
    while idx < len(words):
        word = words[idx]
        negated = False
        if idx > 0 and words[idx - 1] in NEGATION_WORDS:
            negated = True

        if word in BULLISH_WORDS:
            if negated:
                bearish += 1
            else:
                bullish += 1
        elif word in BEARISH_WORDS:
            if negated:
                bullish += 1
            else:
                bearish += 1
        idx += 1

    if bullish > bearish:
        label = "positive"
        score = min(1.0, bullish / max(bearish + bullish, 1) + 0.1)
    elif bearish > bullish:
        label = "negative"
        score = min(1.0, bearish / max(bearish + bullish, 1) + 0.1)
    else:
        label = "neutral"
        score = 0.5

    return {
        "label": label,
        "positive_score": bullish,
        "negative_score": bearish,
        "score": round(score, 2),
    }


_related_cache = None


def extract_related_symbols(headline, asset=None):
    """Return a list of related asset symbols mentioned in a headline.

    Matches exact ticker tokens (e.g. AAPL, TSLA) and company names drawn from
    the Asset table (cached per-process). Optionally excludes the given `asset`.
    """
    global _related_cache
    if _related_cache is None:
        from assets.models import Asset
        _related_cache = [
            (a.yfinance_symbol, a.name) for a in Asset.objects.filter(
                is_active=True, is_delisted=False
            )
        ]

    text_lower = (headline or "").lower()
    found = []
    for sym, name in _related_cache:
        if not sym:
            continue
        if asset is not None and sym == asset.yfinance_symbol:
            continue
        sym_token = sym.split("=")[0].split("^")[0].split("-")[0]
        if not sym_token or len(sym_token) < 1:
            continue
        # Skip generic single letters (e.g. 'C' would be too noisy).
        if len(sym_token) == 1:
            continue
        if re.search(rf"\b{re.escape(sym_token.lower())}\b", text_lower):
            found.append(sym)
            continue
        # Also match the company name as multiple words.
        if name and len(name) > 2:
            name_lower = name.lower()
            if re.search(rf"\b{re.escape(name_lower)}\b", text_lower):
                found.append(sym)

    return found[:6]
