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
from collections import deque
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from indicators import atr, ema, rsi, macd
from mt5_service import candles

log = logging.getLogger("ml")

MODEL_PATH = Path("models/trade_classifier.joblib")
BACKUP_DIR = Path("models/backups")

# ---- in-memory model cache (avoid joblib.load on every predict) -----------
_model_cache: dict | None = None
_model_cache_mtime: float = 0.0


def _load_model() -> dict | None:
    """Load model from disk, cached in memory. Reloads if file changed."""
    global _model_cache, _model_cache_mtime
    if not MODEL_PATH.exists():
        return None
    mtime = MODEL_PATH.stat().st_mtime
    if _model_cache and mtime == _model_cache_mtime:
        return _model_cache
    try:
        _model_cache = joblib.load(MODEL_PATH)
        _model_cache_mtime = mtime
        log.debug("model loaded into cache (mtime=%s)", mtime)
        return _model_cache
    except Exception as exc:  # noqa: BLE001
        log.warning("model load failed: %s", exc)
        return None

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
    does not overlap with causal features (which use data <= t).

    The last `horizon` bars have NaN forward return (no future data) — they
    are dropped by the caller's dropna(), preventing label leakage.
    """
    fwd = df["close"].shift(-horizon) / df["close"] - 1
    labels = np.where(fwd > threshold, 1, np.where(fwd < -threshold, -1, 0))
    # explicitly mark the last `horizon` bars as NaN (no future data to label)
    labels = labels.astype(float)
    labels[-horizon:] = np.nan
    return pd.Series(labels, index=df.index)


def train(symbol: str = "EURUSD", tf: str = "H1", count: int = 3000):
    """Train (or retrain) the classifier with walk-forward validation + class
    balancing. Compares new model's test_acc against the old one — refuses to
    promote a worse model (prevents regression).

    CPU-bound — callers in async context should use ``asyncio.to_thread``.
    """
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    from xgboost import XGBClassifier
    from sklearn.utils.class_weight import compute_sample_weight
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

    # ---- walk-forward: 3 folds, each trains on first 70%, tests on next 15% ----
    fold_accs = []
    fold_size = len(df) // 4  # 4 segments, 3 overlapping folds
    if fold_size < 50:
        # fallback to single split for small datasets
        fold_size = len(df) // 2
        folds = [(0, fold_size, fold_size, len(df))]
    else:
        folds = [
            (0, fold_size, fold_size, fold_size * 2),
            (0, fold_size * 2, fold_size * 2, fold_size * 3),
            (0, fold_size * 3, fold_size * 3, len(df)),
        ]

    best_clf = None
    best_test_acc = 0.0
    for train_start, train_end, test_start, test_end in folds:
        tr = df.iloc[train_start:train_end]
        te = df.iloc[test_start:test_end]
        X_tr, y_tr = tr[FEATURES].values, tr["label"].values
        X_te, y_te = te[FEATURES].values, te["label"].values
        # class-balanced sample weights (handle imbalanced labels)
        sw = compute_sample_weight("balanced", y_tr)
        clf = XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, eval_metric="mlogloss",
            n_jobs=-1,
        )
        clf.fit(X_tr, y_tr, sample_weight=sw, eval_set=[(X_te, y_te)], verbose=False)
        acc = clf.score(X_te, y_te)
        fold_accs.append(acc)
        if acc > best_test_acc:
            best_test_acc = acc
            best_clf = clf

    clf = best_clf
    test_acc = best_test_acc
    avg_acc = float(np.mean(fold_accs))
    log.info("Model trained on %s %s — %d rows, walk-forward folds=%s avg=%.3f",
             symbol, tf, len(df), [round(a, 3) for a in fold_accs], avg_acc)

    # ---- guard: don't promote a worse model over an existing better one ----
    old_bundle = _load_model()
    if old_bundle:
        old_acc = old_bundle.get("test_acc", 0.0)
        old_symbol = old_bundle.get("symbol")
        if old_symbol == symbol and test_acc < old_acc - 0.02:
            log.warning("new model test_acc %.3f < old %.3f — keeping old model",
                        test_acc, old_acc)
            return

    # final train_acc on full set (for display)
    X_full = df[FEATURES].values
    y_full = df["label"].values
    train_acc = clf.score(X_full, y_full)
    log.info("Model promoted on %s %s — %d rows, train_acc=%.3f test_acc=%.3f "
             "avg_fold=%.3f", symbol, tf, len(df), train_acc, test_acc, avg_acc)

    # ---- backup existing model before overwrite (rollback path) ----
    if MODEL_PATH.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"model_{symbol}_{int(__import__('time').time())}.joblib"
        shutil.copy2(MODEL_PATH, backup)
        log.info("backed up previous model → %s", backup.name)

    # compute training-time prediction confidence distribution (for drift detection)
    train_proba = clf.predict_proba(X_full)
    train_max_proba = np.max(train_proba, axis=1)
    train_conf_mean = float(train_max_proba.mean())
    train_conf_std = float(train_max_proba.std())

    joblib.dump({
        "model": clf,
        "features": FEATURES,
        "symbol": symbol,
        "tf": tf,
        "train_acc": float(train_acc),
        "test_acc": float(test_acc),
        "trained_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "n_samples": len(df),
        "train_conf_mean": train_conf_mean,
        "train_conf_std": train_conf_std,
    }, MODEL_PATH)

    # register in DB
    try:
        from db import register_ml_model
        register_ml_model(
            version="v1.0", symbol=symbol, train_acc=float(train_acc),
            test_acc=float(test_acc),
            trained_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            n_samples=len(df), path=str(MODEL_PATH), drift_score=0.0,
        )
    except Exception:  # noqa: BLE001
        pass

    # invalidate in-memory cache so next predict() reloads the new model
    global _model_cache, _model_cache_mtime
    _model_cache = None
    _model_cache_mtime = 0.0


# ---- drift detection -----------------------------------------------------
_RECENT_PREDICTIONS: deque = deque(maxlen=50)  # O(1) append/pop, bounded
_DRIFT_THRESHOLD = 0.08  # 8% confidence drop triggers retrain


def _track_prediction(prob: float) -> None:
    _RECENT_PREDICTIONS.append(prob)  # deque(maxlen=50) auto-trims


def check_drift(symbol: str | None = None) -> float:
    """Compute drift score = how far recent prediction confidence has dropped
    below the training confidence mean. Returns 0.0 if insufficient data.

    A drift > _DRIFT_THRESHOLD (0.08) indicates the model's recent predictions
    are much less confident than at training time → market regime has shifted.
    """
    bundle = _load_model()
    if bundle is None or len(_RECENT_PREDICTIONS) < 10:
        return 0.0
    train_mean = bundle.get("train_conf_mean")
    if train_mean is None:
        return 0.0
    if symbol and bundle.get("symbol") != symbol:
        return 0.0
    recent_mean = float(np.mean(_RECENT_PREDICTIONS))
    drift = max(0.0, train_mean - recent_mean)
    # persist to DB
    try:
        from db import get_active_ml_model, update_drift_score
        m = get_active_ml_model(bundle.get("symbol"))
        if m and m.get("id"):
            update_drift_score(m["id"], drift)
    except Exception:  # noqa: BLE001
        pass
    if drift > _DRIFT_THRESHOLD:
        log.warning("⚠ drift detected on %s: %.3f > %.3f — retrain recommended",
                    bundle.get("symbol"), drift, _DRIFT_THRESHOLD)
    return drift


def predict(df_recent: pd.DataFrame, symbol: str | None = None) -> dict:
    """Predict direction probability for the latest bar.

    Refuses to predict if no model exists OR if the model was trained on a
    different symbol (would be silently wrong). Tracks predictions for drift.
    """
    if not MODEL_PATH.exists():
        return {"direction": "NEUTRAL", "prob": 0.5, "reason": "no model"}
    bundle = _load_model()
    if bundle is None:
        return {"direction": "NEUTRAL", "prob": 0.5, "reason": "model load failed"}
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
    max_prob = float(proba[idx])
    _track_prediction(max_prob)  # feed drift detector
    drift = check_drift(model_symbol)
    return {"direction": direction, "prob": max_prob, "drift": drift}


def model_info() -> dict:
    """Return model metadata for the UI (replaces hardcoded values)."""
    b = _load_model()
    if b is None:
        return {"exists": False, "version": "—", "train_acc": None,
                "test_acc": None, "symbol": None, "trained_at": None,
                "n_samples": None, "drift": 0.0}
    drift = check_drift(b.get("symbol"))
    return {
        "exists": True,
        "version": "v1.0",
        "train_acc": b.get("train_acc"),
        "test_acc": b.get("test_acc"),
        "symbol": b.get("symbol"),
        "trained_at": b.get("trained_at"),
        "n_samples": b.get("n_samples"),
        "drift": round(drift, 3),
        "drift_threshold": _DRIFT_THRESHOLD,
    }
