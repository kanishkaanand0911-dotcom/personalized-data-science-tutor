"""
Profile persistence and the role-aware framing every teaching agent uses.

Kept separate from profile_extractor (which turns text into a profile) and
from state.py (which stores raw JSON): this is the layer that knows how to
describe a learner back to the rest of the system.
"""

from __future__ import annotations

from app.core.schemas import UserProfile
from app.core.state import get_store
from app.personalization.learning_path import ROLE_PROFILES, role_description, role_vocabulary


# Every accessor takes an optional store. The orchestrator runs against an
# injected store (the demo uses a throwaway directory, tests use a temp one),
# and defaulting to the global store here would silently write a learner's
# profile somewhere the caller never reads back.

def load_profile(user_id: str, store=None) -> UserProfile | None:
    raw = (store or get_store()).load(user_id).get("profile")
    return UserProfile.from_dict(raw) if raw else None


def save_profile(user_id: str, profile: UserProfile, store=None) -> None:
    profile.user_id = user_id
    (store or get_store()).update(user_id, profile=profile.to_dict())


def get_or_create_profile(user_id: str, store=None) -> UserProfile:
    return load_profile(user_id, store) or UserProfile(user_id=user_id)


def describe_learner(profile: UserProfile) -> str:
    """One line the prompts and the deterministic text both use, so the LLM
    and fallback paths describe the learner identically."""
    parts = [role_description(profile)]
    if profile.experience_level:
        parts.append(f"at a {profile.experience_level} level")
    if profile.domain:
        parts.append(f"working with {profile.domain} data")
    return ", ".join(parts)


def role_context(profile: UserProfile) -> dict:
    """
    The vocabulary and examples a teaching agent should reach for. This is
    what makes the same concept read differently for HR and for sales without
    writing a separate lesson per role.
    """
    conf = ROLE_PROFILES.get(profile.role, ROLE_PROFILES["general"])
    return {
        "role": profile.role,
        "description": conf["description"],
        "vocabulary": role_vocabulary(profile.role),
        "examples": conf["examples"],
        "experience_level": profile.experience_level,
    }


def profile_summary_lines(profile: UserProfile) -> list[str]:
    """Human-readable profile, for the demo output and the /profile endpoint."""
    lines = []
    if profile.name:
        lines.append(f"Name: {profile.name}")
    if profile.age:
        lines.append(f"Age: {profile.age}")
    lines.append(f"Role: {profile.role.replace('_', ' ').title()}")
    lines.append(f"Experience: {profile.experience_level.title()}")
    lines.append(f"Goal: {profile.learning_goal.replace('_', ' ').title()}")
    if profile.domain:
        lines.append(f"Dataset domain: {profile.domain.title()}")
    lines.append(f"Has own dataset: {'Yes' if profile.dataset_available else 'Not yet'}")
    return lines
