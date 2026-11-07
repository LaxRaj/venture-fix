"""Tiny re-export so modules that only need to read a model's JSON reply do not import the Groq client."""

from .groq_client import extract_json_object as first_object  # noqa: F401
