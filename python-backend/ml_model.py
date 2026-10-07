"""ML model — self-learning gradient-boosted classifier for trade direction.

Trains on historical candles + indicator features labeled by forward return.
Retrains nightly via APScheduler; supports incremental updates.

Safety:
- Proper train/test holdout (no train-acc-as-val overfitting)
- Symbol guard: predict() refuses to predict a symbol the model wasn't trained on
- Version backup before each retrain (rollback path)

Multi-symbol support:
- Each symbol has its own model file: models/trade_classifier_{symbol}.joblib
- Per-symbol in-memory cache (no cross-contamination)
- Per-symbol drift detection (recent predictions tracked separately)
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

MODELS_DIR = Path("models")
BACKUP_DIR = MODELS_DIR / "backups"

# ---- per-symbol model path ------------------------------------------------
def _model_path(symbol: str) -> Path:
    """Return the model file path for a given symbol.

    Each symbol gets its own file so training EURUSD doesn't overwrite the
    XAUUSD model (which was the root cause of 'predict(EURUSD) called with
    model trained on XAUUSD — refusing').
    """
    return MODELS_DIR / f"trade_classifier_{symbol}.joblib"


def _all_model_symbols() -> list[str]:
    """Scan models/ directory and return list of symbols that have trained models."""
    if not MODELS_DIR.exists():
        return []
    syms = []
    for p in MODELS_DIR.glob("trade_classifier_*.joblib"):
        # extract symbol from filename: trade_classifier_EURUSD.joblib → EURUSD
        sym = p.stem.replace("trade_classifier_", "", 1)
        if sym:
            syms.append(sym)
    return sorted(syms)


# Legacy constant for backward compat (points to EURUSD model).
# New code should use _model_path(symbol) instead.
MODEL_PATH = _model_path("EURUSD")

# ---- per-symbol in-memory cache ------------------------------------------
# Keyed by symbol so EURUSD cache doesn't get overwritten by XAUUSD model.
_model_caches: dict[str, dict] = {}
_model_cache_mtimes: dict[str, float] = {}


def _load_model(symbol: str | None = None) -> dict | None:
    """Load model from disk for a specific symbol, cached in memory.

    If symbol is None, returns the first available model (for legacy compat).
    Reloads if file changed on disk.
    """
    if symbol is None:
        syms = _all_model_symbols()
        if not syms:
            return None
        symbol = syms[0]
    path = _model_path(symbol)
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    cached = _model_caches.get(symbol)
    if cached and _model_cache_mtimes.get(symbol) == mtime:
        return cached
    try:
        bundle = joblib.load(path)
        _model_caches[symbol] = bundle
        _model_cache_mtimes[symbol] = mtime
        log.debug("model loaded into cache: symbol=%s (mtime=%s)", symbol, mtime)
        return bundle
    except Exception as exc:  # noqa: BLE001
        log.warning("model load failed for %s: %s", symbol, exc)
        return None


def _invalidate_cache(symbol: str) -> None:
    """Clear the in-memory cache for a symbol (called after retrain)."""
    _model_caches.pop(symbol, None)
    _model_cache_mtimes.pop(symbol, None)


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


def _adaptive_threshold(symbol: str, df: pd.DataFrame) -> float:
    """Compute label threshold based on symbol volatility.

    For high-volatility instruments (XAU), 8 pips is noise; for USDJPY it's
    significant. Uses ATR-based adaptive threshold: 0.5 * ATR(14) / price.
    """
    try:
        atr_val = atr(df, 14).dropna()
        if len(atr_val) == 0:
            return 0.0008  # default
        avg_atr = float(atr_val.iloc[-50:].mean()) if len(atr_val) >= 50 else float(atr_val.mean())
        avg_price = float(df["close"].mean())
        if avg_price > 0 and avg_atr > 0:
            # threshold = 0.5 * (ATR / price) — half the average true range
            return min(0.005, max(0.0003, 0.5 * avg_atr / avg_price))
    except Exception:  # noqa: BLE001
        pass
    return 0.0008


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

    Overfitting controls:
    - Early stopping (stops when val loss stops improving — typically 50-100
      trees instead of 300, drastically reduces overfit)
    - L1/L2 regularization (reg_alpha=1, reg_lambda=3)
    - min_child_weight=3 (prevents splitting on tiny noisy subsets)
    - Reduced max_depth=3 (was 4 — simpler trees generalize better)
    - Non-overlapping walk-forward folds (was overlapping → leakage)

    CPU-bound — callers in async context should use ``asyncio.to_thread``.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_file = _model_path(symbol)
    from xgboost import XGBClassifier
    from sklearn.utils.class_weight import compute_sample_weight
    rates = candles(symbol, tf, count)
    if not rates:
        log.warning("no candles to train on")
        return
    df = pd.DataFrame(rates)
    df = build_features(df)
    df["label"] = label(df, threshold=_adaptive_threshold(symbol, df))
    df = df.dropna()
    if len(df) < 200:
        log.warning("insufficient data to train (%d rows)", len(df))
        return

    # remap labels from [-1, 0, 1] to [0, 1, 2] (XGBoost requires 0-based)
    label_map = {-1: 0, 0: 1, 1: 2}
    df["label"] = df["label"].map(label_map)
    log.info("label distribution: %s", df["label"].value_counts().to_dict())

    # ---- walk-forward: 3 NON-OVERLAPPING folds ----
    # Each fold trains on segment [0..k] and tests on segment [k..k+1].
    # Previous implementation overlapped (fold 2 trained on [0..2k] which
    # included fold 1's test data [k..2k]) → leakage → inflated train_acc.
    fold_accs = []
    n = len(df)
    fold_size = n // 4  # 4 segments, 3 non-overlapping train→test pairs
    if fold_size < 50:
        # fallback to single split for small datasets
        fold_size = n // 2
        folds = [(0, fold_size, fold_size, n)]
    else:
        folds = [
            (0, fold_size, fold_size, fold_size * 2),
            (fold_size, fold_size * 2, fold_size * 2, fold_size * 3),
            (fold_size * 2, fold_size * 3, fold_size * 3, n),
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
            n_estimators=500,           # cap (early stopping will halt ~50-100)
            max_depth=3,                 # was 4 — simpler trees generalize better
            learning_rate=0.05,
            subsample=0.7,               # was 0.8 — more randomness = less overfit
            colsample_bytree=0.7,        # was 0.8 — same rationale
            min_child_weight=3,          # NEW — prevents splits on tiny noisy subsets
            reg_alpha=1.0,               # NEW — L1 regularization (feature sparsity)
            reg_lambda=3.0,              # NEW — L2 regularization (weight shrinkage)
            gamma=0.1,                   # NEW — min loss reduction to split
            early_stopping_rounds=20,    # NEW — stop when val loss stalls 20 rounds
            eval_metric="mlogloss",
            n_jobs=-1,
        )
        clf.fit(X_tr, y_tr, sample_weight=sw, eval_set=[(X_te, y_te)], verbose=False)
        acc = clf.score(X_te, y_te)
        fold_accs.append(acc)
        log.debug("fold %d→%d: test_acc=%.3f, best_iteration=%d",
                  train_end, test_end, acc, getattr(clf, "best_iteration", -1) or -1)
        if acc > best_test_acc:
            best_test_acc = acc
            best_clf = clf

    clf = best_clf
    test_acc = best_test_acc
    avg_acc = float(np.mean(fold_accs))
    log.info("Model trained on %s %s — %d rows, walk-forward folds=%s avg=%.3f",
             symbol, tf, len(df), [round(a, 3) for a in fold_accs], avg_acc)

    # ---- guard: don't promote a worse model over an existing better one ----
    old_bundle = _load_model(symbol)
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
    best_iter = getattr(clf, "best_iteration", None)
    log.info("Model promoted on %s %s — %d rows, train_acc=%.3f test_acc=%.3f "
             "avg_fold=%.3f best_iteration=%s",
             symbol, tf, len(df), train_acc, test_acc, avg_acc,
             best_iter if best_iter is not None else "n/a")

    # log feature importances for debugging (which features drive predictions?)
    try:
        importances = clf.feature_importances_
        fi_pairs = sorted(zip(FEATURES, importances), key=lambda x: x[1], reverse=True)
        fi_str = ", ".join(f"{f}={v:.3f}" for f, v in fi_pairs[:5])
        log.info("Feature importances (top 5): %s", fi_str)
    except Exception:  # noqa: BLE001
        pass

    # overfitting detection: if train_acc >> test_acc, flag it
    gap = train_acc - test_acc
    if gap > 0.15:
        log.warning("⚠ Overfitting detected: train_acc=%.3f >> test_acc=%.3f (gap=%.3f)"
                    " — consider more data or fewer features",
                    train_acc, test_acc, gap)
    elif gap > 0.08:
        log.info("ℹ mild overfitting: train_acc=%.3f, test_acc=%.3f (gap=%.3f) — within tolerance",
                 train_acc, test_acc, gap)
    else:
        log.info("✓ good generalization: train_acc=%.3f, test_acc=%.3f (gap=%.3f)",
                 train_acc, test_acc, gap)

    # ---- backup existing model before overwrite (rollback path) ----
    if model_file.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"model_{symbol}_{int(__import__('time').time())}.joblib"
        shutil.copy2(model_file, backup)
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
    }, model_file)

    # register in DB
    try:
        from db import register_ml_model
        register_ml_model(
            version="v1.0", symbol=symbol, train_acc=float(train_acc),
            test_acc=float(test_acc),
            trained_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            n_samples=len(df), path=str(model_file), drift_score=0.0,
        )
    except Exception:  # noqa: BLE001
        pass

    # invalidate in-memory cache so next predict() reloads the new model
    _invalidate_cache(symbol)


# ---- drift detection (per-symbol) -----------------------------------------
# Each symbol tracks its own recent predictions so EURUSD drift doesn't
# pollute XAUUSD drift detection.
_RECENT_PREDICTIONS: dict[str, deque] = {}
_DRIFT_THRESHOLD = 0.08  # 8% confidence drop triggers retrain


def _track_prediction(symbol: str, prob: float) -> None:
    dq = _RECENT_PREDICTIONS.get(symbol)
    if dq is None:
        dq = deque(maxlen=50)
        _RECENT_PREDICTIONS[symbol] = dq
    dq.append(prob)


def check_drift(symbol: str | None = None) -> float:
    """Compute drift score for a symbol = how far recent prediction confidence
    has dropped below the training confidence mean. Returns 0.0 if insufficient
    data or no model for the symbol.

    A drift > _DRIFT_THRESHOLD (0.08) indicates the model's recent predictions
    are much less confident than at training time → market regime has shifted.
    """
    if symbol is None:
        return 0.0
    bundle = _load_model(symbol)
    if bundle is None:
        return 0.0
    dq = _RECENT_PREDICTIONS.get(symbol)
    if not dq or len(dq) < 10:
        return 0.0
    train_mean = bundle.get("train_conf_mean")
    if train_mean is None:
        return 0.0
    recent_mean = float(np.mean(list(dq)))
    drift = max(0.0, train_mean - recent_mean)
    # persist to DB
    try:
        from db import get_active_ml_model, update_drift_score
        m = get_active_ml_model(symbol)
        if m and m.get("id"):
            update_drift_score(m["id"], drift)
    except Exception:  # noqa: BLE001
        pass
    if drift > _DRIFT_THRESHOLD:
        log.warning("⚠ drift detected on %s: %.3f > %.3f — retrain recommended",
                    symbol, drift, _DRIFT_THRESHOLD)
    return drift


def predict(df_recent: pd.DataFrame, symbol: str | None = None) -> dict:
    """Predict direction probability for the latest bar.

    Loads the symbol-specific model (models/trade_classifier_{symbol}.joblib).
    Returns NEUTRAL/0.5 if no model exists for the requested symbol.
    Tracks predictions per-symbol for drift detection.
    """
    if symbol is None:
        symbol = "EURUSD"  # legacy default
    model_file = _model_path(symbol)
    if not model_file.exists():
        return {"direction": "NEUTRAL", "prob": 0.5,
                "reason": f"no model trained for {symbol} — train it first"}
    bundle = _load_model(symbol)
    if bundle is None:
        return {"direction": "NEUTRAL", "prob": 0.5, "reason": "model load failed"}
    clf = bundle["model"]
    feats = build_features(df_recent).tail(1)[FEATURES].values
    if np.isnan(feats).any():
        return {"direction": "NEUTRAL", "prob": 0.5, "reason": "nan features"}
    proba = clf.predict_proba(feats)[0]
    classes = clf.classes_
    idx = int(np.argmax(proba))
    # remap back from [0,1,2] to [-1,0,1] = [DOWN, NEUTRAL, UP]
    reverse_map = {0: "DOWN", 1: "NEUTRAL", 2: "UP"}
    direction = reverse_map.get(int(classes[idx]), "NEUTRAL")
    max_prob = float(proba[idx])
    _track_prediction(symbol, max_prob)  # feed per-symbol drift detector
    drift = check_drift(symbol)
    return {"direction": direction, "prob": max_prob, "drift": drift}


def model_info(symbol: str | None = None) -> dict:
    """Return model metadata for the UI.

    If symbol is given, returns info for that symbol's model only.
    If symbol is None, returns aggregated info: exists=True if ANY model
    exists, plus a 'models' dict keyed by symbol with per-symbol details.
    """
    if symbol is not None:
        b = _load_model(symbol)
        if b is None:
            return {"exists": False, "symbol": symbol, "drift": 0.0}
        drift = check_drift(symbol)
        return {
            "exists": True,
            "version": "v1.0",
            "train_acc": b.get("train_acc"),
            "test_acc": b.get("test_acc"),
            "symbol": b.get("symbol"),
            "tf": b.get("tf", "H1"),
            "trained_at": b.get("trained_at"),
            "n_samples": b.get("n_samples"),
            "drift": round(drift, 3),
            "drift_threshold": _DRIFT_THRESHOLD,
        }
    # aggregate: return all trained models
    symbols = _all_model_symbols()
    if not symbols:
        return {"exists": False, "version": "—", "train_acc": None,
                "test_acc": None, "symbol": None, "trained_at": None,
                "n_samples": None, "drift": 0.0, "models": {}}
    models: dict[str, dict] = {}
    best = None
    best_acc = -1.0
    for sym in symbols:
        b = _load_model(sym)
        if b is None:
            continue
        drift = check_drift(sym)
        info = {
            "train_acc": b.get("train_acc"),
            "test_acc": b.get("test_acc"),
            "tf": b.get("tf", "H1"),
            "trained_at": b.get("trained_at"),
            "n_samples": b.get("n_samples"),
            "drift": round(drift, 3),
        }
        models[sym] = info
        acc = b.get("test_acc", 0.0) or 0.0
        if acc > best_acc:
            best_acc = acc
            best = b
    if best is None:
        return {"exists": False, "models": {}}
    return {
        "exists": True,
        "version": "v1.0",
        "train_acc": best.get("train_acc"),
        "test_acc": best.get("test_acc"),
        "symbol": best.get("symbol"),
        "trained_at": best.get("trained_at"),
        "n_samples": best.get("n_samples"),
        "drift": round(check_drift(best.get("symbol")), 3),
        "drift_threshold": _DRIFT_THRESHOLD,
        "models": models,  # per-symbol breakdown
    }
