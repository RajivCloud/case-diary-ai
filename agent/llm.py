"""One place for the Claude client, model choice and cost accounting."""

from __future__ import annotations

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("CASEDIARY_MODEL", "claude-opus-5-5")
DEFAULT_EFFORT = os.getenv("CASEDIARY_EFFORT", "medium")

# USD per million tokens for claude-opus-5-5 (input, output, cache read, cache write)
PRICES = {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}


def get_client() -> anthropic.Anthropic:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        try:  # Streamlit Cloud secrets
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


def create(client: anthropic.Anthropic, **kwargs):
    """messages.create with server-side refusal fallback enabled.

    `fallbacks="default"` asks the API to re-run a request on a recommended model if
    the safety classifier declines it (crime-investigation text can occasionally trip it).
    """
    return client.beta.messages.create(
        model=MODEL,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        cache_control={"type": "ephemeral"},  # cache the stable prefix (system + tools + history)
        **kwargs,
    )


class Usage:
    def __init__(self) -> None:
        self.input = self.output = self.cache_read = self.cache_write = 0
        self.calls = 0

    def add(self, u) -> None:
        self.calls += 1
        self.input += u.input_tokens or 0
        self.output += u.output_tokens or 0
        self.cache_read += getattr(u, "cache_read_input_tokens", 0) or 0
        self.cache_write += getattr(u, "cache_creation_input_tokens", 0) or 0

    @property
    def cost(self) -> float:
        return (self.input * PRICES["input"] + self.output * PRICES["output"]
                + self.cache_read * PRICES["cache_read"] + self.cache_write * PRICES["cache_write"]) / 1e6

    def as_dict(self) -> dict:
        return {"api_calls": self.calls, "input_tokens": self.input, "output_tokens": self.output,
                "cache_read_tokens": self.cache_read, "cache_write_tokens": self.cache_write,
                "cost_usd": round(self.cost, 4)}
