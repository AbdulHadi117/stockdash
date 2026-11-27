import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth import api
from market_page import fetch_prices, fetch_symbols


def _err(resp):
    try:
        d = resp.json().get("detail")
    except Exception:
        d = None
    st.error(d if isinstance(d, str) else f"Request failed ({resp.status_code}).")


def _show_run(run: dict, key: str):
    pts = pd.DataFrame(run["points"])
    pts["date"] = pd.to_datetime(pts["date"])
    last = pd.to_datetime(run["params"]["last_date"])
    hist = fetch_prices(
        run["ticker"], (last - dt.timedelta(days=180)).date(), last.date()
    )

    fig = go.Figure()
    if not hist.empty:
        fig.add_trace(go.Scatter(x=hist.index, y=hist["adj_close"],
                                 mode="lines", name="History"))
    fig.add_trace(go.Scatter(x=pts["date"], y=pts["upper"], mode="lines",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=pts["date"], y=pts["lower"], mode="lines",
                             line=dict(width=0), fill="tonexty",
                             name="95% interval"))
    fig.add_trace(go.Scatter(x=pts["date"], y=pts["yhat"], mode="lines",
                             name=f'{run["model"].upper()} forecast'))
    fig.update_layout(title=f'{run["ticker"]} - {run["horizon"]}-day forecast',
                      height=420, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True, key=f"{key}_chart")

    m = run["metrics"]
    tbl = pd.DataFrame({"Model": m["model"], "Naive": m["naive"]}).T
    tbl.columns = ["MAE", "RMSE", "Directional acc."]
    st.dataframe(tbl.round(4), use_container_width=True)
    st.caption(
        f'Walk-forward, {m["n_eval"]} days, 1-day log-returns. '
        "Naive = zero return; naive direction = previous day's sign."
    )
    if not m["beats_naive_rmse"]:
        st.info("Model does not beat the naive baseline on RMSE.")
    with st.expander("Parameters and diagnostics"):
        st.json(run["params"])


def render_forecast():
    try:
        symbols = [s["ticker"] for s in fetch_symbols()]
    except Exception:
        st.error("Cannot reach the API.")
        return

    c1, c2, c3 = st.columns([2, 2, 3])
    ticker = c1.selectbox("Symbol", symbols, key="fc_symbol")
    model = c2.radio("Model", ["arima", "xgboost"], horizontal=True, key="fc_model")
    horizon = c3.slider("Horizon (days)", 1, 30, 7, key="fc_h")

    if st.button("Run forecast", key="fc_run"):
        with st.spinner("Running forecast..."):
            resp = api("POST", "/forecasts",
                       json={"ticker": ticker, "model": model, "horizon": horizon},
                       timeout=90)
        if resp.status_code == 201:
            st.session_state["fc_current"] = resp.json()
        else:
            _err(resp)

    cur = st.session_state.get("fc_current")
    if cur:
        _show_run(cur, "fc_cur")

    st.divider()
    if st.toggle("Show forecast history", key="fc_hist_on"):
        resp = api("GET", "/forecasts")
        if resp.status_code != 200:
            _err(resp)
            return
        runs = resp.json()
        if not runs:
            st.caption("No saved forecasts.")
            return
        labels = {
            f'#{r["id"]} {r["ticker"]} {r["model"]} h={r["horizon"]} '
            f'{r["created_at"][:16]}': r["id"] for r in runs
        }
        pick = st.selectbox("Past runs", list(labels), index=None, key="fc_hist")
        if pick:
            d = api("GET", f"/forecasts/{labels[pick]}")
            if d.status_code == 200:
                _show_run(d.json(), "fc_hist_run")
            else:
                _err(d)