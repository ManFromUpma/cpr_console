"""
Data Provider Module for CPR Screening Console

Live market data uses Yahoo Finance (yfinance) because the Perplexity Finance
connector (`perplexity_finance_connector`) only exists inside Perplexity Computer.

Yahoo covers NSE tickers with a `.NS` suffix. Quotes can be delayed and are
for research use only — not exchange-grade realtime.
"""

from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional

import pandas as pd
import pytz


class DataProviderError(Exception):
    """Custom exception for data provider errors"""
    pass


def _timezone_name(tz) -> str:
    if isinstance(tz, str):
        return tz
    return getattr(tz, "zone", None) or str(tz)


def is_market_session_open(session_timezone: str) -> bool:
    """Approximate cash-session hours for the configured timezone."""
    tz = pytz.timezone(session_timezone)
    now = datetime.now(tz)
    if now.weekday() >= 5:
        return False

    hours = {
        "Asia/Kolkata": (dt_time(9, 15), dt_time(15, 30)),
        "America/New_York": (dt_time(9, 30), dt_time(16, 0)),
        "Europe/London": (dt_time(8, 0), dt_time(16, 30)),
    }
    start, end = hours.get(session_timezone, (dt_time(9, 15), dt_time(15, 30)))
    return start <= now.time() <= end


class SessionAwareProvider:
    """Shared market-hours helper for all data providers."""

    def is_session_open(self) -> bool:
        return is_market_session_open(_timezone_name(self.session_timezone))


def _row_float(row, key: str) -> Optional[float]:
    if key not in row.index and key not in getattr(row, "keys", lambda: [])():
        return None
    try:
        value = row[key]
    except Exception:
        return None
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return float(value)


class OHLCVData:
    """Container for OHLCV data with metadata"""

    def __init__(
        self,
        symbol: str,
        df: pd.DataFrame,
        data_source: str,
        fetch_timestamp: datetime,
        session_timezone: str = "Asia/Kolkata",
        current_quote: Optional[Dict] = None,
    ):
        self.symbol = symbol
        self.df = df  # Must have columns: ['open', 'high', 'low', 'close', 'volume']
        self.data_source = data_source
        self.fetch_timestamp = fetch_timestamp
        self.session_timezone = pytz.timezone(_timezone_name(session_timezone))
        self.current_quote = current_quote or {}

    def _index_date(self, ts) -> Optional[datetime.date]:
        stamp = pd.Timestamp(ts)
        if pd.isna(stamp):
            return None
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert(self.session_timezone)
        return stamp.date()

    def _session_today(self):
        return datetime.now(self.session_timezone).date()

    def get_completed_sessions(self) -> pd.DataFrame:
        """Daily bars used as CPR input (excludes today's session)."""
        if self.df is None or self.df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        today = self._session_today()
        last_date = self._index_date(self.df.index[-1])
        if last_date is not None and last_date >= today and len(self.df) >= 2:
            return self.df.iloc[:-1]
        if last_date is not None and last_date >= today:
            return pd.DataFrame(columns=self.df.columns)
        return self.df

    def get_previous_session(self) -> Optional[Dict]:
        """OHLC of the last completed session used as CPR input (not today)."""
        completed = self.get_completed_sessions()
        if completed is None or completed.empty:
            return None
        row = completed.iloc[-1]
        close = _row_float(row, "close")
        high = _row_float(row, "high")
        low = _row_float(row, "low")
        if close is None or high is None or low is None:
            return None
        return {
            "open": _row_float(row, "open"),
            "high": high,
            "low": low,
            "close": close,
            "volume": _row_float(row, "volume"),
            "date": self._index_date(completed.index[-1]),
        }

    def get_session_before_previous(self) -> Optional[Dict]:
        """OHLC two completed sessions back — used for CPR overlay."""
        completed = self.get_completed_sessions()
        if completed is None or len(completed) < 2:
            return None
        row = completed.iloc[-2]
        close = _row_float(row, "close")
        high = _row_float(row, "high")
        low = _row_float(row, "low")
        if close is None or high is None or low is None:
            return None
        return {
            "open": _row_float(row, "open"),
            "high": high,
            "low": low,
            "close": close,
            "volume": _row_float(row, "volume"),
            "date": self._index_date(completed.index[-2]),
        }

    def get_current_quote(self) -> Dict:
        """Latest price / session high-low, preferring live intraday quote."""
        quote = dict(self.current_quote or {})
        today = self._session_today()

        if self.df is not None and not self.df.empty:
            last = self.df.iloc[-1]
            last_date = self._index_date(self.df.index[-1])
            if last_date == today:
                quote.setdefault("price", _row_float(last, "close"))
                quote.setdefault("day_high", _row_float(last, "high"))
                quote.setdefault("day_low", _row_float(last, "low"))
                quote.setdefault("open", _row_float(last, "open"))
                quote.setdefault("volume", _row_float(last, "volume"))
            elif quote.get("price") is None:
                quote["price"] = _row_float(last, "close")

        return quote

    def get_current_price(self) -> Optional[float]:
        """Get current/latest price (may be from incomplete session)"""
        price = self.get_current_quote().get("price")
        if price is not None:
            return float(price)
        if self.df is None or self.df.empty or "close" not in self.df.columns:
            return None
        return float(self.df.iloc[-1]["close"])

    def get_data_status(self) -> str:
        """Determine data quality status"""
        if self.df is None or self.df.empty:
            return "Data unavailable"

        last_date = self._index_date(self.df.index[-1])
        if last_date is None:
            return "Data unavailable"

        today = self._session_today()
        days_old = (today - last_date).days
        if days_old > 2:
            return "Stale"
        if self.current_quote.get("price") is not None:
            return "Live" if is_market_session_open(_timezone_name(self.session_timezone)) else "OK"
        if last_date == today:
            return "OK"
        return "Delayed"

    def is_session_open(self) -> bool:
        return is_market_session_open(_timezone_name(self.session_timezone))


