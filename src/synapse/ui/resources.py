"""One thread-safe service shared across Streamlit reruns and sessions."""

import atexit
import os
from pathlib import Path

import streamlit as st

from synapse.models import SynthesisConfig
from synapse.search import TavilySearch
from synapse.service import ResearchService
from synapse.synthesis import GeminiSynthesis


def release(service: ResearchService) -> None:
    service.close()


@st.cache_resource(show_spinner=False, max_entries=1, on_release=release)
def get_service(data_dir: str) -> ResearchService:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    enabled = os.environ.get("SYNAPSE_ENABLE_LIVE") == "1"
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    synthesis_enabled = (
        os.environ.get("SYNAPSE_ENABLE_SYNTHESIS") == "1"
        and os.environ.get("SYNAPSE_GEMINI_FREE_TIER") == "1"
        and bool(gemini_key)
    )
    adapter = None
    if synthesis_enabled:
        config = SynthesisConfig(
            model=os.environ.get("SYNAPSE_GEMINI_MODEL", "gemini-3.5-flash-lite")
        )
        adapter = GeminiSynthesis(gemini_key, config=config)
    service = ResearchService(
        Path(data_dir),
        search=TavilySearch(key) if key and enabled else None,
        live_enabled=enabled,
        synthesis=adapter,
        synthesis_enabled=synthesis_enabled,
    )
    atexit.register(service.close)
    return service
