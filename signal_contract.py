"""Shared signal labels, scores, and ranking helpers.

The strings are deliberately identical to the current EOD and breakout public
schemas so existing CSVs, static-site filters, and Streamlit consumers remain
compatible.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class SetupLabel(str, Enum):
    LONG = "Long"
    WATCH_LONG = "Watch Long"
    SHORT = "Short"
    WATCH_SHORT = "Watch Short"
    WATCH = "Watch"
    NO_SETUP = "No setup"


class BreakoutSignal(str, Enum):
    LONG = "Long"
    SHORT = "Short"
    WATCH = "Watch"
    NONE = "None"


SETUP_SCORES = {
    SetupLabel.LONG.value: 2,
    SetupLabel.WATCH_LONG.value: 1,
    SetupLabel.SHORT.value: -2,
    SetupLabel.WATCH_SHORT.value: -1,
    SetupLabel.WATCH.value: 0,
    SetupLabel.NO_SETUP.value: 0,
}

BREAKOUT_SIGNAL_RANK = {
    BreakoutSignal.LONG.value: 0,
    BreakoutSignal.SHORT.value: 1,
    BreakoutSignal.WATCH.value: 2,
    BreakoutSignal.NONE.value: 3,
}


def _label_value(label: Any) -> str:
    return str(getattr(label, "value", label))


def setup_score(setup: Any) -> int:
    """Convert an EOD setup label into its signed confluence contribution."""
    return int(SETUP_SCORES.get(_label_value(setup), 0))


def breakout_signal_rank(signal: Any) -> int:
    """Return the stable display rank used by the breakout table."""
    return int(BREAKOUT_SIGNAL_RANK.get(_label_value(signal), 9))