def _extract_symbol_ohlcv(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    if data is None or data.empty:
        return empty

    frame = None
    if isinstance(data.columns, pd.MultiIndex):
        try:
            frame = data[symbol]
        except Exception:
            frame = None
        if frame is None or isinstance(frame, pd.Series):
            for level in range(data.columns.nlevels):
                if symbol in data.columns.get_level_values(level):
                    frame = data.xs(symbol, axis=1, level=level)
                    break
    else:
        frame = data

    if frame is None or isinstance(frame, pd.Series) or frame.empty:
        return empty

    frame = frame.copy()
    frame.columns = [str(c).strip().lower().replace(" ", "_") for c in frame.columns]
    needed = [c for c in ["open", "high", "low", "close", "volume"] if c in frame.columns]
    if "close" not in needed:
        return empty

    out = frame[needed].copy()
    out = out.dropna(subset=["close"])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def _quote_from_intraday(idf: pd.DataFrame) -> Dict:
    if idf is None or idf.empty:
        return {}
    return {
        "price": float(idf["close"].iloc[-1]),
        "day_high": float(idf["high"].max()) if "high" in idf.columns else None,
        "day_low": float(idf["low"].min()) if "low" in idf.columns else None,
        "open": float(idf["open"].iloc[0]) if "open" in idf.columns else None,
        "volume": float(idf["volume"].sum()) if "volume" in idf.columns else None,
        "timestamp": idf.index[-1],
    }


def _yahoo_download_chunked(yf, symbols: List[str], start: str, end: str, interval: str, chunk_size: int = 80):
    """Download Yahoo OHLCV in chunks so large cash universes do not time out."""
    frames = []
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i : i + chunk_size]
        try:
            part = yf.download(
                tickers=chunk,
                start=start,
                end=end,
                interval=interval,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
            if part is not None and not part.empty:
                frames.append(part)
        except Exception as exc:
            print(f"Yahoo daily chunk failed ({chunk[0]}…): {exc}")
    if not frames:
        return pd.DataFrame()
    try:
        return pd.concat(frames, axis=1)
    except Exception:
        return frames[0]


class YahooFinanceDataProvider(SessionAwareProvider):
    """
    Live OHLCV from Yahoo Finance via yfinance.

    NSE symbols must use the `.NS` suffix (e.g. RELIANCE.NS).
    Data may be delayed 0–15 minutes and is not licensed for trading.
    """

    def __init__(self, session_timezone: str = "Asia/Kolkata"):
        self.session_timezone = pytz.timezone(session_timezone)
        self.fetch_timestamp = datetime.now(self.session_timezone)
        self.data_source = "Yahoo Finance daily + 1m (CPR prior-day HLC + today's OHLC)"
        self._cache: Dict[str, OHLCVData] = {}

    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1day",
    ) -> OHLCVData:
        results = self.fetch_multiple_symbols([symbol], lookback_days=60)
        return results.get(
            symbol,
            OHLCVData(
                symbol=symbol,
                df=pd.DataFrame(),
                data_source=self.data_source,
                fetch_timestamp=self.fetch_timestamp,
                session_timezone=_timezone_name(self.session_timezone),
            ),
        )

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        lookback_days: int = 60,
    ) -> Dict[str, OHLCVData]:
        import yfinance as yf

        self.fetch_timestamp = datetime.now(self.session_timezone)
        symbols = [s.strip() for s in symbols if s and s.strip()]
        empty_results = {
            symbol: OHLCVData(
                symbol=symbol,
                df=pd.DataFrame(),
                data_source=self.data_source,
                fetch_timestamp=self.fetch_timestamp,
                session_timezone=_timezone_name(self.session_timezone),
            )
            for symbol in symbols
        }
        if not symbols:
            return empty_results

        end_day = datetime.now(self.session_timezone).date() + timedelta(days=1)
        start_day = datetime.now(self.session_timezone).date() - timedelta(days=max(lookback_days, 5))
        large_universe = len(symbols) > 80
        daily = _yahoo_download_chunked(
            yf,
            symbols,
            start=start_day.isoformat(),
            end=end_day.isoformat(),
            interval="1d",
        )
        if large_universe:
            # Daily bars already include today's developing OHLC; 1m on 200–500 names is too heavy.
            intraday = pd.DataFrame()
            self.data_source = "Yahoo Finance daily (cash + F&O universe)"
        else:
            try:
                intraday = yf.download(
                    tickers=symbols,
                    period="1d",
                    interval="1m",
                    group_by="ticker",
                    auto_adjust=False,
                    threads=True,
                    progress=False,
                )
            except Exception as exc:
                print(f"Yahoo intraday download failed: {exc}")
                intraday = pd.DataFrame()
            self.data_source = "Yahoo Finance daily + 1m (CPR prior-day HLC + today's OHLC)"

        results: Dict[str, OHLCVData] = {}
        for symbol in symbols:
            try:
                df = _extract_symbol_ohlcv(daily, symbol)
                idf = _extract_symbol_ohlcv(intraday, symbol)
                quote = _quote_from_intraday(idf)
                results[symbol] = OHLCVData(
                    symbol=symbol,
                    df=df,
                    data_source=self.data_source,
                    fetch_timestamp=self.fetch_timestamp,
                    session_timezone=_timezone_name(self.session_timezone),
                    current_quote=quote,
                )
            except Exception as exc:
                print(f"Error parsing {symbol}: {exc}")
                results[symbol] = empty_results[symbol]
        return results

    def clear_cache(self):
        self._cache.clear()


