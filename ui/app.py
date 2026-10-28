"""Minimal Streamlit HTTP client for the local backend."""

import os

import httpx
import streamlit as st


st.title("AI HR Copilot")

backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

try:
    response = httpx.get(f"{backend_url}/health", timeout=3.0)
    response.raise_for_status()
    if response.json() == {"status": "ok"}:
        st.success("Backend is available")
    else:
        st.error("Backend returned an unexpected health response.")
except (httpx.HTTPError, ValueError):
    st.error("Backend is unavailable. Start the FastAPI server and refresh this page.")
