"""Strict schemas for AI evaluation output."""

from typing import Literal

from pydantic import BaseModel, Field


class GrammarError(BaseModel):
    """One grammar issue detected in the user's messages."""

    original: str
    corrected: str
    explanation_vi: str


class EvaluationResult(BaseModel):
    """Structured evaluation returned by the AI evaluation service."""

    grammar_score: int = Field(ge=0, le=100)
    vocabulary_score: int = Field(ge=0, le=100)
    eq_score: int = Field(ge=0, le=100)
    cefr_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    grammar_errors: list[GrammarError]
    suggested_replies: list[str]
    overall_feedback_vi: str
