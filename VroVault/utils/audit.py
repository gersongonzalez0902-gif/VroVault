"""
VroVault - Password Auditor
============================
Strength scoring, duplicate detection, and common-pattern detection.
Uses zxcvbn for realistic entropy estimation.
"""

import re
import logging
from typing import List, Dict, Any, Tuple

try:
    import zxcvbn as _zxcvbn
    _ZXCVBN_AVAILABLE = True
except ImportError:
    _ZXCVBN_AVAILABLE = False

logger = logging.getLogger(__name__)

# Strength labels aligned to zxcvbn scores 0-4
STRENGTH_LABELS = ["Muy débil", "Débil", "Media", "Fuerte", "Muy fuerte"]
STRENGTH_COLORS = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#27ae60"]

# Common trivial patterns worth flagging regardless of length
_COMMON_PATTERNS = re.compile(
    r"^(1234|password|qwerty|abc|000|111|123456|admin|letmein|welcome)",
    re.IGNORECASE,
)


# ── Individual scoring ───────────────────────────────────────────────────────

def score_password(password: str) -> Dict[str, Any]:
    """
    Return a rich scoring dict for a single password.

    Keys:
        score       int  0-4 (zxcvbn scale)
        label       str  human label
        color       str  hex colour for the UI
        entropy     float  estimated bits
        crack_time  str  human-readable crack estimate
        suggestions list[str]  improvement hints
        is_common   bool
    """
    if not password:
        return {
            "score": 0, "label": STRENGTH_LABELS[0], "color": STRENGTH_COLORS[0],
            "entropy": 0.0, "crack_time": "instant", "suggestions": [], "is_common": False,
        }

    is_common = bool(_COMMON_PATTERNS.match(password))

    if _ZXCVBN_AVAILABLE:
        try:
            result      = _zxcvbn.zxcvbn(password)
            score       = result["score"]
            crack_time  = result["crack_times_display"]["offline_slow_hashing_1e4_per_second"]
            suggestions = result["feedback"]["suggestions"]
            entropy     = result.get("guesses_log10", 0) * 3.32  # log2 approx
        except Exception as exc:
            logger.warning("zxcvbn failed: %s", exc)
            score, crack_time, suggestions, entropy = _fallback_score(password)
    else:
        score, crack_time, suggestions, entropy = _fallback_score(password)

    # Downgrade if common pattern detected
    if is_common and score > 1:
        score = 1
        suggestions = ["Avoid common words and patterns."] + suggestions

    return {
        "score":       score,
        "label":       STRENGTH_LABELS[score],
        "color":       STRENGTH_COLORS[score],
        "entropy":     entropy,
        "crack_time":  crack_time,
        "suggestions": suggestions,
        "is_common":   is_common,
    }


def _fallback_score(password: str) -> Tuple[int, str, List[str], float]:
    """Simple heuristic when zxcvbn is unavailable."""
    length   = len(password)
    has_upper  = bool(re.search(r"[A-Z]", password))
    has_lower  = bool(re.search(r"[a-z]", password))
    has_digit  = bool(re.search(r"\d",    password))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", password))

    classes = sum([has_upper, has_lower, has_digit, has_symbol])
    entropy = length * (classes * 1.5)  # rough approximation

    if length < 8:
        score = 0
    elif length < 10 or classes < 2:
        score = 1
    elif length < 12 or classes < 3:
        score = 2
    elif length < 16 or classes < 4:
        score = 3
    else:
        score = 4

    hints = []
    if not has_upper:    hints.append("Add uppercase letters.")
    if not has_lower:    hints.append("Add lowercase letters.")
    if not has_digit:    hints.append("Add numbers.")
    if not has_symbol:   hints.append("Add symbols.")
    if length < 12:      hints.append("Use at least 12 characters.")

    times = ["instant", "seconds", "hours", "months", "centuries"]
    return score, times[score], hints, float(entropy)


# ── Batch audit ──────────────────────────────────────────────────────────────

def audit_credentials(credentials: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Audit a list of credential dicts (each must have 'password', 'service', 'id').

    Returns:
        {
            "average_score":   float,
            "weak":            list of cred dicts with score < 2,
            "duplicates":      list of groups (each group = list of cred dicts sharing a password),
            "breached_common": list of cred dicts flagged as common pattern,
            "strength_dist":   {label: count, ...},
        }
    """
    scores: Dict[int, Dict]   = {}  # cred_id -> score_dict
    pw_map: Dict[str, List]   = {}  # password -> [cred dicts]

    for cred in credentials:
        pwd     = cred.get("password", "")
        cred_id = cred.get("id", 0)
        sc      = score_password(pwd)
        scores[cred_id] = sc

        # Group by exact password for duplicate detection
        if pwd:
            pw_map.setdefault(pwd, []).append(cred)

    # Build outputs
    weak            = [c for c in credentials if scores.get(c["id"], {}).get("score", 0) < 2]
    duplicates      = [group for group in pw_map.values() if len(group) > 1]
    breached_common = [c for c in credentials if scores.get(c["id"], {}).get("is_common", False)]

    dist: Dict[str, int] = {label: 0 for label in STRENGTH_LABELS}
    total_score = 0
    for sc in scores.values():
        dist[sc["label"]] += 1
        total_score += sc["score"]

    avg = (total_score / len(scores)) if scores else 0.0

    return {
        "average_score":   avg,
        "weak":            weak,
        "duplicates":      duplicates,
        "breached_common": breached_common,
        "strength_dist":   dist,
        "per_credential":  scores,
    }


def strength_bar_value(score: int) -> float:
    """Map score 0-4 to 0.0-1.0 for progress bars."""
    return score / 4.0
