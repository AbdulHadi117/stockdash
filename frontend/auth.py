import datetime as dt
import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
COOKIE = "sd_refresh"
COOKIE_DAYS = 7
TIMEOUT = 10


def _key(prefix: str) -> str:
    st.session_state["_ck"] = st.session_state.get("_ck", 0) + 1
    return f"{prefix}_{st.session_state['_ck']}"


def _error(r: requests.Response) -> str:
    try:
        detail = r.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list) and all(isinstance(d, str) for d in detail):
        return " ".join(detail)
    if isinstance(detail, str):
        return detail
    return "Request failed"


def _store(data: dict) -> None:
    st.session_state["access_token"] = data["access_token"]
    st.session_state["refresh_token"] = data["refresh_token"]
    st.session_state["pending_cookie"] = data["refresh_token"]
    st.session_state["logged_out"] = False


def flush_cookie(cm) -> None:
    """Write/delete the browser cookie. Must run at top level, not inside a placeholder."""
    token = st.session_state.pop("pending_cookie", None)
    if token:
        cm.set(
            COOKIE,
            token,
            expires_at=dt.datetime.now() + dt.timedelta(days=COOKIE_DAYS),
            key=_key("set"),
        )
    if st.session_state.pop("pending_cookie_delete", False):
        try:
            cm.delete(COOKIE, key=_key("del"))
        except Exception:
            pass


def clear_session() -> None:
    for k in ("access_token", "refresh_token"):
        st.session_state.pop(k, None)
    st.session_state["pending_cookie_delete"] = True


def try_restore(cm) -> None:
    if (
        st.session_state.get("access_token")
        or st.session_state.get("logged_out")
        or st.session_state.get("restore_tried")
    ):
        return
    token = cm.get(COOKIE)
    if not token:
        return  # cookie not loaded yet, or none exists
    st.session_state["restore_tried"] = True
    r = requests.post(
        f"{BACKEND_URL}/auth/refresh", json={"refresh_token": token}, timeout=TIMEOUT
    )
    if r.status_code == 200:
        _store(r.json())
    else:
        st.session_state["pending_cookie_delete"] = True


def login(email: str, password: str) -> str | None:
    r = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=TIMEOUT,
    )
    if r.status_code == 200:
        _store(r.json())
        return None
    return _error(r)


def register(email: str, password: str) -> str | None:
    r = requests.post(
        f"{BACKEND_URL}/auth/register",
        json={"email": email, "password": password},
        timeout=TIMEOUT,
    )
    return None if r.status_code == 201 else _error(r)


def logout() -> None:
    token = st.session_state.get("refresh_token")
    if token:
        try:
            requests.post(
                f"{BACKEND_URL}/auth/logout",
                json={"refresh_token": token},
                timeout=TIMEOUT,
            )
        except requests.RequestException:
            pass
    clear_session()
    st.session_state["logged_out"] = True


def api(method: str, path: str, **kwargs) -> requests.Response:
    """Authenticated call; refreshes once on 401."""

    def call() -> requests.Response:
        headers = {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}
        return requests.request(
            method, f"{BACKEND_URL}{path}", headers=headers, timeout=TIMEOUT, **kwargs
        )

    r = call()
    if r.status_code == 401 and st.session_state.get("refresh_token"):
        rr = requests.post(
            f"{BACKEND_URL}/auth/refresh",
            json={"refresh_token": st.session_state["refresh_token"]},
            timeout=TIMEOUT,
        )
        if rr.status_code == 200:
            _store(rr.json())
            r = call()
        else:
            clear_session()
    return r