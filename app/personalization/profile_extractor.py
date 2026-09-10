"""
Turns free text ("I'm 20, I work in sales, total beginner") into a UserProfile.

Deterministic keyword/regex extraction runs FIRST and always. If an LLM is
configured it runs second and is allowed to fill in only the fields the
deterministic pass could not resolve -- it never overwrites a field the rules
already matched with high confidence. That ordering is the whole point: the
platform behaves identically with or without an API key on the common cases,
and the LLM only adds reach on the phrasings a keyword list cannot cover.

Every field carries a confidence score so the orchestrator knows whether to
ask a short onboarding question instead of guessing.
"""

from __future__ import annotations

import re

from app.core.schemas import UserProfile, EXPERIENCE_LEVELS, ROLES, LEARNING_GOALS

# ------------------------------------------------------------------ keyword tables

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sales": ("sales", "salesperson", "account executive", "business development", "bdr", "quota", "deals", "crm"),
    "marketing": ("marketing", "campaign", "seo", "brand", "growth marketer", "advertising", "content marketer"),
    "hr": ("hr", "human resources", "people team", "recruit", "recruiter", "talent", "attrition", "payroll"),
    "operations": ("operations", "ops", "supply chain", "logistics", "warehouse", "fulfilment", "fulfillment"),
    "finance": ("finance", "accounting", "accountant", "financial analyst", "budget", "revenue reporting"),
    "data_cleaner": ("data cleaner", "data cleaning", "messy data", "clean data", "data entry", "data quality"),
    "analyst": ("analyst", "business analyst", "data analyst", "reporting analyst", "bi "),
    "student": ("student", "studying", "at university", "at college", "undergrad", "in school"),
}

EXPERIENCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "beginner": ("beginner", "complete beginner", "no idea", "never done", "no experience", "new to",
                 "just starting", "starting out", "zero background", "absolutely no", "don't know anything",
                 "not technical", "non-technical", "novice", "from scratch"),
    "intermediate": ("intermediate", "some experience", "a bit of", "basics", "know the basics", "comfortable with excel",
                     "used pandas", "some python", "dabbled", "self-taught"),
    "advanced": ("advanced", "experienced", "expert", "years of experience", "senior", "i build models",
                 "machine learning engineer", "data scientist", "proficient", "fluent in python"),
}

GOAL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "visualization": ("visuali", "chart", "graph", "plot", "dashboard", "see my data", "bar chart", "line chart"),
    "data_cleaning": ("clean", "messy", "missing value", "duplicate", "tidy", "data quality", "fix my data",
                      "inconsistent", "outlier"),
    "eda": ("explore", "exploratory", "eda", "patterns", "what's in my data", "summary statistics", "descriptive"),
    "feature_engineering": ("feature engineering", "features", "derive column", "transform column"),
    "machine_learning": ("machine learning", "ml", "model", "train a model", "algorithm", "ai model"),
    "prediction": ("predict", "forecast", "projection", "what will happen", "estimate future"),
    "business_decisions": ("decision", "insight", "strategy", "improve my business", "make better calls", "roi"),
    "understand_dataset": ("understand my data", "understand my dataset", "what my data means", "make sense of"),
}

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sales": ("sales data", "deals", "revenue", "pipeline", "crm data"),
    "marketing": ("campaign data", "ad data", "marketing data", "conversion"),
    "hr": ("employee data", "hr data", "attrition data", "headcount"),
    "operations": ("inventory", "supply chain data", "logistics data", "shipment"),
    "finance": ("financial data", "budget data", "expenses", "transactions"),
}

# Matched as regexes rather than fixed phrases so "my sales data", "my HR
# dataset" and "have campaign data" all register, not just a bare "my data".
_DATA_NOUN = r"(?:data|dataset|csv|spreadsheet|excel|file|records|numbers)"
DATASET_POSITIVE = (
    re.compile(rf"\bmy\s+(?:\w+\s+){{0,2}}{_DATA_NOUN}\b", re.I),
    re.compile(rf"\b(?:i\s+have|i've\s+got|ive\s+got|we\s+have|have|got|working\s+with|work\s+with)\s+(?:some\s+|a\s+|an\s+)?(?:\w+\s+){{0,2}}{_DATA_NOUN}\b", re.I),
    re.compile(r"\b(?:uploaded|attached|here is my|here's my)\b", re.I),
)
DATASET_NEGATIVE = (
    re.compile(r"\b(?:i\s+(?:don'?t|do\s+not)\s+have|haven'?t\s+got|no)\s+(?:any\s+)?(?:own\s+)?(?:\w+\s+){0,1}(?:data|dataset|csv|spreadsheet|file)\b", re.I),
)

