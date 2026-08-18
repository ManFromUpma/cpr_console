"""Explainable confirmation-aware scoring for EOD CPR setups.

The scorer is additive: it never changes CPR calculations, existing Setup labels,
shortlist membership, archive filenames, or publication behavior.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


SCORE_FIELDS = (
    "Signal_Direction",
    "Signal_Score",
    "Signal_Grade",
    "Signal_Explanation",
)


def _value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        value = row.get(key)
    else:
        try:
            value = row[key]
        except (KeyError, IndexError, TypeError):
            value = None
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _number(row: Any, key: str) -> float | None:
    value = _value(row, key)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _boolean(row: Any, key: str) -> bool | None:
    value = _value(row, key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)) and not pd.isna(value):
        return bool(value)
    return None


def setup_direction(setup: Any) -> str:
    """Return Long, Short, or Neutral from the existing setup vocabulary."""
    text = "" if setup is None else str(setup)
    if "Long" in text:
        return "Long"
    if "Short" in text:
        return "Short"
    return "Neutral"


def _grade(score: int, direction: str) -> str:
    if direction == "Neutral":
        return "Not applicable"
    if score >= 80:
        return "Strong confirmation"
    if score >= 65:
        return "Confirmed"
    if score >= 50:
        return "Mixed"
    return "Weak confirmation"


def _component(label: str, detail: str, points: int) -> tuple[int, str]:
    return points, f"{label}: {detail} ({points}/20)"


def score_row(row: Any) -> dict[str, Any]:
    """Score one row using only fields available at that session close."""
    direction = setup_direction(_value(row, "Setup"))
    if direction == "Neutral":
        return {
            "Signal_Direction": direction,
            "Signal_Score": 0,
            "Signal_Grade": "Not applicable",
            "Signal_Explanation": "No directional setup; confirmation score not applicable.",
        }

    sign = 1 if direction == "Long" else -1
    components: list[tuple[int, str]] = []

    cpr_class = str(_value(row, "CPR_Class") or "").strip()
    width_pct = _number(row, "CPR_Width_Pct")
    if cpr_class == "Narrow":
        components.append(_component("CPR width", "Narrow", 20))
    elif cpr_class == "Wide":
        components.append(_component("CPR width", "Wide; directional confirmation limited", 8))
    elif width_pct is not None:
        components.append(_component("CPR width", f"{width_pct:.4f}%", 12))
    else:
        components.append(_component("CPR width", "unavailable", 10))

    position = str(_value(row, "Price_Position") or "").strip()
    expected_position = "Above CPR" if direction == "Long" else "Below CPR"
    if position == expected_position:
        components.append(_component("Price location", position, 20))
    elif position == "Inside CPR":
        components.append(_component("Price location", "Inside CPR; watch state", 10))
    elif position:
        components.append(_component("Price location", f"against {direction.lower()} bias", 0))
    else:
        components.append(_component("Price location", "unavailable", 10))

    fast = _boolean(row, "Above_SMA50")
    slow = _boolean(row, "Above_SMA100")
    if fast is None and slow is None:
        components.append(_component("Trend", "unavailable", 10))
    else:
        aligned = 0
        available = 0
        for value in (fast, slow):
            if value is None:
                continue
            available += 1
            if (direction == "Long" and value) or (direction == "Short" and not value):
                aligned += 1
        if available == 2 and aligned == 2:
            points, detail = 20, "aligned with SMA50/SMA100"
        elif aligned > 0:
            points, detail = 12, f"partially aligned ({aligned}/{available})"
        else:
            points, detail = 0, "opposes SMA direction"
        components.append(_component("Trend", detail, points))

    value_ratio = _number(row, "Value_Ratio")
    if value_ratio is None:
        components.append(_component("Participation", "unavailable", 10))
    elif value_ratio >= 1.0:
        components.append(_component("Participation", f"confirmed ({value_ratio:.2f}x)", 20))
    elif value_ratio >= 0.75:
        components.append(_component("Participation", f"moderate ({value_ratio:.2f}x)", 12))
    else:
        components.append(_component("Participation", f"light ({value_ratio:.2f}x)", 4))

    confluence = _number(row, "Confluence_Score")
    if confluence is None:
        components.append(_component("Higher timeframe", "unavailable", 10))
    else:
        aligned_confluence = sign * confluence
        if aligned_confluence >= 4:
            points, detail = 20, f"strongly aligned ({confluence:+.0f})"
        elif aligned_confluence >= 2:
            points, detail = 16, f"aligned ({confluence:+.0f})"
        elif aligned_confluence > 0:
            points, detail = 12, f"slightly aligned ({confluence:+.0f})"
        elif aligned_confluence == 0:
            points, detail = 8, "neutral (0)"
        else:
            points, detail = 0, f"opposes setup ({confluence:+.0f})"
        components.append(_component("Higher timeframe", detail, points))

    score = int(round(sum(points for points, _ in components)))
    explanation = "; ".join(detail for _, detail in components)
    return {
        "Signal_Direction": direction,
        "Signal_Score": max(0, min(100, score)),
        "Signal_Grade": _grade(score, direction),
        "Signal_Explanation": explanation,
    }


def attach_confirmation_score(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with additive Stage 1 score fields."""
    out = frame.copy()
    if out.empty:
        out["Signal_Direction"] = pd.Series(index=out.index, dtype="object")
        out["Signal_Score"] = pd.Series(index=out.index, dtype="int64")
        out["Signal_Grade"] = pd.Series(index=out.index, dtype="object")
        out["Signal_Explanation"] = pd.Series(index=out.index, dtype="object")
        return out
    scored = pd.DataFrame(
        [score_row(row) for row in out.to_dict(orient="records")],
        index=out.index,
    )
    for column in SCORE_FIELDS:
        out[column] = scored[column]
    out["Signal_Score"] = pd.to_numeric(out["Signal_Score"], errors="coerce").fillna(0).astype(int)
    return out


__all__ = ["SCORE_FIELDS", "attach_confirmation_score", "score_row", "setup_direction"]
