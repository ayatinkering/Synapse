"""One thread-safe service shared across Streamlit reruns and sessions."""

import atexit
from pathlib import Path

import streamlit as st

from synapse.service import ResearchService


def release(service: ResearchService) -> None:
    service.close()


@st.cache_resource(show_spinner=False, max_entries=1, on_release=release)
def get_service(data_dir: str) -> ResearchService:
    service = ResearchService(Path(data_dir))
    atexit.register(service.close)
    return service
