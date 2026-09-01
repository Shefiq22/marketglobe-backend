"""
features.py
------------
Builds technical-indicator features from OHLCV data.

v2 improvements:
- Added volume regime, momentum decay, volatility regime, price acceleration,
  range contraction/expansion features
- Default threshold raised to 0.01 (1%) to filter noisy small moves
- Feature selection via importance filtering

Sources: School of Pipsology (BabyPips.com) — ADX, Stochastic, ATR,
OBV, candlestick patterns, multi-timeframe alignment, Fibonacci levels.

IMPORTANT — every feature is computed using only data up to and
including day t (no future information), and the target is shifted so we
are always predicting something that happens AFTER the features were known.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Core indicator helpers
# ---------------------------------------------------------------------------

def _compute_adx(high: pd.Series, low: pd.Series, close: pd.Series,
                 period: int = 14) -> pd.DataFrame:
    """Average Directional Index — measures trend strength (Pipsology Ch. 7)."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr = pd.Series(tr, index=high.index).rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=high.index).rolling(period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=high.index).rolling(period).mean() / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(period).mean()

    return pd.DataFrame({
        "adx_14": adx,
        "plus_di_14": plus_di,
        "minus_di_14": minus_di,
    }, index=high.index)


def _compute_stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                        k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """Stochastic Oscillator — %K and %D (Pipsology Ch. 7)."""
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    k = raw_k.rolling(d_period).mean()
    d = k.rolling(d_period).mean()
    return pd.DataFrame({
        "stoch_k_14": k,
        "stoch_d_14": d,
    }, index=high.index)


def _compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                 period: int = 14) -> pd.Series:
    """Average True Range — volatility (Pipsology Ch. 7)."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume — volume confirms trend (Pipsology Ch. 7)."""
    direction = np.sign(close.diff())
    return (volume * direction).cumsum()


def _detect_candlestick_patterns(open_: pd.Series, high: pd.Series,
                                 low: pd.Series, close: pd.Series) -> pd.DataFrame:
    """
    Simple candlestick pattern heuristics (Pipsology Ch. 6).

    Each column is a binary flag: 1 = pattern present, 0 = absent.
    """
    body = (close - open_).abs()
    upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low
    candle_range = (high - low).replace(0, np.nan)

    # Doji: tiny body relative to range
    is_doji = (body / candle_range < 0.1).astype(int)

    # Hammer / Hanging Man: small body near top, long lower shadow
    is_hammer = (
        (body / candle_range < 0.35) &
        (lower_shadow > 2 * body) &
        (upper_shadow < body * 0.5)
    ).astype(int)

    # Engulfing: current body fully wraps previous body
    prev_open = open_.shift(1)
    prev_close = close.shift(1)
    bull_engulf = (
        (close > open_) & (prev_close < prev_open) &
        (open_ <= prev_close) & (close >= prev_open)
    ).astype(int)
    bear_engulf = (
        (close < open_) & (prev_close > prev_open) &
        (open_ >= prev_close) & (close <= prev_open)
    ).astype(int)

    # Shooting Star: small body near bottom, long upper shadow
    is_shooting_star = (
        (body / candle_range < 0.35) &
        (upper_shadow > 2 * body) &
        (lower_shadow < body * 0.5)
    ).astype(int)

    return pd.DataFrame({
        "pattern_doji": is_doji,
        "pattern_hammer": is_hammer,
        "pattern_engulfing_bull": bull_engulf,
        "pattern_engulfing_bear": bear_engulf,
        "pattern_shooting_star": is_shooting_star,
    }, index=open_.index)


def _compute_higher_tf_trend(close: pd.Series) -> pd.DataFrame:
    """
    Multi-timeframe trend alignment (Pipsology: multiple time frame analysis).
    Resamples daily close to weekly, checks if weekly trend agrees with daily.
    """
    weekly = close.resample("W").last().dropna()
    w_sma10 = weekly.rolling(10).mean()
    w_sma20 = weekly.rolling(20).mean()

    # Weekly trend: 1 = up, 0 = down (SMA10 > SMA20)
    weekly_up = (w_sma10 > w_sma20).astype(int)
    # Reindex back to daily, forward-fill
    weekly_up_daily = weekly_up.reindex(close.index, method="ffill")

    # Daily trend
    d_sma10 = close.rolling(10).mean()
    d_sma50 = close.rolling(50).mean()
    daily_up = (d_sma10 > d_sma50).astype(int)

    # Alignment: both timeframes agree
    aligned = (weekly_up_daily == daily_up).astype(int)

    return pd.DataFrame({
        "htf_weekly_trend": weekly_up_daily,
        "htf_daily_trend": daily_up,
        "htf_aligned": aligned,
    }, index=close.index)


