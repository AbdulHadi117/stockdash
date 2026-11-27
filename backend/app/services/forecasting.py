"""Forecasting on log-returns of adj_close. No DB or web imports."""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from xgboost import XGBRegressor

WINDOW_ROWS = 756   # ~3 years of daily price rows
EVAL_ROWS = 250     # walk-forward evaluation window (returns)
REFIT_EVERY = 60
MIN_ROWS = 400
LAGS = 5
WIN = 20            # return window feeding the features
MAX_PQ = 2
N_SIMS = 1000
SEED = 42


@dataclass
class ForecastResult:
    dates: list
    yhat: list[float]
    lower: list[float]
    upper: list[float]
    params: dict
    metrics: dict


def log_returns(prices: pd.Series) -> np.ndarray:
    p = prices.astype(float).values
    if not np.all(np.isfinite(p)) or np.any(p <= 0):
        raise ValueError("Invalid price data")
    return np.diff(np.log(p))


def evaluate(actual: np.ndarray, pred: np.ndarray, prev: np.ndarray) -> dict:
    """Metrics on 1-day log-returns. prev = previous day's actual return
    (naive direction baseline = persistence of yesterday's sign)."""
    zero = np.zeros_like(actual)
    nz = actual != 0

    def da(p: np.ndarray) -> float:
        return float(np.mean(np.sign(p[nz]) == np.sign(actual[nz])))

    def block(p: np.ndarray, d: float) -> dict:
        return {
            "mae": float(mean_absolute_error(actual, p)),
            "rmse": float(np.sqrt(mean_squared_error(actual, p))),
            "directional_accuracy": d,
        }

    model = block(pred, da(pred))
    naive = block(zero, da(prev))
    return {
        "model": model,
        "naive": naive,
        "n_eval": int(len(actual)),
        "beats_naive_rmse": bool(model["rmse"] < naive["rmse"]),
    }


# ---------- features (single definition used for train, eval and recursion) ----------
def features(W: np.ndarray) -> np.ndarray:
    """W: (n, WIN) returns preceding each target, oldest first."""
    cols = [W[:, -k] for k in range(1, LAGS + 1)]
    cols += [
        W[:, -5:].mean(axis=1),
        W.mean(axis=1),
        W[:, -5:].std(axis=1, ddof=1),
        W.std(axis=1, ddof=1),
    ]
    return np.column_stack(cols)


