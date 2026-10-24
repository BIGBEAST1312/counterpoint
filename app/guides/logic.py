# Feature 3 · Fix guides | Owner: Priyesh Patel
# AI disclosure: Used AI for concept explanations, understanding syntax and debugging guidance.
import re

from app.core.config import PROBLEM_TYPES

from .models import Guide

_WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def search_score(guide: Guide, query: str) -> int:
    """US-15: every query word must appear somewhere. Title matches rank above matches
    found only in the steps. Hyphens are ignored, so 'wifi' matches 'Wi-Fi'."""
    q = words(query.replace("-", ""))
    if not q:
        return 0
    title = words(guide.title.replace("-", ""))
    body = words(" ".join(s.text for s in guide.steps).replace("-", "")) | words(guide.before_you_start.replace("-", ""))
    type_words = words(PROBLEM_TYPES.get(guide.problem_type, "").replace("-", ""))
    if not q <= (title | body | type_words):
        return 0
    return 10 * len(q & title) + len(q & body) + len(q & type_words)
