"""
predict.py
----------
Loads the saved model and produces a live prediction for one ticker,
with a confidence threshold: weak signals are reported as "no clear signal"
rather than a false-confident up/down call.

Returns rich indicator context so the frontend can display technical analysis.

Run: python predict.py --ticker AAPL --horizon 5
"""
import argparse
import os
import sys
import joblib
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_DEFAULT_MODEL = os.path.join(_HERE, "model_artifact.joblib")

from data_loader import load_live
from features import build_feature_set, add_technical_indicators

CONFIDENCE_THRESHOLD = 0.06  # probability must be >0.56 or <0.44 to count as a real signal

# Map horizon labels used by the backend API to the day-counts the model
# was trained with (features.py `add_target` uses `horizon` in days).
HORIZON_DAYS = {
    "1d": 1,
    "5d": 5,
    "1mo": 22,
    "3mo": 66,
    "1y": 252,
}


def _interpret_rsi(rsi: float) -> str:
    if rsi >= 70:
        return "Overbought — potential reversal or pullback"
    elif rsi <= 30:
        return "Oversold — potential bounce or reversal"
    elif rsi >= 60:
        return "Bullish momentum"
    elif rsi <= 40:
        return "Bearish momentum"
    return "Neutral"


def _interpret_macd(hist: float, prev_hist: float) -> str:
    if hist > 0 and prev_hist <= 0:
        return "Bullish crossover — momentum shifting up"
    elif hist < 0 and prev_hist >= 0:
        return "Bearish crossover — momentum shifting down"
    elif hist > 0:
        return "Bullish momentum"
    elif hist < 0:
        return "Bearish momentum"
    return "Neutral"


def _interpret_stoch(k: float, d: float) -> str:
    if k >= 80 and d >= 80:
        return "Overbought — watch for bearish divergence"
    elif k <= 20 and d <= 20:
        return "Oversold — watch for bullish reversal"
    elif k > d:
        return "Bullish (%K above %D)"
    return "Bearish (%K below %D)"


def _interpret_adx(adx: float, plus_di: float, minus_di: float) -> str:
    if adx > 25:
        trend = "strong uptrend" if plus_di > minus_di else "strong downtrend"
        return f"Strong trend (ADX {adx:.0f}) — {trend}"
    elif adx > 20:
        return "Developing trend — watch for confirmation"
    return "Ranging market — no clear trend (ADX < 20)"


def _interpret_bb(bb_pct: float) -> str:
    if bb_pct > 1.0:
        return "Above upper band — overbought, potential mean reversion"
    elif bb_pct < 0.0:
        return "Below lower band — oversold, potential bounce"
    elif bb_pct > 0.8:
        return "Near upper band"
    elif bb_pct < 0.2:
        return "Near lower band"
    return "Mid-range"


