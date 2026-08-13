"""NSE cash vs F&O universes for CPR screening.

Built from NSE EQUITY_L, F&O market-lot, and index constituent files.
Yahoo tickers use the `.NS` suffix.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

UNIVERSE_DIR = Path(__file__).resolve().parent / "universes"

UNIVERSE_FILES = {
    "Nifty 500 (cash + F&O)": "nifty500.txt",
    "Cash stocks (Nifty 500, not F&O)": "cash_nifty500.txt",
    "F&O stocks": "fo_stocks.txt",
    "Nifty 50": "nifty50.txt",
    "Nifty Next 50": "nifty_next50.txt",
    "Nifty Midcap 150": "nifty_midcap150.txt",
    "Nifty Smallcap 250": "nifty_smallcap250.txt",
}

INDEX_UNIVERSES = list(UNIVERSE_FILES.keys())


def _read_symbol_file(filename: str) -> List[str]:
    path = UNIVERSE_DIR / filename
    if not path.exists():
        return []
    symbols = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        symbols.append(line)
    return symbols


def to_yahoo(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol:
        return symbol
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}.NS"


def from_yahoo(symbol: str) -> str:
    return symbol.strip().upper().replace(".NS", "").replace(".BO", "")


@lru_cache(maxsize=1)
def fo_symbol_set() -> frozenset:
    return frozenset(from_yahoo(s) for s in _read_symbol_file("fo_stocks.txt"))


def classify_symbol(symbol: str) -> str:
    bare = from_yahoo(symbol)
    return "F&O" if bare in fo_symbol_set() else "Cash"


def load_universe(name: str) -> List[str]:
    filename = UNIVERSE_FILES.get(name)
    if not filename:
        return []
    return [to_yahoo(s) for s in _read_symbol_file(filename)]


def universe_counts(symbols: List[str]) -> Tuple[int, int, int]:
    fo = fo_symbol_set()
    cash_n = 0
    fo_n = 0
    for symbol in symbols:
        if from_yahoo(symbol) in fo:
            fo_n += 1
        else:
            cash_n += 1
    return len(symbols), cash_n, fo_n
