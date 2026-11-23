import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.set_page_config(page_title="StockDash", layout="wide")
st.title("StockDash")

try:
    r = requests.get(f"{BACKEND_URL}/health", timeout=5)
    r.raise_for_status()
    st.success(f"Backend: {r.json()}")
except requests.RequestException as e:
    st.error(f"Backend unreachable: {e}")