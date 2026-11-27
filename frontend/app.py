import extra_streamlit_components as stx
import streamlit as st

import auth
from market_page import render_market
from forecast_page import render_forecast

st.set_page_config(page_title="StockDash", layout="wide")

cm = stx.CookieManager(key="cookie_manager")
auth.try_restore(cm)

if st.session_state.get("access_token") and st.sidebar.button("Log out"):
    auth.logout()


def render_login() -> None:
    st.title("StockDash")
    tab_login, tab_register = st.tabs(["Log in", "Register"])
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            err = auth.login(email, password)
            if err:
                st.error(err)
    with tab_register:
        with st.form("register_form"):
            r_email = st.text_input("Email", key="reg_email")
            r_password = st.text_input("Password", type="password", key="reg_pw")
            r_submitted = st.form_submit_button("Create account")
        if r_submitted:
            err = auth.register(r_email, r_password)
            if err:
                st.error(err)
            else:
                st.success("Account created. Log in from the first tab.")


gate = st.empty()
if not st.session_state.get("access_token"):
    with gate.container():
        render_login()
    if st.session_state.get("access_token"):
        gate.empty()

auth.flush_cookie(cm)

if not st.session_state.get("access_token"):
    st.stop()

st.title("StockDash")
me = auth.api("GET", "/auth/me")
if me.status_code == 200:
    st.sidebar.write(me.json()["email"])
    health = auth.api("GET", "/health")
    if health.ok:
        st.sidebar.success(f"Backend: {health.json()}")
    else:
        st.sidebar.error("Backend error: " + health.text)
elif not st.session_state.get("access_token"):
    st.rerun()
else:
    st.error("Could not load session")

auth.flush_cookie(cm)

tab_market, tab_forecast, tab_watch = st.tabs(["Market", "Forecast", "Watchlist / Alerts"])
with tab_market:
    render_market()
with tab_forecast:
    render_forecast()
with tab_watch:
    st.info("Watchlist / Alerts: M6")