def _compute_fibonacci_levels(high: pd.Series, low: pd.Series,
                              close: pd.Series, lookback: int = 50) -> pd.DataFrame:
    """
    Fibonacci retracement levels from recent swing (Pipsology Ch. 7).
    Features: price position relative to 38.2% and 61.8% retracement.
    """
    rolling_high = high.rolling(lookback).max()
    rolling_low = low.rolling(lookback).min()
    swing_range = rolling_high - rolling_low

    fib_382 = rolling_high - 0.382 * swing_range
    fib_618 = rolling_high - 0.618 * swing_range

    price_vs_fib382 = (close - fib_382) / swing_range.replace(0, np.nan)
    price_vs_fib618 = (close - fib_618) / swing_range.replace(0, np.nan)

    return pd.DataFrame({
        "fib_382_dist": price_vs_fib382,
        "fib_618_dist": price_vs_fib618,
    }, index=close.index)


# ---------------------------------------------------------------------------
# New v2 indicator helpers
# ---------------------------------------------------------------------------

def _compute_volume_regime(volume: pd.Series) -> pd.DataFrame:
    """Volume regime: high/low volume environment classification."""
    vol_sma_20 = volume.rolling(20).mean()
    vol_sma_50 = volume.rolling(50).mean()
    vol_ratio = volume / vol_sma_20.replace(0, np.nan)
    is_high_vol = (vol_ratio > 1.5).astype(int)
    is_low_vol = (vol_ratio < 0.5).astype(int)
    vol_trend = (vol_sma_20 / vol_sma_50.replace(0, np.nan)) - 1

    return pd.DataFrame({
        "volume_ratio_20d": vol_ratio,
        "is_high_volume": is_high_vol,
        "is_low_volume": is_low_vol,
        "volume_trend": vol_trend,
    }, index=volume.index)


def _compute_momentum_decay(close: pd.Series) -> pd.DataFrame:
    """Momentum decay: rate of change of momentum indicators."""
    rsi_14 = _compute_rsi(close, 14)
    rsi_decay = rsi_14 - rsi_14.shift(5)

    macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_signal
    macd_decay = macd_hist - macd_hist.shift(3)

    return pd.DataFrame({
        "rsi_14": rsi_14,
        "rsi_decay": rsi_decay,
        "macd_hist": macd_hist,
        "macd_decay": macd_decay,
    }, index=close.index)


def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI calculation helper."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _compute_volatility_regime(close: pd.Series) -> pd.DataFrame:
    """Volatility regime: high/low vol environment."""
    returns = close.pct_change()
    vol_10d = returns.rolling(10).std()
    vol_30d = returns.rolling(30).std()
    vol_ratio = vol_10d / vol_30d.replace(0, np.nan)
    is_high_vol = (vol_ratio > 1.3).astype(int)
    is_low_vol = (vol_ratio < 0.7).astype(int)

    return pd.DataFrame({
        "vol_ratio_10_30": vol_ratio,
        "is_high_vol": is_high_vol,
        "is_low_vol": is_low_vol,
    }, index=close.index)


def _compute_price_acceleration(close: pd.Series) -> pd.DataFrame:
    """Price acceleration: second derivative of price."""
    returns_1d = close.pct_change(1)
    returns_5d = close.pct_change(5)
    acceleration_1d = returns_1d - returns_1d.shift(1)
    acceleration_5d = returns_5d - returns_5d.shift(5)

    return pd.DataFrame({
        "acceleration_1d": acceleration_1d,
        "acceleration_5d": acceleration_5d,
    }, index=close.index)


