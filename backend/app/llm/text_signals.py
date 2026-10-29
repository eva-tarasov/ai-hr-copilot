"""Small shared language signals for conservative offline evidence checks."""

import re

# Match words and short phrases, not substrings inside technology names.
NEGATIVE_EXPERIENCE = re.compile(
    r"\b(?:"
    r"never\s+(?:worked|used|developed|built)"
    r"|(?:have|has|had)\s+(?:no\s+experience|not\s+(?:worked|used|built|developed))"
    r"|(?:did|do|does)\s+not\s+(?:use|work|have)"
    r"|(?:don['’]t|doesn['’]t|didn['’]t)\s+(?:use|work|have)"
    r"|no\s+(?:hands-on\s+|professional\s+)?experience|not\s+used"
    r"|(?:не|никогда\s+не)\s+(?:работал(?:а|и)?|использовал(?:а|и)?)"
    r"|нет\s+опыта(?:\s+работы)?|не\s+име(?:ю|ет|ем|ют)\s+опыта"
    r")\b",
    re.IGNORECASE,
)

DIRECT_EXPERIENCE = re.compile(
    r"\b(?:experience|used|built|worked\s+with|implemented|developed|led"
    r"|работал(?:а|и)?|использовал(?:а|и)?|опыт\s+работы)\b",
    re.IGNORECASE,
)

WEAK_EXPERIENCE = re.compile(
    r"\b(?:familiar\s+with|interested\s+in|learning|знаком(?:а)?\s+с|изучаю)\b",
    re.IGNORECASE,
)