# "20 years old", "i am 20", "aged 20" -- but not "20 years of experience"
AGE_PATTERNS = (
    re.compile(r"\b(\d{1,2})\s*(?:years?\s*old|yrs?\s*old|y/o|yo)\b", re.I),
    re.compile(r"\b(?:i am|i'm|im|aged|age)\s+(\d{1,2})\b(?!\s*years?\s+of\s+experience)", re.I),
)

NAME_PATTERNS = (
    re.compile(r"\bmy name is\s+([A-Z][a-zA-Z'-]+)", re.I),
    re.compile(r"\bi(?:'m| am)\s+([A-Z][a-zA-Z'-]+)(?:[,.]|\s+and\b|\s+i\b|$)"),
    re.compile(r"\bthis is\s+([A-Z][a-zA-Z'-]+)", re.I),
)

# Words that follow "I'm" but are never a name -- stops "I'm beginner" -> name="Beginner"
_NOT_NAMES = set(EXPERIENCE_LEVELS) | {
    "a", "an", "the", "new", "working", "trying", "looking", "learning", "not", "very",
    "just", "still", "really", "totally", "completely", "in", "at", "from", "interested",
    "keen", "curious", "confused", "struggling", "good", "bad", "ok", "okay", "fine",
}


def _first_keyword_hit(text: str, table: dict[str, tuple[str, ...]]) -> tuple[str | None, float, str | None]:
    """
    Returns (key, confidence, matched_phrase). Longer phrases win over shorter
    ones so "data analyst" beats a bare "analyst", and the confidence reflects
    how specific the match was.
    """
    best_key, best_len, best_phrase = None, 0, None
    for key, phrases in table.items():
        for phrase in phrases:
            if phrase in text and len(phrase) > best_len:
                best_key, best_len, best_phrase = key, len(phrase), phrase
    if best_key is None:
        return None, 0.0, None
    confidence = 0.9 if best_len >= 8 else 0.75
    return best_key, confidence, best_phrase


def _extract_age(text: str) -> int | None:
    for pattern in AGE_PATTERNS:
        match = pattern.search(text)
        if match:
            age = int(match.group(1))
            if 10 <= age <= 99:
                return age
    return None


def _extract_name(original_text: str) -> str | None:
    for pattern in NAME_PATTERNS:
        match = pattern.search(original_text)
        if match:
            candidate = match.group(1).strip()
            if candidate.lower() not in _NOT_NAMES and len(candidate) > 1:
                return candidate.capitalize()
    return None


def _extract_dataset_flag(text: str) -> tuple[bool | None, float]:
    """Negatives are checked first -- "I don't have any data" contains a
    data noun and would otherwise read as a positive."""
    for pattern in DATASET_NEGATIVE:
        if pattern.search(text):
            return False, 0.85
    for pattern in DATASET_POSITIVE:
        if pattern.search(text):
            return True, 0.8
    return None, 0.0


def extract_profile_rules(text: str, base: UserProfile | None = None) -> UserProfile:
    """
    The deterministic pass. Always runs, never needs an API key, and is what
    the tests pin the platform's behaviour to.
    """
    profile = base or UserProfile()
    lowered = " " + text.lower().strip() + " "
    profile.raw_statements = (profile.raw_statements or []) + [text.strip()]

    name = _extract_name(text)
    if name and not profile.name:
        profile.name = name
        profile.confidence["name"] = 0.8

    age = _extract_age(lowered)
    if age and not profile.age:
        profile.age = age
        profile.confidence["age"] = 0.9

    role, role_conf, role_phrase = _first_keyword_hit(lowered, ROLE_KEYWORDS)
    if role and role_conf > profile.confidence.get("role", 0.0):
        profile.role = role
        profile.confidence["role"] = role_conf
        if not profile.profession and role_phrase:
            profile.profession = role_phrase.strip()

    level, level_conf, _ = _first_keyword_hit(lowered, EXPERIENCE_KEYWORDS)
    if level and level_conf > profile.confidence.get("experience_level", 0.0):
        profile.experience_level = level
        profile.confidence["experience_level"] = level_conf

    goal, goal_conf, _ = _first_keyword_hit(lowered, GOAL_KEYWORDS)
    if goal and goal_conf > profile.confidence.get("learning_goal", 0.0):
        if profile.confidence.get("learning_goal", 0.0) > 0:
            # a previously stated goal isn't discarded, it becomes secondary
            prior = profile.learning_goal
            if prior and prior != goal and prior not in profile.secondary_goals:
                profile.secondary_goals.append(prior)
        profile.learning_goal = goal
        profile.confidence["learning_goal"] = goal_conf

    domain, domain_conf, _ = _first_keyword_hit(lowered, DOMAIN_KEYWORDS)
    if domain and domain_conf > profile.confidence.get("domain", 0.0):
        profile.domain = domain
        profile.confidence["domain"] = domain_conf
    elif not profile.domain and profile.confidence.get("role", 0) >= 0.75 and profile.role in DOMAIN_KEYWORDS:
        # a stated role implies the dataset's likely domain, at lower confidence
        profile.domain = profile.role
        profile.confidence["domain"] = 0.6

    has_data, data_conf = _extract_dataset_flag(lowered)
    if has_data is not None and data_conf > profile.confidence.get("dataset_available", 0.0):
        profile.dataset_available = has_data
        profile.confidence["dataset_available"] = data_conf
        if has_data and profile.domain:
            profile.dataset_type = profile.domain

    # A data cleaner who never named a goal is obviously here for cleaning.
    if profile.role == "data_cleaner" and profile.confidence.get("learning_goal", 0.0) < 0.5:
        profile.learning_goal = "data_cleaning"
        profile.confidence["learning_goal"] = 0.7

    return profile


