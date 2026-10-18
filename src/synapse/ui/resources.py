"""One thread-safe service shared across Streamlit reruns and sessions."""

import atexit
import os
from pathlib import Path

import streamlit as st

from synapse.search import TavilySearch
from synapse.service import ResearchService


def release(service: ResearchService) -> None:
    service.close()


@st.cache_resource(show_spinner=False, max_entries=1, on_release=release)
def get_service(data_dir: str) -> ResearchService:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    enabled = os.environ.get("SYNAPSE_ENABLE_LIVE") == "1"
    service = ResearchService(
        Path(data_dir), search=TavilySearch(key) if key and enabled else None, live_enabled=enabled
    )
    atexit.register(service.close)
    return service