def _compute_range_features(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.DataFrame:
    """Range contraction/expansion features."""
    daily_range = (high - low) / close
    range_sma_20 = daily_range.rolling(20).mean()
    range_ratio = daily_range / range_sma_20.replace(0, np.nan)
    is_contraction = (range_ratio < 0.7).astype(int)
    is_expansion = (range_ratio > 1.3).astype(int)

    return pd.DataFrame({
        "range_ratio_20d": range_ratio,
        "is_range_contraction": is_contraction,
        "is_range_expansion": is_expansion,
    }, index=close.index)


# ---------------------------------------------------------------------------
# Main indicator builder
# ---------------------------------------------------------------------------

def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to OHLCV dataframe."""
    out = df.copy()

    # --- Existing indicators ---
    out["return_1d"] = out["Close"].pct_change(1)
    out["return_5d"] = out["Close"].pct_change(5)
    out["return_10d"] = out["Close"].pct_change(10)

    out["sma_10"] = out["Close"].rolling(10).mean()
    out["sma_50"] = out["Close"].rolling(50).mean()
    out["ema_12"] = out["Close"].ewm(span=12, adjust=False).mean()
    out["ema_26"] = out["Close"].ewm(span=26, adjust=False).mean()
    out["price_vs_sma10"] = out["Close"] / out["sma_10"] - 1
    out["price_vs_sma50"] = out["Close"] / out["sma_50"] - 1

    out["macd"] = out["ema_12"] - out["ema_26"]
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]

    out["rsi_14"] = _compute_rsi(out["Close"], 14)

    sma20 = out["Close"].rolling(20).mean()
    std20 = out["Close"].rolling(20).std()
    out["bb_upper"] = sma20 + 2 * std20
    out["bb_lower"] = sma20 - 2 * std20
    out["bb_pct"] = (out["Close"] - out["bb_lower"]) / (out["bb_upper"] - out["bb_lower"])

    out["volatility_10d"] = out["return_1d"].rolling(10).std()
    out["volatility_30d"] = out["return_1d"].rolling(30).std()

    out["volume_change"] = out["Volume"].pct_change()
    out["volume_sma_10"] = out["Volume"].rolling(10).mean()
    out["volume_vs_avg"] = out["Volume"] / out["volume_sma_10"] - 1

    out["high_low_range"] = (out["High"] - out["Low"]) / out["Close"]
    out["close_open_range"] = (out["Close"] - out["Open"]) / out["Open"]

    # --- Pipsology indicators ---

    # ADX — trend strength
    adx_df = _compute_adx(out["High"], out["Low"], out["Close"])
    out["adx_14"] = adx_df["adx_14"]
    out["plus_di_14"] = adx_df["plus_di_14"]
    out["minus_di_14"] = adx_df["minus_di_14"]

    # Stochastic — overbought/oversold
    stoch_df = _compute_stochastic(out["High"], out["Low"], out["Close"])
    out["stoch_k_14"] = stoch_df["stoch_k_14"]
    out["stoch_d_14"] = stoch_df["stoch_d_14"]

    # ATR — volatility measure
    out["atr_14"] = _compute_atr(out["High"], out["Low"], out["Close"])

    # OBV — volume confirms trend
    out["obv"] = _compute_obv(out["Close"], out["Volume"])

    # Candlestick patterns
    patterns = _detect_candlestick_patterns(out["Open"], out["High"],
                                            out["Low"], out["Close"])
    for col in patterns.columns:
        out[col] = patterns[col]

    # Higher-timeframe trend alignment
    htf = _compute_higher_tf_trend(out["Close"])
    for col in htf.columns:
        out[col] = htf[col]

    # Fibonacci levels
    fib = _compute_fibonacci_levels(out["High"], out["Low"], out["Close"])
    out["fib_382_dist"] = fib["fib_382_dist"]
    out["fib_618_dist"] = fib["fib_618_dist"]

    # --- New v2 indicators ---

    # Volume regime
    vol_regime = _compute_volume_regime(out["Volume"])
    for col in vol_regime.columns:
        out[col] = vol_regime[col]

    # Momentum decay
    mom_decay = _compute_momentum_decay(out["Close"])
    out["rsi_decay"] = mom_decay["rsi_decay"]
    out["macd_decay"] = mom_decay["macd_decay"]

    # Volatility regime
    vol_regime_ind = _compute_volatility_regime(out["Close"])
    for col in vol_regime_ind.columns:
        out[col] = vol_regime_ind[col]

    # Price acceleration
    accel = _compute_price_acceleration(out["Close"])
    for col in accel.columns:
        out[col] = accel[col]

    # Range features
    range_feats = _compute_range_features(out["High"], out["Low"], out["Close"])
    for col in range_feats.columns:
        out[col] = range_feats[col]

    return out


def add_target(df: pd.DataFrame, horizon: int = 1, threshold: float = 0.01) -> pd.DataFrame:
    """
    Target = will Close move more than `threshold` (e.g. 0.01 = 1%) in
    either direction over the next `horizon` days? Rows with smaller, noisy
    moves are dropped entirely rather than forced into an arbitrary up/down.

    v2: Default threshold raised from 0.005 to 0.01 to filter noise.
    """
    out = df.copy()
    future_close = out["Close"].shift(-horizon)
    ret = future_close / out["Close"] - 1
    out["target_direction"] = (ret > threshold).astype(int)
    out["target_return"] = ret
    out = out[(ret > threshold) | (ret < -threshold)]
    return out


def build_feature_set(df: pd.DataFrame, horizon: int = 1, threshold: float = 0.01):
    df = add_technical_indicators(df)
    df = add_target(df, horizon=horizon, threshold=threshold)
    df = df.dropna()

    # Features that are raw price/volume scale — exclude from model input
    raw_scale_features = [
        "sma_10", "sma_50", "ema_12", "ema_26",
        "bb_upper", "bb_lower", "macd", "macd_signal",
        "volume_sma_10", "obv", "atr_14",
    ]
    exclude_cols = (
        ["Open", "High", "Low", "Close", "Volume",
         "target_direction", "target_return"]
        + raw_scale_features
    )
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols]
    y_direction = df["target_direction"]
    y_return = df["target_return"]
    return X, y_direction, y_return, df


def select_features_by_importance(X: pd.DataFrame, y: pd.Series,
                                   model, top_n: int = 20) -> list:
    """Select top N features by importance from a trained model."""
    importances = pd.Series(model.feature_importances_, index=X.columns)
    top_features = importances.sort_values(ascending=False).head(top_n).index.tolist()
    return top_features