class PerplexityFinanceDataProvider(SessionAwareProvider):
    """
    Data provider using Perplexity Finance connector when running inside
    Perplexity Computer. Locally this connector is not installed.
    """

    def __init__(self, session_timezone: str = "Asia/Kolkata"):
        self.session_timezone = pytz.timezone(session_timezone)
        self.fetch_timestamp = datetime.now(self.session_timezone)
        self.data_source = "Perplexity Finance (research use only)"
        self._cache: Dict[str, OHLCVData] = {}

    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1day",
    ) -> OHLCVData:
        cache_key = f"{symbol}_{start_date}_{end_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            from perplexity_finance_connector import finance_ohlcv_histories

            csv_result = finance_ohlcv_histories(
                ticker_symbols=[symbol],
                start_date_yyyy_mm_dd=start_date,
                end_date_yyyy_mm_dd=end_date,
                time_interval=interval,
                fields=["open", "high", "low", "close", "volume"],
            )
            df = pd.read_csv(csv_result["csv_files"][0])
            df.index = pd.to_datetime(df["date"])
            df = df.sort_index()
            df.columns = [str(c).strip().lower() for c in df.columns]
        except ImportError:
            df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        except Exception as exc:
            print(f"Perplexity fetch failed for {symbol}: {exc}")
            df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        ohlcv_data = OHLCVData(
            symbol=symbol,
            df=df,
            data_source=self.data_source,
            fetch_timestamp=self.fetch_timestamp,
            session_timezone=_timezone_name(self.session_timezone),
        )
        self._cache[cache_key] = ohlcv_data
        return ohlcv_data

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        lookback_days: int = 60,
    ) -> Dict[str, OHLCVData]:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.fetch_ohlcv(symbol, start_date, end_date)
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                results[symbol] = OHLCVData(
                    symbol=symbol,
                    df=pd.DataFrame(),
                    data_source=self.data_source,
                    fetch_timestamp=self.fetch_timestamp,
                    session_timezone=_timezone_name(self.session_timezone),
                )
        return results

    def clear_cache(self):
        self._cache.clear()


