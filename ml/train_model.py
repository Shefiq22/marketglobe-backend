"""
train_model.py
---------------
Trains and evaluates a direction-prediction model with PROPER time-series
validation, then saves a final production model to disk.

Enhanced with multi-asset training (stocks + forex + crypto) for better
generalisation across market types.

Run:
    python train_model.py --ticker AAPL --start 2015-01-01
    python train_model.py --tickers AAPL,XOM,JPM,BTC-USD,GLD --start 2015-01-01 --horizon 5
    python train_model.py --multi --horizon 5          # trains on 12 diverse assets
    python train_model.py --csv /path/to/kaggle_file.csv
"""

import argparse
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, confusion_matrix, r2_score)
from xgboost import XGBClassifier, XGBRegressor

from data_loader import load_from_kaggle_csv, load_live
from features import build_feature_set

# Diverse set: stocks (tech, energy, finance, consumer), forex, crypto, commodity
MULTI_ASSET_TICKERS = [
    # Stocks
    "AAPL", "MSFT", "TSLA", "JPM", "XOM",
    # Forex
    "EURUSD=X", "GBPUSD=X", "USDJPY=X",
    # Crypto
    "BTC-USD", "ETH-USD",
    # Commodity ETF
    "GLD", "USO",
]


def _make_model(y_train):
    """Build an XGBoost classifier tuned to the training fold.

    - `scale_pos_weight` corrects imbalanced up/down classes so the model
      doesn't just predict the majority class (a silent accuracy killer).
    - Early stopping against a hold-out slice of the training fold prevents
      overfitting, which is what produced the sub-baseline 44% result above.
    """
    pos_count = int(y_train.sum())
    neg_count = int((1 - y_train).sum())
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0

    return XGBClassifier(
        n_estimators=1000,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight,
        early_stopping_rounds=50,
        random_state=42,
    )


