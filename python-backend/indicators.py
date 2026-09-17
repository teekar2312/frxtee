"""Technical indicators — 30 indicators computed on OHLCV pandas DataFrames.

Categories: Trend, Momentum, Volatility, Volume.
Uses the `ta` library where available, with manual fallbacks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import ta  # type: ignore
    from ta.trend import MACD, IchimokuIndicator
    from ta.momentum import RSIIndicator, StochasticOscillator, CCIIndicator, WilliamsRIndicator
    from ta.volatility import BollingerBands, AverageTrueRange, KeltnerChannel, DonchianChannel
    from ta.volume import OnBalanceVolumeIndicator, MFIIndicator, volume_weighted_average_price
    TA = True
except Exception:  # pragma: no cover
    TA = False


# ---------- Trend ----------
def ema(df, period=20, col="close"):
    return df["close"].ewm(span=period, adjust=False).mean()


def sma(df, period=20):
    return df["close"].rolling(period).mean()


def vwap(df):
    if TA:
        return volume_weighted_average_price(df["high"], df["low"], df["close"], df["volume"])
    return (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()


def supertrend(df, period=10, multiplier=3):
    hl2 = (df["high"] + df["low"]) / 2
    atr = (df["high"] - df["low"]).rolling(period).mean()
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
    st = pd.Series(np.nan, index=df.index)
    dir_ = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        # carry previous direction when no crossover
        dir_.iloc[i] = dir_.iloc[i - 1]
        if df["close"].iloc[i] > upper.iloc[i - 1]:
            dir_.iloc[i] = 1
        elif df["close"].iloc[i] < lower.iloc[i - 1]:
            dir_.iloc[i] = -1
        st.iloc[i] = lower.iloc[i] if dir_.iloc[i] == 1 else upper.iloc[i]
    return st


def psar(df, step=0.02, max_step=0.2):
    if TA:
        from ta.trend import PSARIndicator
        return PSARIndicator(df["high"], df["low"], step, max_step).psar()
    high, low, close = df["high"], df["low"], df["close"]
    psar = close.copy()
    bull = True
    af, ep = step, high.iloc[0]
    for i in range(2, len(df)):
        if bull:
            psar.iloc[i] = psar.iloc[i - 1] + af * (ep - psar.iloc[i - 1])
            if low.iloc[i] < psar.iloc[i]:
                bull = False
                psar.iloc[i] = ep
                ep, af = low.iloc[i], step
            elif high.iloc[i] > ep:
                ep, af = high.iloc[i], min(af + step, max_step)
        else:
            psar.iloc[i] = psar.iloc[i - 1] + af * (ep - psar.iloc[i - 1])
            if high.iloc[i] > psar.iloc[i]:
                bull = True
                psar.iloc[i] = ep
                ep, af = high.iloc[i], step
            elif low.iloc[i] < ep:
                ep, af = low.iloc[i], min(af + step, max_step)
    return psar


def ichimoku(df):
    if TA:
        return IchimokuIndicator(df["high"], df["low"]).ichimoku_cloud_()
    return sma(df, 26)


def hma(df, period=14):
    half, sqrt = max(1, period // 2), max(1, int(np.sqrt(period)))
    wma1 = df["close"].rolling(half).apply(lambda x: (x * np.arange(1, len(x) + 1)).sum() / np.arange(1, len(x) + 1).sum(), raw=True)
    wma2 = df["close"].rolling(period).apply(lambda x: (x * np.arange(1, len(x) + 1)).sum() / np.arange(1, len(x) + 1).sum(), raw=True)
    return 2 * wma1 - wma2.rolling(sqrt).mean()


# ---------- Momentum ----------
def rsi(df, period=14):
    if TA:
        return RSIIndicator(df["close"], period).rsi()
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def stochastic(df, k=14, d=3):
    if TA:
        s = StochasticOscillator(df["high"], df["low"], df["close"], k, d)
        return s.stoch(), s.stoch_signal()
    ll = df["low"].rolling(k).min()
    hh = df["high"].rolling(k).max()
    k_ = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    return k_, k_.rolling(d).mean()


def macd(df, fast=12, slow=26, signal=9):
    if TA:
        m = MACD(df["close"], slow, fast, signal)
        return m.macd(), m.macd_signal(), m.macd_diff()
    ema_f = df["close"].ewm(span=fast, adjust=False).mean()
    ema_s = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_f - ema_s
    sig = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, sig, macd_line - sig


def cci(df, period=20):
    if TA:
        return CCIIndicator(df["high"], df["low"], df["close"], period).cci()
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))


def williams_r(df, period=14):
    if TA:
        return WilliamsRIndicator(df["high"], df["low"], df["close"], period).williams_r()
    hh = df["high"].rolling(period).max()
    ll = df["low"].rolling(period).min()
    return -100 * (hh - df["close"]) / (hh - ll).replace(0, np.nan)


def roc(df, period=12):
    return df["close"].pct_change(periods=period) * 100


def momentum(df, period=10):
    return df["close"] - df["close"].shift(period)


def tsi(df, r=25, s=13):
    # True Strength Index: double-smoothed momentum
    m = df["close"].diff()
    m1 = m.ewm(span=r, adjust=False).mean()
    m2 = m1.ewm(span=s, adjust=False).mean()          # second smoothing uses s
    m1a = abs(m).ewm(span=r, adjust=False).mean()
    m2a = m1a.ewm(span=s, adjust=False).mean()        # second smoothing uses s
    return 100 * m2 / m2a.replace(0, np.nan)


# ---------- Volatility ----------
def bollinger(df, period=20, dev=2):
    if TA:
        b = BollingerBands(df["close"], period, dev)
        return b.bollinger_hband(), b.bollinger_mavg(), b.bollinger_lband()
    mid = df["close"].rolling(period).mean()
    sd = df["close"].rolling(period).std()
    return mid + dev * sd, mid, mid - dev * sd


def atr(df, period=14):
    if TA:
        return AverageTrueRange(df["high"], df["low"], df["close"], period).average_true_range()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift()).abs(),
                   (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def keltner(df, period=20, mult=2):
    mid = ema(df, period)
    a = atr(df, period)
    if TA:
        k = KeltnerChannel(df["high"], df["low"], df["close"], period, mult)
        return k.keltner_channel_hband(), k.keltner_channel_mband(), k.keltner_channel_lband()
    return mid + mult * a, mid, mid - mult * a


def donchian(df, period=20):
    if TA:
        d = DonchianChannel(df["high"], df["low"], df["close"], period)
        return d.donchian_channel_hband(), d.donchian_channel_mband(), d.donchian_channel_lband()
    return df["high"].rolling(period).max(), df["close"].rolling(period).mean(), df["low"].rolling(period).min()


def stddev(df, period=20):
    return df["close"].rolling(period).std()


def linreg(df, period=20):
    x = np.arange(period)
    return df["close"].rolling(period).apply(
        lambda y: np.polyval(np.polyfit(x, y, 1), period - 1), raw=True
    )


# ---------- Volume ----------
def obv(df):
    if TA:
        return OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume()
    dir_ = np.sign(df["close"].diff().fillna(0))
    return (dir_ * df["volume"]).cumsum()


def mfi(df, period=14):
    if TA:
        return MFIIndicator(df["high"], df["low"], df["close"], df["volume"], period).money_flow_index()
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    pos = (tp.diff() > 0).astype(float) * mf
    neg = (tp.diff() < 0).astype(float) * mf
    pos_sum = pos.rolling(period).sum()
    neg_sum = neg.rolling(period).sum()
    return 100 - 100 / (1 + pos_sum / neg_sum.replace(0, np.nan))


def accdist(df):
    clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"]).replace(0, np.nan)
    return (clv * df["volume"]).cumsum()


def tick_volume(df):
    return df["volume"]


# ---------- Additional Momentum / Volatility / Volume ----------
def stc(df, fast=23, slow=50, length=10):
    """Schaff Trend Cycle: MACD smoothed by TSI-style double EMA, then stochastic."""
    macd_line = ema(df, fast) - ema(df, slow)
    m1 = macd_line.ewm(span=length, adjust=False).mean()
    m2 = m1.ewm(span=length, adjust=False).mean()
    # stochastic of m2
    ll = m2.rolling(length).min()
    hh = m2.rolling(length).max()
    stc_val = 100 * (m2 - ll) / (hh - ll).replace(0, np.nan)
    return stc_val.fillna(50)


def ultimate(df, p1=7, p2=14, p3=28):
    """Ultimate Oscillator — weighted average of 3 buying-pressure periods."""
    prev_close = df["close"].shift(1)
    bp = df["close"] - np.minimum(df["low"], prev_close)
    tr = np.maximum(df["high"], prev_close) - np.minimum(df["low"], prev_close)
    avg1 = bp.rolling(p1).sum() / tr.rolling(p1).sum().replace(0, np.nan)
    avg2 = bp.rolling(p2).sum() / tr.rolling(p2).sum().replace(0, np.nan)
    avg3 = bp.rolling(p3).sum() / tr.rolling(p3).sum().replace(0, np.nan)
    return 100 * (4 * avg1 + 2 * avg2 + avg3) / 7


def chaikin_vol(df, ema_period=10, roc_period=10):
    """Chaikin Volatility — rate-of-change of an EMA of (high-low)."""
    hl = df["high"] - df["low"]
    ema_hl = hl.ewm(span=ema_period, adjust=False).mean()
    return (ema_hl / ema_hl.shift(roc_period) - 1) * 100


def vol_ratio(df, period=14):
    """Volatility Ratio — current True Range vs ATR (volatility expansion gauge)."""
    prev_close = df["close"].shift(1)
    tr = np.maximum.reduce([
        (df["high"] - df["low"]).to_numpy(),
        np.abs(df["high"].to_numpy() - prev_close.to_numpy()),
        np.abs(df["low"].to_numpy() - prev_close.to_numpy()),
    ])
    tr = pd.Series(tr, index=df.index)
    return tr / atr(df, period).replace(0, np.nan)


def volume_profile(df, bins=20):
    """Volume Profile — volume bucketed by price, returns a dict of {price: vol}.

    Returns a pandas Series indexed by price-bin midpoint so `compute()` can
    serialise it as a list.
    """
    lo, hi = df["low"].min(), df["high"].max()
    if lo == hi:
        return pd.Series([0.0], index=[float(lo)])
    edges = np.linspace(lo, hi, bins + 1)
    cents = (edges[:-1] + edges[1:]) / 2
    # distribute bar volume across the price bins its range overlaps
    vol = np.zeros(bins)
    for _, row in df.iterrows():
        mask = (edges[:-1] < row["high"]) & (edges[1:] > row["low"])
        vol[mask] += row["volume"]
    return pd.Series(vol, index=cents)


INDICATOR_REGISTRY = {
    "ema": ema, "sma": sma, "vwap": vwap, "supertrend": supertrend,
    "psar": psar, "ichimoku": ichimoku, "hma": hma,
    "rsi": rsi, "stochastic": stochastic, "macd": macd, "cci": cci,
    "williamsr": williams_r, "roc": roc, "momentum": momentum, "tsi": tsi,
    "stc": stc, "ultimate": ultimate,
    "bbands": bollinger, "atr": atr, "keltner": keltner, "donchian": donchian,
    "stddev": stddev, "linreg": linreg,
    "chaikinvol": chaikin_vol, "volratio": vol_ratio,
    "obv": obv, "mfi": mfi, "accdist": accdist, "tickvol": tick_volume,
    "volprofile": volume_profile,
}


def compute(df: pd.DataFrame, indicators: list[str]) -> dict:
    """Compute a dict of series for the requested indicator ids."""
    out = {}
    for ind in indicators:
        fn = INDICATOR_REGISTRY.get(ind)
        if not fn:
            continue
        try:
            res = fn(df)
            if isinstance(res, tuple):
                for k, s in zip(["main", "signal", "hist"][: len(res)], res):
                    out[f"{ind}_{k}"] = s.dropna().round(5).tail(60).tolist()
            else:
                out[ind] = res.dropna().round(5).tail(60).tolist()
        except Exception as exc:  # noqa: BLE001
            out[ind] = []
    return out
