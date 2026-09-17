"""ML model — self-learning gradient-boosted classifier for trade direction.

Trains on historical candles + indicator features labeled by forward return.
Retrains nightly via APScheduler; supports incremental updates.

Safety:
- Proper train/test holdout (no train-acc-as-val overfitting)
- Symbol guard: predict() refuses to predict a symbol the model wasn't trained on
- Version backup before each retrain (rollback path)
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from indicators import atr, ema, rsi, macd
from mt5_service import candles

log = logging.getLogger("ml")

MODEL_PATH = Path("models/trade_classifier.joblib")
BACKUP_DIR = Path("models/backups")

FEATURES = ["ema_20", "ema_50", "rsi_14", "atr_14", "macd", "macd_signal",
            "ret_1", "ret_3", "ret_5", "vol_5"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema_20"] = ema(df, 20)
    df["ema_50"] = ema(df, 50)
    df["rsi_14"] = rsi(df, 14)
    df["atr_14"] = atr(df, 14)
    m, sig, _ = macd(df)
    df["macd"] = m
    df["macd_signal"] = sig
    for p in (1, 3, 5):
        df[f"ret_{p}"] = df["close"].pct_change(p)
    df["vol_5"] = df["close"].pct_change().rolling(5).std()
    return df


def label(df: pd.DataFrame, horizon=5, threshold=0.0008) -> pd.Series:
    """Forward return label: 1 up, -1 down, 0 flat. Window [t, t+horizon]
    does not overlap with causal features (which use data <= t)."""
    fwd = df["close"].shift(-horizon) / df["close"] - 1
    return pd.Series(np.where(fwd > threshold, 1, np.where(fwd < -threshold, -1, 0)),
                     index=df.index)


def train(symbol: str = "EURUSD", tf: str = "H1", count: int = 3000):
    """Train (or retrain) the classifier with a proper train/test holdout.

    CPU-bound — callers in async context should use ``asyncio.to_thread``.
    """
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    from xgboost import XGBClassifier
    rates = candles(symbol, tf, count)
    if not rates:
        log.warning("no candles to train on")
        return
    df = pd.DataFrame(rates)
    df = build_features(df)
    df["label"] = label(df)
    df = df.dropna()
    if len(df) < 200:
        log.warning("insufficient data to train (%d rows)", len(df))
        return

    # ---- holdout split: last 20% as test set (chronological, no shuffle) ----
    split = int(len(df) * 0.8)
    train_df, test_df = df.iloc[:split], df.iloc[split:]
    X_train, y_train = train_df[FEATURES].values, train_df["label"].values
    X_test, y_test = test_df[FEATURES].values, test_df["label"].values

    clf = XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="mlogloss",
        n_jobs=-1,
    )
    clf.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    train_acc = clf.score(X_train, y_train)
    test_acc = clf.score(X_test, y_test)
    log.info("Model trained on %s %s — %d rows (train %d / test %d) "
             "train_acc %.3f test_acc %.3f",
             symbol, tf, len(df), len(train_df), len(test_df), train_acc, test_acc)

    # ---- backup existing model before overwrite (rollback path) ----
    if MODEL_PATH.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"model_{symbol}_{int(__import__('time').time())}.joblib"
        shutil.copy2(MODEL_PATH, backup)
        log.info("backed up previous model → %s", backup.name)

    joblib.dump({
        "model": clf,
        "features": FEATURES,
        "symbol": symbol,
        "tf": tf,
        "train_acc": float(train_acc),
        "test_acc": float(test_acc),
        "trained_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "n_samples": len(df),
    }, MODEL_PATH)


def predict(df_recent: pd.DataFrame, symbol: str | None = None) -> dict:
    """Predict direction probability for the latest bar.

    Refuses to predict if no model exists OR if the model was trained on a
    different symbol (would be silently wrong).
    """
    if not MODEL_PATH.exists():
        return {"direction": "NEUTRAL", "prob": 0.5, "reason": "no model"}
    bundle = joblib.load(MODEL_PATH)
    model_symbol = bundle.get("symbol")
    if symbol and model_symbol and symbol != model_symbol:
        log.warning("predict(%s) called with model trained on %s — refusing",
                    symbol, model_symbol)
        return {"direction": "NEUTRAL", "prob": 0.5,
                "reason": f"model trained on {model_symbol}, not {symbol}"}
    clf = bundle["model"]
    feats = build_features(df_recent).tail(1)[FEATURES].values
    if np.isnan(feats).any():
        return {"direction": "NEUTRAL", "prob": 0.5, "reason": "nan features"}
    proba = clf.predict_proba(feats)[0]
    classes = clf.classes_
    idx = int(np.argmax(proba))
    direction = {1: "UP", -1: "DOWN", 0: "NEUTRAL"}.get(int(classes[idx]), "NEUTRAL")
    return {"direction": direction, "prob": float(proba[idx])}


def model_info() -> dict:
    """Return model metadata for the UI (replaces hardcoded values)."""
    if not MODEL_PATH.exists():
        return {"exists": False, "version": "—", "train_acc": None,
                "test_acc": None, "symbol": None, "trained_at": None, "n_samples": None}
    b = joblib.load(MODEL_PATH)
    return {
        "exists": True,
        "version": "v1.0",
        "train_acc": b.get("train_acc"),
        "test_acc": b.get("test_acc"),
        "symbol": b.get("symbol"),
        "trained_at": b.get("trained_at"),
        "n_samples": b.get("n_samples"),
    }