def walk_forward_evaluate(X, y, n_splits=5):
    """
    TimeSeriesSplit: each fold trains only on the PAST and tests on the
    FUTURE relative to that fold. No shuffling. No peeking. This is the
    only honest way to validate a time-series model.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_metrics = []

    for fold, (train_idx, test_idx) in enumerate(tscv.split(X), 1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        model = _make_model(y_train)

        # Hold out the last 15% of the training fold for early stopping.
        cutoff = int(len(X_train) * 0.85)
        X_fit, X_val = X_train.iloc[:cutoff], X_train.iloc[cutoff:]
        y_fit, y_val = y_train.iloc[:cutoff], y_train.iloc[cutoff:]

        model.fit(
            X_fit, y_fit,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        preds = model.predict(X_test)

        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        baseline = max(y_test.mean(), 1 - y_test.mean())

        fold_metrics.append(dict(fold=fold, accuracy=acc, precision=prec,
                                  recall=rec, f1=f1, naive_baseline=baseline,
                                  test_size=len(y_test)))

        print(f"Fold {fold}: accuracy={acc:.3f} | precision={prec:.3f} | "
              f"recall={rec:.3f} | f1={f1:.3f} | naive baseline={baseline:.3f}")

    return pd.DataFrame(fold_metrics), model


def demonstrate_the_fake_99_percent_trap(df):
    """
    Trains a REGRESSION model to predict tomorrow's raw closing price and
    reports R^2, to show why that metric is misleading for this problem.
    """
    df = df.copy()
    df["next_close"] = df["Close"].shift(-1)
    df = df.dropna()

    split = int(len(df) * 0.8)
    X = df[["Close"]].iloc[:split], df[["Close"]].iloc[split:]
    y = df["next_close"].iloc[:split], df["next_close"].iloc[split:]

    model = XGBRegressor(n_estimators=200, max_depth=3, random_state=42)
    model.fit(X[0], y[0])
    preds = model.predict(X[1])
    fake_r2 = r2_score(y[1], preds)

    naive_preds = X[1]["Close"].values
    naive_r2 = r2_score(y[1], naive_preds)

    print("\n--- WHY 'R2 = 0.99' ON PRICE PREDICTION IS MISLEADING ---")
    print(f"XGBoost regressor R^2 on next-day raw price: {fake_r2:.4f}")
    print(f"Naive 'tomorrow = today' R^2 (zero intelligence): {naive_r2:.4f}")
    print("These two numbers are nearly identical. The model isn't predicting")
    print("the future -- it's just tracking the price's natural autocorrelation.")
    print("This is the trap behind most '94-99% accurate' market predictors you'll")
    print("see advertised. Direction/return prediction (above) is the honest metric.")


def train_and_save_final_model(X, y, path="model_artifact.joblib"):
    """
    Trains one final model on ALL available data (the folds above were only
    for honest evaluation) and saves it to disk along with the exact
    feature column order, so predict.py can load it later.
    """
    final_model = _make_model(y)

    # Use the full training set for the final model (early stopping needs a
    # validation slice, retained only to protect the fold models above).
    cutoff = int(len(X) * 0.85)
    final_model.fit(
        X, y,
        eval_set=[(X.iloc[cutoff:], y.iloc[cutoff:])],
        verbose=False,
    )
    joblib.dump({"model": final_model, "feature_columns": list(X.columns)}, path)
    print(f"\nSaved final production model to {path}")
    return final_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, default=None, help="e.g. AAPL, BTC-USD, EURUSD=X")
    parser.add_argument("--tickers", type=str, default=None,
                         help="comma-separated list, e.g. AAPL,XOM,JPM,BTC-USD,GLD")
    parser.add_argument("--multi", action="store_true",
                         help="train on diverse set of 12 stocks+forex+crypto assets")
    parser.add_argument("--csv", type=str, default=None, help="path to Kaggle CSV instead of live download")
    parser.add_argument("--start", type=str, default="2015-01-01")
    parser.add_argument("--horizon", type=int, default=1, help="days ahead to predict")
    parser.add_argument("--threshold", type=float, default=0.005,
                         help="minimum move (e.g. 0.005 = 0.5%%) to count as a real signal")
    args = parser.parse_args()

    if args.multi or args.tickers:
        if args.multi:
            ticker_list = MULTI_ASSET_TICKERS
            print(f"Multi-asset mode: training on {len(ticker_list)} assets\n")
        else:
            ticker_list = [t.strip() for t in args.tickers.split(",")]

        all_X, all_y, full_df = [], [], None
        for t in ticker_list:
            print(f"Loading {t}...")
            try:
                df = load_live(t, start=args.start)
                Xi, yi, _, full_i = build_feature_set(df, horizon=args.horizon, threshold=args.threshold)
                all_X.append(Xi)
                all_y.append(yi)
                if full_df is None:
                    full_df = full_i
            except Exception as e:
                print(f"  Skipping {t}: {e}")

        X = pd.concat(all_X).reset_index(drop=True)
        y_direction = pd.concat(all_y).reset_index(drop=True)
        print(f"\nCombined {len(all_X)} assets: {X.shape[0]} rows x {X.shape[1]} features")

    else:
        if args.csv:
            raw = load_from_kaggle_csv(args.csv)
        elif args.ticker:
            raw = load_live(args.ticker, start=args.start)
        else:
            print("No --csv/--ticker/--tickers/--multi given, defaulting to the bundled "
                  "real sample dataset so this runs immediately with zero setup.")
            raw = load_from_kaggle_csv("sample_dataset_AAPL.csv")

        print(f"Loaded {len(raw)} rows from {raw.index.min().date()} to {raw.index.max().date()}\n")
        X, y_direction, y_return, full_df = build_feature_set(raw, horizon=args.horizon, threshold=args.threshold)
        print(f"Feature matrix: {X.shape[0]} rows x {X.shape[1]} features")

    print(f"Class balance (up=1): {y_direction.mean():.3f}\n")

    print("=== Walk-forward validated DIRECTION prediction (the honest metric) ===")
    results, last_model = walk_forward_evaluate(X, y_direction, n_splits=5)

    print("\n=== Summary across folds ===")
    print(results[["accuracy", "precision", "recall", "f1", "naive_baseline"]].mean().round(3))

    print("\n=== Top 15 most important features ===")
    importances = pd.Series(last_model.feature_importances_, index=X.columns)
    print(importances.sort_values(ascending=False).head(15).round(4))

    demonstrate_the_fake_99_percent_trap(full_df)

    results.to_csv("walk_forward_results.csv", index=False)
    print("\nSaved fold-by-fold results to walk_forward_results.csv")

    train_and_save_final_model(X, y_direction)


if __name__ == "__main__":
    main()
