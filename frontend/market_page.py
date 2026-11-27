import os
import datetime as dt
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://backend:8000")
STALE_DAYS = 4


@st.cache_data(ttl=300)
def fetch_symbols():
    r = requests.get(f"{API_URL}/symbols", timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
def fetch_summary():
    r = requests.get(f"{API_URL}/market/summary", timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
def fetch_prices(ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    r = requests.get(
        f"{API_URL}/symbols/{quote(ticker, safe='')}/prices",
        params={"start": start.isoformat(), "end": end.isoformat()},
        timeout=15,
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def _price_chart(df: pd.DataFrame, ticker: str, kind: str):
    fig = go.Figure()
    if kind == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name=ticker))
        fig.update_layout(xaxis_rangeslider_visible=False)
    else:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["adj_close"], mode="lines", name=ticker))
    fig.update_layout(title=f"{ticker} price", height=420,
                      margin=dict(l=10, r=10, t=40, b=10))
    return fig


def render_market():
    try:
        symbols = fetch_symbols()
    except requests.RequestException:
        st.error("Cannot reach the API.")
        return
    tickers = [s["ticker"] for s in symbols]

    # Summary table
    try:
        summ = pd.DataFrame(fetch_summary())
        if not summ.empty:
            summ = summ.rename(columns={
                "ticker": "Ticker", "name": "Name", "as_of": "As of",
                "close": "Close", "prev_close": "Prev close",
                "change_pct": "Change %"})
            st.dataframe(summ.round(2), hide_index=True, use_container_width=True)
    except requests.RequestException:
        st.warning("Summary unavailable.")

    # Controls
    c1, c2, c3 = st.columns([2, 3, 2])
    ticker = c1.selectbox("Symbol", tickers, key="mk_symbol")
    today = dt.date.today()
    rng = c2.date_input(
        "Date range",
        value=(today - dt.timedelta(days=365), today),
        min_value=today - dt.timedelta(days=365 * 6),
        max_value=today, key="mk_range")
    kind = c3.radio("Chart", ["Line", "Candlestick"], horizontal=True, key="mk_kind")
    if not isinstance(rng, tuple) or len(rng) != 2:
        st.info("Select a start and end date.")
        return
    start, end = rng

    try:
        df = fetch_prices(ticker, start, end)
    except requests.RequestException:
        st.error("Failed to load prices.")
        return
    if df.empty:
        st.warning("No data for this range.")
        return

    last = df.index.max().date()
    if (today - last).days > STALE_DAYS:
        st.warning(f"Data may be stale. Latest stored date: {last}.")

    st.plotly_chart(_price_chart(df, ticker, kind), use_container_width=True)

    # Returns (adjusted close)
    ret = df["adj_close"].pct_change().dropna() * 100
    fig = go.Figure(go.Bar(x=ret.index, y=ret.values, name="Daily return %"))
    fig.update_layout(title="Daily returns (%)", height=300,
                      margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Rolling volatility (annualized)
    win = st.selectbox("Volatility window (days)", [10, 20, 30, 60],
                       index=1, key="mk_win")
    vol = (df["adj_close"].pct_change().rolling(win).std() * np.sqrt(252) * 100).dropna()
    if vol.empty:
        st.info("Range too short for this window.")
    else:
        fig = go.Figure(go.Scatter(x=vol.index, y=vol.values, mode="lines"))
        fig.update_layout(title=f"{win}-day rolling volatility (annualized %)",
                          height=300, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Normalized comparison
    st.subheader("Normalized comparison (base 100)")
    defaults = [t for t in ("^GSPC", "^DJI", "^IXIC") if t in tickers]
    picks = st.multiselect("Symbols", tickers, default=defaults, key="mk_cmp")
    if len(picks) >= 2:
        frames = {}
        for t in picks:
            d = fetch_prices(t, start, end)
            if not d.empty:
                frames[t] = d["adj_close"]
        if len(frames) >= 2:
            comb = pd.concat(frames, axis=1).dropna()
            if comb.empty:
                st.info("No overlapping dates.")
            else:
                norm = comb / comb.iloc[0] * 100
                fig = go.Figure()
                for col in norm.columns:
                    fig.add_trace(go.Scatter(x=norm.index, y=norm[col],
                                             mode="lines", name=col))
                fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Only dates present in all selected symbols are shown.")
    else:
        st.caption("Select at least 2 symbols.")