class MockDataProvider(SessionAwareProvider):
    """
    Mock data provider for testing and demonstration.
    Generates realistic-looking OHLCV data for testing CPR calculations.
    """

    def __init__(self, session_timezone: str = "Asia/Kolkata"):
        self.session_timezone = pytz.timezone(session_timezone)
        self.fetch_timestamp = datetime.now(self.session_timezone)
        self.data_source = "Mock Data (testing only)"

    def fetch_ohlcv(self, symbol: str, start_date: str, end_date: str, interval: str = "1day") -> OHLCVData:
        """Generate mock OHLCV data for testing"""
        import random

        dates = pd.date_range(start=start_date, end=end_date, freq="B")
        base_price = random.uniform(100, 3000)

        data = []
        for date in dates:
            daily_change = random.uniform(-0.03, 0.03)
            open_price = base_price * (1 + random.uniform(-0.01, 0.01))
            close_price = base_price * (1 + daily_change)
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.02))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.02))
            volume = random.randint(100000, 10000000)

            data.append(
                {
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                }
            )
            base_price = close_price

        df = pd.DataFrame(data, index=dates)
        return OHLCVData(
            symbol=symbol,
            df=df,
            data_source=self.data_source,
            fetch_timestamp=self.fetch_timestamp,
            session_timezone=_timezone_name(self.session_timezone),
        )

    def fetch_multiple_symbols(self, symbols: List[str], lookback_days: int = 60) -> Dict[str, OHLCVData]:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        return {symbol: self.fetch_ohlcv(symbol, start_date, end_date) for symbol in symbols}


def get_data_provider(use_mock: bool = False, session_timezone: str = "Asia/Kolkata"):
    """
    Get the appropriate data provider.

    Live mode uses Yahoo Finance locally. If the Perplexity Finance connector
    is installed (Perplexity Computer), that is preferred instead.
    """
    if use_mock:
        return MockDataProvider(session_timezone)

    try:
        from perplexity_finance_connector import finance_ohlcv_histories  # noqa: F401

        return PerplexityFinanceDataProvider(session_timezone)
    except ImportError:
        return YahooFinanceDataProvider(session_timezone)
