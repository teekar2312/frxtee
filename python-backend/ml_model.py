"""ML model — self-learning gradient-boosted classifier for trade direction.

Trains on historical candles + indicator features labeled by forward return.
Retrains nightly via APScheduler; supports incremental updates.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from indicators import INDICATOR_REGISTRY, atr, ema, rsi, macd
from mt5_service import candles

log = logging.getLogger("ml")

MODEL_PATH = Path("models/trade_classifier.joblib")
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

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
    """Forward return label: 1 up, -1 down, 0 flat."""
    fwd = df["close"].shift(-horizon) / df["close"] - 1
    return pd.Series(np.where(fwd > threshold, 1, np.where(fwd < -threshold, -1, 0)),
                    index=df.index)


def train(symbol: str = "EURUSD", tf: str = "H1", count: int = 3000):
    """Train (or retrain) the classifier on `count` historical candles."""
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
    X = df[FEATURES].values
    y = df["label"].values
    clf = XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="mlogloss",
        use_label_encoder=False, n_jobs=-1,
    )
    clf.fit(X, y)
    joblib.dump({"model": clf, "features": FEATURES, "symbol": symbol}, MODEL_PATH)
    acc = clf.score(X, y)
    log.info("Model retrained on %s %s — %d rows, train acc %.3f", symbol, tf, len(df), acc)


def predict(df_recent: pd.DataFrame) -> dict:
    """Predict direction probability for the latest bar."""
    if not MODEL_PATH.exists():
        train()
    if not MODEL_PATH.exists():
        return {"direction": "NEUTRAL", "prob": 0.5}
    bundle = joblib.load(MODEL_PATH)
    clf = bundle["model"]
    feats = build_features(df_recent).tail(1)[FEATURES].values
    if np.isnan(feats).any():
        return {"direction": "NEUTRAL", "prob": 0.5}
    proba = clf.predict_proba(feats)[0]
    classes = clf.classes_
    idx = int(np.argmax(proba))
    direction = {1: "UP", -1: "DOWN", 0: "NEUTRAL"}.get(classes[idx], "NEUTRAL")
    return {"direction": direction, "prob": float(proba[idx])}