def extract_profile_llm(text: str, profile: UserProfile) -> tuple[UserProfile, bool]:
    """
    The optional second pass. Only fills fields the rules left below 0.5
    confidence, so an LLM can never overturn a phrase the rules matched
    explicitly. Returns (profile, used_llm).
    """
    from app.llm.llm_client import get_llm_client
    from app.llm.prompts import PROFILER_SYSTEM, PROFILER_USER

    client = get_llm_client()
    if not client.enabled:
        return profile, False

    parsed = client.complete_json(PROFILER_SYSTEM, PROFILER_USER.format(text=text), max_tokens=400)
    if not isinstance(parsed, dict):
        return profile, False

    def maybe_set(field: str, value, valid: tuple = ()) -> None:
        if value in (None, "", "null"):
            return
        if valid and value not in valid:
            return
        if profile.confidence.get(field, 0.0) >= 0.5:
            return   # the rules already decided this one
        setattr(profile, field, value)
        profile.confidence[field] = 0.65   # below a rule match on purpose

    maybe_set("name", parsed.get("name"))
    if isinstance(parsed.get("age"), int) and 10 <= parsed["age"] <= 99:
        maybe_set("age", parsed["age"])
    maybe_set("profession", parsed.get("profession"))
    maybe_set("role", parsed.get("role"), ROLES)
    maybe_set("experience_level", parsed.get("experience_level"), EXPERIENCE_LEVELS)
    maybe_set("learning_goal", parsed.get("learning_goal"), LEARNING_GOALS)
    maybe_set("domain", parsed.get("domain"))
    if isinstance(parsed.get("dataset_available"), bool):
        maybe_set("dataset_available", parsed["dataset_available"])

    return profile, True


def extract_profile(text: str, base: UserProfile | None = None, use_llm: bool = True) -> tuple[UserProfile, bool]:
    """Rules first, LLM only to fill the gaps. Returns (profile, used_llm)."""
    profile = extract_profile_rules(text, base)
    used_llm = False
    if use_llm and profile.missing_critical_fields():
        profile, used_llm = extract_profile_llm(text, profile)
    return profile, used_llm


# ------------------------------------------------------------------ onboarding

ONBOARDING_QUESTIONS = {
    "role": "What kind of work do you do? (for example sales, marketing, HR, operations, or studying)",
    "experience_level": "How comfortable are you with data right now -- complete beginner, some basics, or pretty confident?",
    "learning_goal": "What would you most like to get out of this -- understanding your data, cleaning it up, making charts, or building a prediction?",
    "dataset_available": "Do you have your own data file (a CSV or spreadsheet) you'd like to work with?",
}


def next_onboarding_questions(profile: UserProfile, limit: int = 2) -> list[str]:
    """
    At most `limit` questions at a time. The brief was explicit that a giant
    questionnaire is the wrong experience, so the system asks for the one or
    two things it genuinely could not infer and starts teaching regardless.
    """
    return [ONBOARDING_QUESTIONS[f] for f in profile.missing_critical_fields()[:limit]
            if f in ONBOARDING_QUESTIONS]
