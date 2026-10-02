"""Models for generalization ladders and verification."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from pgm.config import LadderSource


class LadderRungProposal(BaseModel):
    """A proposed generalization level for a memory."""
    level: int = Field(ge=0, description="Ladder level (0 = exact)")
    text: str = Field(description="The generalized text")
    source: LadderSource = Field(description="Where this proposal came from")
    
    # Optionally store verification metadata if we want to run the verifier
    # before writing to DB
    verification_passed: bool = Field(default=False)
    verification_details: dict = Field(default_factory=dict)


class VerificationResult(BaseModel):
    """Result of running the verifier on a proposed rung."""
    is_valid: bool
    
    # Specific checks
    entails: bool = Field(default=False, description="Finer level entails this level")
    monotonic: bool = Field(default=False, description="Less informative than finer level")
    no_leakage: bool = Field(default=False, description="Does not leak identifying details (e.g. CEO of Apple -> Tim Cook)")
    
    reasoning: str = Field(default="")
