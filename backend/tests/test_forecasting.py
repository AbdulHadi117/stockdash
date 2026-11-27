import numpy as np
import pandas as pd
import pytest

from app.services.forecasting import EVAL_ROWS, WIN, evaluate, run_forecast, supervised


def test_features_use_only_past():
    r = np.random.default_rng(1).normal(0, 0.01, 200)
    X1, _ = supervised(r)
    r2 = r.copy()
    r2[150:] += 1.0  # alter the "future"
    X2, _ = supervised(r2)
    k = 150 - WIN + 1  # rows whose window ends before index 150
    assert np.allclose(X1[:k], X2[:k])


def test_metrics_perfect_prediction():
    a = np.array([0.01, -0.02, 0.03, -0.01])
    m = evaluate(a, a.copy(), np.roll(a, 1))
    assert m["model"]["mae"] == 0 and m["model"]["directional_accuracy"] == 1


@pytest.mark.parametrize("model", ["arima", "xgboost"])
def test_forecast_shape(model):
    idx = pd.bdate_range("2022-01-03", periods=600)
    rng = np.random.default_rng(2)
    p = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 600))), index=idx)
    res = run_forecast(model, p, 7)
    assert len(res.dates) == len(res.yhat) == len(res.lower) == len(res.upper) == 7
    assert res.dates[0] > idx[-1].date()
    assert all(lo <= hi for lo, hi in zip(res.lower, res.upper))
    assert res.metrics["n_eval"] == EVAL_ROWS