def predict(ticker: str, model_path=_DEFAULT_MODEL, horizon=5, threshold=0.005):
    if isinstance(horizon, str):
        horizon = HORIZON_DAYS.get(horizon, 5)

    artifact = joblib.load(model_path)
    model, feature_columns = artifact["model"], artifact["feature_columns"]

    df = load_live(ticker, start="2023-01-01")
    X, _, _, full_df = build_feature_set(df, horizon=horizon, threshold=threshold)
    X = X.reindex(columns=feature_columns)

    latest_row = X.iloc[[-1]]
    prob_up = float(model.predict_proba(latest_row)[0][1])

    distance_from_neutral = abs(prob_up - 0.5)
    has_signal = distance_from_neutral >= CONFIDENCE_THRESHOLD

    # Compute full indicator set for context
    enriched = add_technical_indicators(df)
    latest = enriched.iloc[-1]
    prev = enriched.iloc[-2] if len(enriched) > 1 else latest

    indicators = {
        "rsi_14": round(float(latest.get("rsi_14", 0)), 1),
        "rsi_interpretation": _interpret_rsi(float(latest.get("rsi_14", 50))),
        "macd_hist": round(float(latest.get("macd_hist", 0)), 4),
        "macd_interpretation": _interpret_macd(
            float(latest.get("macd_hist", 0)),
            float(prev.get("macd_hist", 0)),
        ),
        "stoch_k": round(float(latest.get("stoch_k_14", 50)), 1),
        "stoch_d": round(float(latest.get("stoch_d_14", 50)), 1),
        "stoch_interpretation": _interpret_stoch(
            float(latest.get("stoch_k_14", 50)),
            float(latest.get("stoch_d_14", 50)),
        ),
        "adx": round(float(latest.get("adx_14", 20)), 1),
        "plus_di": round(float(latest.get("plus_di_14", 0)), 1),
        "minus_di": round(float(latest.get("minus_di_14", 0)), 1),
        "adx_interpretation": _interpret_adx(
            float(latest.get("adx_14", 20)),
            float(latest.get("plus_di_14", 0)),
            float(latest.get("minus_di_14", 0)),
        ),
        "bb_pct": round(float(latest.get("bb_pct", 0.5)), 2),
        "bb_interpretation": _interpret_bb(float(latest.get("bb_pct", 0.5))),
        "price_vs_sma10": round(float(latest.get("price_vs_sma10", 0)) * 100, 2),
        "price_vs_sma50": round(float(latest.get("price_vs_sma50", 0)) * 100, 2),
        "atr_14": round(float(latest.get("atr_14", 0)), 4),
        "htf_aligned": bool(latest.get("htf_aligned", 0)),
        "htf_weekly_trend": "UP" if latest.get("htf_weekly_trend", 0) == 1 else "DOWN",
        "htf_daily_trend": "UP" if latest.get("htf_daily_trend", 0) == 1 else "DOWN",
        "fib_382_dist": round(float(latest.get("fib_382_dist", 0)), 3),
        "fib_618_dist": round(float(latest.get("fib_618_dist", 0)), 3),
        "pattern_doji": bool(latest.get("pattern_doji", 0)),
        "pattern_hammer": bool(latest.get("pattern_hammer", 0)),
        "pattern_engulfing_bull": bool(latest.get("pattern_engulfing_bull", 0)),
        "pattern_engulfing_bear": bool(latest.get("pattern_engulfing_bear", 0)),
        "pattern_shooting_star": bool(latest.get("pattern_shooting_star", 0)),
    }

    # Build human-readable summary
    summary_parts = []
    summary_parts.append(f"RSI: {indicators['rsi_14']} ({indicators['rsi_interpretation']})")
    summary_parts.append(f"MACD: {indicators['macd_interpretation']}")
    summary_parts.append(f"ADX: {indicators['adx_interpretation']}")
    summary_parts.append(f"Stochastic: {indicators['stoch_interpretation']}")
    summary_parts.append(f"Bollinger: {indicators['bb_interpretation']}")
    if indicators["htf_aligned"]:
        summary_parts.append(f"Multi-TF: Aligned {indicators['htf_daily_trend']} (weekly {indicators['htf_weekly_trend']})")
    else:
        summary_parts.append(f"Multi-TF: Divergent — daily {indicators['htf_daily_trend']}, weekly {indicators['htf_weekly_trend']}")

    # Candlestick patterns
    patterns_found = []
    if indicators["pattern_doji"]:
        patterns_found.append("Doji")
    if indicators["pattern_hammer"]:
        patterns_found.append("Hammer")
    if indicators["pattern_engulfing_bull"]:
        patterns_found.append("Bullish Engulfing")
    if indicators["pattern_engulfing_bear"]:
        patterns_found.append("Bearish Engulfing")
    if indicators["pattern_shooting_star"]:
        patterns_found.append("Shooting Star")
    if patterns_found:
        summary_parts.append(f"Patterns: {', '.join(patterns_found)}")
    else:
        summary_parts.append("Patterns: None detected")

    return {
        "ticker": ticker,
        "as_of_date": str(full_df.index[-1].date()),
        "last_close": float(full_df["Close"].iloc[-1]),
        "probability_up": round(prob_up, 4),
        "probability_down": round(1 - prob_up, 4),
        "has_clear_signal": has_signal,
        "call": ("UP" if prob_up > 0.5 else "DOWN") if has_signal else "NO CLEAR SIGNAL",
        "confidence": round(prob_up if prob_up > 0.5 else 1 - prob_up, 4),
        "indicators": indicators,
        "summary": "\n".join(summary_parts),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, required=True)
    parser.add_argument("--horizon", type=int, default=5)
    args = parser.parse_args()
    result = predict(args.ticker, horizon=args.horizon)
    print(f"\n{'='*50}")
    print(f"Prediction: {result['call']} (confidence: {result['confidence']})")
    print(f"{'='*50}")
    print(f"Last close: {result['last_close']}")
    print(f"Probability UP: {result['probability_up']}")
    print(f"Probability DOWN: {result['probability_down']}")
    print(f"\n{result['summary']}")