def supervised(r: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Row i: features from r[i:i+WIN], target r[i+WIN]."""
    W = sliding_window_view(r[:-1], WIN)
    return features(W), r[WIN:]


def _blocks(n: int):
    s = n - EVAL_ROWS
    while s < n:
        e = min(s + REFIT_EVERY, n)
        yield s, e
        s = e


# ---------- ARIMA ----------
def _arima(y, order):
    return ARIMA(y, order=(order[0], 0, order[1]), trend="c")


def _select_order(r_train: np.ndarray) -> tuple[tuple[int, int], float]:
    best, best_aic = (0, 0), np.inf
    for p in range(MAX_PQ + 1):
        for q in range(MAX_PQ + 1):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    aic = _arima(r_train, (p, q)).fit().aic
            except Exception:
                continue
            if aic < best_aic:
                best, best_aic = (p, q), float(aic)
    return best, best_aic


def _wf_arima(r: np.ndarray, order) -> np.ndarray:
    n, base = len(r), len(r) - EVAL_ROWS
    pred = np.empty(EVAL_ROWS)
    for s, e in _blocks(n):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = _arima(r[:s], order).fit()
            applied = res.apply(r[:e], refit=False)  # fixed params, real data
            pred[s - base:e - base] = np.asarray(
                applied.get_prediction(start=s, end=e - 1).predicted_mean
            )
    return pred


def _forecast_arima(r, order, horizon, last_price):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = _arima(r, order).fit()
        mean = np.asarray(res.forecast(horizon), dtype=float)
        sims = res.simulate(
            nsimulations=horizon, repetitions=N_SIMS, anchor="end", rng=SEED
        )
    sims = np.asarray(sims, dtype=float).reshape(horizon, -1)
    paths = last_price * np.exp(np.cumsum(sims, axis=0))
    yhat = last_price * np.exp(np.cumsum(mean))
    lo, hi = np.percentile(paths, [2.5, 97.5], axis=1)
    diag = {
        "adf_pvalue": float(adfuller(r)[1]),
        "ljung_box_pvalue_lag10": float(
            acorr_ljungbox(res.resid, lags=[10], return_df=True)["lb_pvalue"].iloc[0]
        ),
    }
    return yhat, lo, hi, diag


# ---------- XGBoost ----------
def _xgb() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, random_state=SEED, n_jobs=1, verbosity=0,
    )


def _wf_xgb(r: np.ndarray) -> np.ndarray:
    X, y = supervised(r)
    n, base = len(r), len(r) - EVAL_ROWS
    pred = np.empty(EVAL_ROWS)
    for s, e in _blocks(n):
        m = _xgb().fit(X[: s - WIN], y[: s - WIN])       # targets strictly before s
        pred[s - base:e - base] = m.predict(X[s - WIN:e - WIN])
    return pred


def _forecast_xgb(r, resid, horizon, last_price):
    X, y = supervised(r)
    m = _xgb().fit(X, y)
    rng = np.random.default_rng(SEED)
    base_w = r[-WIN:]

    w = base_w[None, :].copy()          # deterministic recursive path
    det = []
    for _ in range(horizon):
        p = float(m.predict(features(w))[0])
        det.append(p)
        w = np.concatenate([w[:, 1:], [[p]]], axis=1)

    W = np.tile(base_w, (N_SIMS, 1))    # residual-bootstrap paths
    sims = np.empty((horizon, N_SIMS))
    for h in range(horizon):
        step = m.predict(features(W)).astype(float) + rng.choice(resid, N_SIMS)
        sims[h] = step
        W = np.concatenate([W[:, 1:], step[:, None]], axis=1)

    paths = last_price * np.exp(np.cumsum(sims, axis=0))
    yhat = last_price * np.exp(np.cumsum(det))
    lo, hi = np.percentile(paths, [2.5, 97.5], axis=1)
    return yhat, lo, hi


# ---------- entry point ----------
def run_forecast(model: str, prices: pd.Series, horizon: int) -> ForecastResult:
    if model not in ("arima", "xgboost"):
        raise ValueError("Unknown model")
    if not 1 <= horizon <= 30:
        raise ValueError("Horizon must be 1-30")
    prices = prices.dropna().tail(WINDOW_ROWS)
    if len(prices) < MIN_ROWS:
        raise ValueError(f"Need at least {MIN_ROWS} price rows, have {len(prices)}")

    r = log_returns(prices)
    actual, prev = r[-EVAL_ROWS:], r[-EVAL_ROWS - 1:-1]
    last_price, last_date = float(prices.iloc[-1]), prices.index[-1]
    params = {
        "last_date": last_date.date().isoformat(),
        "last_price": last_price,
        "window_rows": int(len(prices)),
        "eval_rows": EVAL_ROWS,
        "refit_every": REFIT_EVERY,
        "target": "log-return of adj_close",
    }

    if model == "arima":
        order, aic = _select_order(r[:-EVAL_ROWS])  # order chosen before eval window
        pred = _wf_arima(r, order)
        yhat, lo, hi, diag = _forecast_arima(r, order, horizon, last_price)
        params.update(order=[order[0], 0, order[1]], aic=aic, **diag)
    else:
        pred = _wf_xgb(r)
        yhat, lo, hi = _forecast_xgb(r, actual - pred, horizon, last_price)
        params.update(lags=LAGS, feature_window=WIN, n_estimators=200,
                      max_depth=3, learning_rate=0.05, interval="residual bootstrap")

    for arr in (yhat, lo, hi, pred):
        if not np.all(np.isfinite(arr)):
            raise ValueError("Non-finite forecast")

    dates = pd.bdate_range(last_date + pd.Timedelta(days=1), periods=horizon)
    return ForecastResult(
        dates=[d.date() for d in dates],
        yhat=[float(x) for x in yhat],
        lower=[float(x) for x in lo],
        upper=[float(x) for x in hi],
        params=params,
        metrics=evaluate(actual, pred, prev),
    )