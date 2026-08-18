"""Additive Wide CPR strategy classification.

This module deliberately does not modify the existing Setup or Signal_* fields.
It creates a separate strategy vocabulary for Wide CPR consolidation and
range-breakout states using only information available at the session close.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import pandas as pd


WIDE_FIELDS = (
    "Strategy_Type",
    "Strategy_Setup",
    "Strategy_Confirmation",
    "Strategy_Explanation",
)

WIDE_CLASS = "Wide"
NARROW_CLASS = "Narrow"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _as_bool(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "aligned", "confirmed"}:
        return True
    if text in {"false", "0", "no", "n", "opposes", "rejected"}:
        return False
    return None


def _as_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _position(value: Any) -> str:
    """Normalize current repository and legacy position spellings."""
    text = "" if _is_missing(value) else str(value).strip().lower()
    if "above" in text:
        return "above"
    if "below" in text:
        return "below"
    if "inside" in text or "within" in text:
        return "inside"
    return "unknown"


def _trend_state(row: Mapping[str, Any], direction: str) -> str:
    above_50 = _as_bool(row.get("Above_SMA50"))
    above_100 = _as_bool(row.get("Above_SMA100"))
    if above_50 is None or above_100 is None:
        return "unavailable"
    if direction == "up":
        aligned = above_50 and above_100
    else:
        aligned = not above_50 and not above_100
    if aligned:
        return "aligned"
    if above_50 != above_100:
        return "mixed"
    return "opposes"


def _participation_state(row: Mapping[str, Any]) -> str:
    """Use the existing Value_Ratio as the available participation proxy.

    A ratio of at least 1.0 means current value traded is at or above the
    available rolling baseline. Missing values remain explicitly unavailable.
    """
    value_ratio = _as_float(row.get("Value_Ratio"))
    if value_ratio is None:
        return "unavailable"
    return "confirmed" if value_ratio >= 1.0 else "light"


def _strategy_type(row: Mapping[str, Any]) -> str:
    cpr_class = "" if _is_missing(row.get("CPR_Class")) else str(row.get("CPR_Class")).strip()
    if cpr_class == WIDE_CLASS:
        return "Wide CPR"
    if cpr_class == NARROW_CLASS:
        return "Narrow CPR"
    return "Standard CPR"


def classify_wide_row(row: Mapping[str, Any]) -> Dict[str, str]:
    """Return additive Wide CPR fields for one completed-session row.

    Wide CPR rules:

    * A Wide CPR with price inside the CPR is a consolidation/watch state.
    * A close above the CPR is a confirmed upside breakout only when both
      available trend fields align and Value_Ratio confirms participation.
    * A close below the CPR follows the symmetric downside rule.
    * Missing confirmations produce a Watch/Unavailable state rather than an
      unqualified breakout.
    * Non-Wide CPR rows receive a descriptive strategy type but no Wide setup.
    """
    strategy_type = _strategy_type(row)
    if strategy_type != "Wide CPR":
        return {
            "Strategy_Type": strategy_type,
            "Strategy_Setup": "Not applicable",
            "Strategy_Confirmation": "Not applicable",
            "Strategy_Explanation": f"{strategy_type}; Wide CPR rules not applied",
        }

    position = _position(row.get("Price_Position"))
    trend_up = _trend_state(row, "up")
    trend_down = _trend_state(row, "down")
    participation = _participation_state(row)

    if position == "inside":
        explanation = "Wide CPR + close inside CPR; consolidation/range watch"
        if trend_up == "unavailable" or participation == "unavailable":
            explanation += "; confirmation inputs unavailable"
            confirmation = "Unavailable"
        else:
            confirmation = "Watch"
        return {
            "Strategy_Type": "Wide CPR",
            "Strategy_Setup": "Wide Consolidation",
            "Strategy_Confirmation": confirmation,
            "Strategy_Explanation": explanation,
        }

    if position == "above":
        confirmed = trend_up == "aligned" and participation == "confirmed"
        if confirmed:
            setup = "Wide Upside Breakout"
            confirmation = "Confirmed"
            explanation = "Wide CPR + close above CPR + trend aligned + participation confirmed"
        else:
            setup = "Wide Upside Watch"
            confirmation = "Unavailable" if "unavailable" in {trend_up, participation} else "Watch"
            explanation = (
                "Wide CPR + close above CPR; "
                f"trend {trend_up}; participation {participation}"
            )
        return {
            "Strategy_Type": "Wide CPR",
            "Strategy_Setup": setup,
            "Strategy_Confirmation": confirmation,
            "Strategy_Explanation": explanation,
        }

    if position == "below":
        confirmed = trend_down == "aligned" and participation == "confirmed"
        if confirmed:
            setup = "Wide Downside Breakout"
            confirmation = "Confirmed"
            explanation = "Wide CPR + close below CPR + trend aligned + participation confirmed"
        else:
            setup = "Wide Downside Watch"
            confirmation = "Unavailable" if "unavailable" in {trend_down, participation} else "Watch"
            explanation = (
                "Wide CPR + close below CPR; "
                f"trend {trend_down}; participation {participation}"
            )
        return {
            "Strategy_Type": "Wide CPR",
            "Strategy_Setup": setup,
            "Strategy_Confirmation": confirmation,
            "Strategy_Explanation": explanation,
        }

    return {
        "Strategy_Type": "Wide CPR",
        "Strategy_Setup": "Wide Watch",
        "Strategy_Confirmation": "Unavailable",
        "Strategy_Explanation": "Wide CPR; price position unavailable",
    }


def attach_wide_strategy(frame: pd.DataFrame) -> pd.DataFrame:
    """Add Wide CPR strategy fields without changing existing columns."""
    out = frame.copy()
    values = [classify_wide_row(row) for row in out.to_dict(orient="records")]
    for field in WIDE_FIELDS:
        out[field] = [item[field] for item in values]
    return out


def wide_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a deterministic, confirmation-first Wide CPR view."""
    if frame.empty:
        return frame.copy()
    out = frame if set(WIDE_FIELDS).issubset(frame.columns) else attach_wide_strategy(frame)
    out = out[out["Strategy_Type"] == "Wide CPR"].copy()
    if out.empty:
        return out.reset_index(drop=True)
    confirmation_rank = {"Confirmed": 0, "Watch": 1, "Unavailable": 2, "Not applicable": 3}
    out["_confirmation_rank"] = out["Strategy_Confirmation"].map(confirmation_rank).fillna(9)
    sort_cols = ["_confirmation_rank"]
    ascending = [True]
    if "Signal_Score" in out.columns:
        sort_cols.append("Signal_Score")
        ascending.append(False)
    if "CPR_Width_Pct" in out.columns:
        sort_cols.append("CPR_Width_Pct")
        ascending.append(False)
    out = out.sort_values(sort_cols, ascending=ascending, na_position="last")
    return out.drop(columns=["_confirmation_rank"]).reset_index(drop=True)
