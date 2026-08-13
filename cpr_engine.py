"""
CPR Calculation and Screening Engine

This module implements the Central Pivot Range (CPR) calculation and screening logic.
It is decoupled from the data provider to allow easy replacement of data sources.

Formulas:
- Pivot = (Previous High + Previous Low + Previous Close) / 3
- BC (Bottom Central) = (Previous High + Previous Low) / 2
- TC (Top Central) = 2 × Pivot − BC
- CPR Top = max(BC, TC)
- CPR Bottom = min(BC, TC)
- CPR Width = CPR Top − CPR Bottom
- CPR Width % = (CPR Width / Previous Close) × 100
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CPRBias(Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"


class PricePosition(Enum):
    ABOVE = "Above CPR"
    BELOW = "Below CPR"
    INSIDE = "Inside CPR"
    NEAR = "Near CPR"
    UNKNOWN = "Unknown"


class VirginCPRStatus(Enum):
    BULLISH = "Bullish Virgin"
    BEARISH = "Bearish Virgin"
    ANY = "Any Virgin"
    NONE = "None"
    DEVELOPING = "Developing"


class CPRWidthClass(Enum):
    TOO_NARROW = "Too Narrow"
    NARROW = "Narrow"
    MEDIUM = "Medium"
    WIDE = "Wide"
    TOO_WIDE = "Too Wide"


class CPROverlay(Enum):
    HIGHER = "Higher CPR"
    LOWER = "Lower CPR"
    INSIDE = "Inside prior CPR"
    OUTSIDE = "Outside prior CPR"
    OVERLAPPING = "Overlapping"
    UNKNOWN = "Unknown"


class OpenVsCPR(Enum):
    ABOVE = "Opened above"
    BELOW = "Opened below"
    INSIDE = "Opened inside"
    UNKNOWN = "Unknown"


@dataclass
class CPRResult:
    """Container for CPR calculation results for a single symbol"""
    symbol: str
    company_name: Optional[str]
    current_price: Optional[float]
    previous_close: Optional[float]
    previous_high: Optional[float]
    previous_low: Optional[float]
    pivot: Optional[float]
    bc: Optional[float]
    tc: Optional[float]
    cpr_bottom: Optional[float]
    cpr_top: Optional[float]
    cpr_width: Optional[float]
    cpr_width_pct: Optional[float]
    bias: Optional[CPRBias]
    position: Optional[PricePosition]
    virgin_cpr: Optional[VirginCPRStatus]
    data_timestamp: Optional[str]
    data_status: str
    current_high: Optional[float]  # For Virgin CPR detection
    current_low: Optional[float]    # For Virgin CPR detection
    width_class: Optional[CPRWidthClass] = None
    overlay: Optional[CPROverlay] = None
    open_vs_cpr: Optional[OpenVsCPR] = None
    day_open: Optional[float] = None
    dist_from_pivot_pct: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame conversion"""
        return {
            'Symbol': self.symbol,
            'Company': self.company_name or '',
            'Current Price': self.current_price,
            'Day Open': self.day_open,
            'Previous Close': self.previous_close,
            'CPR Bottom': self.cpr_bottom,
            'Pivot': self.pivot,
            'CPR Top': self.cpr_top,
            'CPR Width': self.cpr_width,
            'Width %': self.cpr_width_pct,
            'Width Class': self.width_class.value if self.width_class else None,
            'Bias': self.bias.value if self.bias else None,
            'Overlay': self.overlay.value if self.overlay else None,
            'Position': self.position.value if self.position else None,
            'Open vs CPR': self.open_vs_cpr.value if self.open_vs_cpr else None,
            'Dist from Pivot %': self.dist_from_pivot_pct,
            'Virgin CPR': self.virgin_cpr.value if self.virgin_cpr else None,
            'Data Timestamp': self.data_timestamp or '',
            'Data Status': self.data_status,
            'Current High': self.current_high,
            'Current Low': self.current_low
        }


class CPREngine:
    """
    Central Pivot Range calculation and screening engine.
    """
    
    def __init__(
        self,
        narrow_max_pct: float = 0.25,
        wide_min_pct: float = 0.75,
        near_cpr_distance_pct: float = 0.5,
        min_price: Optional[float] = None,
        min_volume: Optional[float] = None,
        min_market_cap: Optional[float] = None,
        require_above_sma20: bool = False,
        require_above_sma50: bool = False
    ):
        """
        Initialize CPR screening engine with filter parameters.
        
        Args:
            narrow_max_pct: Maximum Width % for "Narrow" CPR (default 0.25%)
            wide_min_pct: Minimum Width % for "Wide" CPR (default 0.75%)
            near_cpr_distance_pct: Distance % from CPR for "Near CPR" position
            min_price: Minimum current price filter
            min_volume: Minimum average volume filter
            min_market_cap: Minimum market cap filter
            require_above_sma20: Require price above 20-day SMA
            require_above_sma50: Require price above 50-day SMA
        """
        self.narrow_max_pct = narrow_max_pct
        self.wide_min_pct = wide_min_pct
        self.too_narrow_max_pct = 0.15
        self.too_wide_min_pct = 1.50
        self.near_cpr_distance_pct = near_cpr_distance_pct
        self.min_price = min_price
        self.min_volume = min_volume
        self.min_market_cap = min_market_cap
        self.require_above_sma20 = require_above_sma20
        self.require_above_sma50 = require_above_sma50
    
    def calculate_cpr(
        self,
        prev_high: float,
        prev_low: float,
        prev_close: float
    ) -> Dict[str, float]:
        """
        Calculate CPR levels from previous session OHLC.
        
        Returns dict with: pivot, bc, tc, cpr_bottom, cpr_top, cpr_width, cpr_width_pct
        """
        if prev_close <= 0:
            raise ValueError("Previous close must be positive")
        
        pivot = (prev_high + prev_low + prev_close) / 3.0
        bc = (prev_high + prev_low) / 2.0
        tc = 2.0 * pivot - bc
        cpr_top = max(bc, tc)
        cpr_bottom = min(bc, tc)
        cpr_width = cpr_top - cpr_bottom
        cpr_width_pct = (cpr_width / prev_close) * 100.0
        
        return {
            'pivot': pivot,
            'bc': bc,
            'tc': tc,
            'cpr_bottom': cpr_bottom,
            'cpr_top': cpr_top,
            'cpr_width': cpr_width,
            'cpr_width_pct': cpr_width_pct
        }
    
    def determine_bias(self, pivot: float, bc: float) -> CPRBias:
        """Determine previous-session bias"""
        if pivot > bc:
            return CPRBias.BULLISH
        elif pivot < bc:
            return CPRBias.BEARISH
        else:
            return CPRBias.NEUTRAL
    
    def determine_position(
        self,
        current_price: float,
        cpr_bottom: float,
        cpr_top: float
    ) -> PricePosition:
        """Determine current price position relative to CPR"""
        if current_price is None or cpr_bottom is None or cpr_top is None:
            return PricePosition.UNKNOWN
        
        cpr_range = cpr_top - cpr_bottom
        near_threshold = cpr_range + (cpr_top * self.near_cpr_distance_pct / 100.0)
        
        if current_price > cpr_top:
            # Check if "Near" (within threshold above CPR)
            if current_price <= cpr_top * (1 + self.near_cpr_distance_pct / 100.0):
                return PricePosition.NEAR
            return PricePosition.ABOVE
        elif current_price < cpr_bottom:
            # Check if "Near" (within threshold below CPR)
            if current_price >= cpr_bottom * (1 - self.near_cpr_distance_pct / 100.0):
                return PricePosition.NEAR
            return PricePosition.BELOW
        else:
            return PricePosition.INSIDE
    
    def determine_virgin_cpr(
        self,
        current_high: Optional[float],
        current_low: Optional[float],
        cpr_top: float,
        cpr_bottom: float,
        is_session_open: bool = True
    ) -> VirginCPRStatus:
        """
        Determine Virgin CPR status.
        
        Bullish Virgin: Current session's Low > CPR Top
        Bearish Virgin: Current session's High < CPR Bottom
        
        Mark as "Developing" if session is still open (can change before close).
        """
        if current_high is None or current_low is None:
            return VirginCPRStatus.NONE
        
        bullish_virgin = current_low > cpr_top
        bearish_virgin = current_high < cpr_bottom
        
        if is_session_open and (bullish_virgin or bearish_virgin):
            return VirginCPRStatus.DEVELOPING
        elif bullish_virgin:
            return VirginCPRStatus.BULLISH
        elif bearish_virgin:
            return VirginCPRStatus.BEARISH
        else:
            return VirginCPRStatus.NONE

    def determine_width_class(self, width_pct: float) -> CPRWidthClass:
        """Shah: narrow = close near mid-range; wide = close far from mid-range."""
        if width_pct <= self.too_narrow_max_pct:
            return CPRWidthClass.TOO_NARROW
        if width_pct <= self.narrow_max_pct:
            return CPRWidthClass.NARROW
        if width_pct >= self.too_wide_min_pct:
            return CPRWidthClass.TOO_WIDE
        if width_pct >= self.wide_min_pct:
            return CPRWidthClass.WIDE
        return CPRWidthClass.MEDIUM

    def determine_overlay(
        self,
        today_top: float,
        today_bottom: float,
        prior_top: Optional[float],
        prior_bottom: Optional[float],
    ) -> CPROverlay:
        """Today's CPR vs previous day's CPR. Higher band = bullish overlay (Shah)."""
        if prior_top is None or prior_bottom is None:
            return CPROverlay.UNKNOWN
        if today_bottom > prior_top:
            return CPROverlay.HIGHER
        if today_top < prior_bottom:
            return CPROverlay.LOWER
        if today_top <= prior_top and today_bottom >= prior_bottom:
            return CPROverlay.INSIDE
        if today_top >= prior_top and today_bottom <= prior_bottom:
            return CPROverlay.OUTSIDE
        return CPROverlay.OVERLAPPING

    def determine_open_vs_cpr(
        self,
        day_open: Optional[float],
        cpr_bottom: float,
        cpr_top: float,
    ) -> OpenVsCPR:
        if day_open is None:
            return OpenVsCPR.UNKNOWN
        if day_open > cpr_top:
            return OpenVsCPR.ABOVE
        if day_open < cpr_bottom:
            return OpenVsCPR.BELOW
        return OpenVsCPR.INSIDE
    
    def screen_symbol(
        self,
        symbol: str,
        company_name: Optional[str],
        prev_high: float,
        prev_low: float,
        prev_close: float,
        current_price: Optional[float] = None,
        current_high: Optional[float] = None,
        current_low: Optional[float] = None,
        current_volume: Optional[float] = None,
        market_cap: Optional[float] = None,
        sma20: Optional[float] = None,
        sma50: Optional[float] = None,
        data_timestamp: Optional[str] = None,
        data_status: str = "OK",
        is_session_open: bool = True,
        current_open: Optional[float] = None,
        prior_high: Optional[float] = None,
        prior_low: Optional[float] = None,
        prior_close: Optional[float] = None,
    ) -> Optional[CPRResult]:
        """
        Screen a single symbol and return CPR result if it passes filters.
        
        Returns None if symbol fails filters or has invalid data.
        """
        # Validate required data
        if prev_high is None or prev_low is None or prev_close is None:
            return CPRResult(
                symbol=symbol,
                company_name=company_name,
                current_price=current_price,
                previous_close=prev_close,
                previous_high=None,
                previous_low=None,
                pivot=None,
                bc=None,
                tc=None,
                cpr_bottom=None,
                cpr_top=None,
                cpr_width=None,
                cpr_width_pct=None,
                bias=None,
                position=None,
                virgin_cpr=None,
                data_timestamp=data_timestamp,
                data_status="Data unavailable",
                current_high=None,
                current_low=None
            )
        
        if prev_close <= 0:
            return CPRResult(
                symbol=symbol,
                company_name=company_name,
                current_price=None,
                previous_close=prev_close,
                previous_high=prev_high,
                previous_low=prev_low,
                pivot=None,
                bc=None,
                tc=None,
                cpr_bottom=None,
                cpr_top=None,
                cpr_width=None,
                cpr_width_pct=None,
                bias=None,
                position=None,
                virgin_cpr=None,
                data_timestamp=data_timestamp,
                data_status="Invalid data (zero/negative close)",
                current_high=None,
                current_low=None
            )
        
        # Calculate CPR
        cpr_data = self.calculate_cpr(prev_high, prev_low, prev_close)
        
        # Determine bias
        bias = self.determine_bias(cpr_data['pivot'], cpr_data['bc'])
        
        # Determine position
        position = self.determine_position(
            current_price,
            cpr_data['cpr_bottom'],
            cpr_data['cpr_top']
        ) if current_price else PricePosition.UNKNOWN
        
        # Determine Virgin CPR — Shah: price never touches the band
        virgin_cpr = self.determine_virgin_cpr(
            current_high,
            current_low,
            cpr_data['cpr_top'],
            cpr_data['cpr_bottom'],
            is_session_open
        )

        width_class = self.determine_width_class(cpr_data['cpr_width_pct'])
        open_vs_cpr = self.determine_open_vs_cpr(
            current_open, cpr_data['cpr_bottom'], cpr_data['cpr_top']
        )

        overlay = CPROverlay.UNKNOWN
        if prior_high is not None and prior_low is not None and prior_close is not None and prior_close > 0:
            prior_cpr = self.calculate_cpr(prior_high, prior_low, prior_close)
            overlay = self.determine_overlay(
                cpr_data['cpr_top'],
                cpr_data['cpr_bottom'],
                prior_cpr['cpr_top'],
                prior_cpr['cpr_bottom'],
            )

        dist_from_pivot_pct = None
        if current_price is not None and cpr_data['pivot']:
            dist_from_pivot_pct = ((current_price - cpr_data['pivot']) / cpr_data['pivot']) * 100.0
        
        # Apply filters
        if not self._passes_filters(
            current_price=current_price,
            cpr_width_pct=cpr_data['cpr_width_pct'],
            current_volume=current_volume,
            market_cap=market_cap,
            sma20=sma20,
            sma50=sma50
        ):
            return None
        
        return CPRResult(
            symbol=symbol,
            company_name=company_name,
            current_price=current_price,
            previous_close=prev_close,
            previous_high=prev_high,
            previous_low=prev_low,
            pivot=cpr_data['pivot'],
            bc=cpr_data['bc'],
            tc=cpr_data['tc'],
            cpr_bottom=cpr_data['cpr_bottom'],
            cpr_top=cpr_data['cpr_top'],
            cpr_width=cpr_data['cpr_width'],
            cpr_width_pct=cpr_data['cpr_width_pct'],
            bias=bias,
            position=position,
            virgin_cpr=virgin_cpr,
            data_timestamp=data_timestamp,
            data_status=data_status,
            current_high=current_high,
            current_low=current_low,
            width_class=width_class,
            overlay=overlay,
            open_vs_cpr=open_vs_cpr,
            day_open=current_open,
            dist_from_pivot_pct=dist_from_pivot_pct
        )
    
    def _passes_filters(
        self,
        current_price: Optional[float],
        cpr_width_pct: float,
        current_volume: Optional[float],
        market_cap: Optional[float],
        sma20: Optional[float],
        sma50: Optional[float]
    ) -> bool:
        """Check if symbol passes all configured filters"""
        # Price filter
        if self.min_price is not None and current_price is not None:
            if current_price < self.min_price:
                return False
        
        # Volume filter
        if self.min_volume is not None and current_volume is not None:
            if current_volume < self.min_volume:
                return False
        
        # Market cap filter
        if self.min_market_cap is not None and market_cap is not None:
            if market_cap < self.min_market_cap:
                return False
        
        # SMA filters
        if self.require_above_sma20 and sma20 is not None and current_price is not None:
            if current_price < sma20:
                return False
        
        if self.require_above_sma50 and sma50 is not None and current_price is not None:
            if current_price < sma50:
                return False
        
        return True
    
    def screen_dataframe(
        self,
        df: pd.DataFrame,
        cpr_width_filter: str = "Any",  # "Any", "Narrow", "Wide", "Custom"
        position_filter: str = "Any",    # "Any", "Above CPR", "Below CPR", "Inside CPR", "Near CPR"
        bias_filter: str = "Any",        # "Any", "Bullish", "Bearish", "Neutral"
        virgin_cpr_filter: str = "Any",  # "Any", "Bullish Virgin", "Bearish Virgin", "Any Virgin"
        custom_width_min: Optional[float] = None,
        custom_width_max: Optional[float] = None,
        overlay_filter: str = "Any",
        open_vs_cpr_filter: str = "Any",
        width_class_filter: str = "Any",
    ) -> pd.DataFrame:
        """
        Apply screening filters to a DataFrame of CPR results.
        
        Args:
            df: DataFrame with CPR result columns
            cpr_width_filter: "Any", "Narrow", "Wide", or "Custom"
            position_filter: "Any", "Above CPR", "Below CPR", "Inside CPR", "Near CPR"
            bias_filter: "Any", "Bullish", "Bearish", "Neutral"
            virgin_cpr_filter: "Any", "Bullish Virgin", "Bearish Virgin", "Any Virgin"
            custom_width_min: Minimum Width % for custom filter
            custom_width_max: Maximum Width % for custom filter
        
        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df
        
        mask = pd.Series(True, index=df.index)
        
        # CPR Width filter
        if cpr_width_filter == "Narrow":
            mask &= df['Width %'] <= self.narrow_max_pct
        elif cpr_width_filter == "Wide":
            mask &= df['Width %'] >= self.wide_min_pct
        elif cpr_width_filter == "Custom":
            if custom_width_min is not None:
                mask &= df['Width %'] >= custom_width_min
            if custom_width_max is not None:
                mask &= df['Width %'] <= custom_width_max
        
        # Position filter
        if position_filter != "Any":
            mask &= df['Position'] == position_filter
        
        # Bias filter
        if bias_filter != "Any":
            mask &= df['Bias'] == bias_filter
        
        # Virgin CPR filter
        if virgin_cpr_filter == "Bullish Virgin":
            mask &= df['Virgin CPR'].isin(['Bullish Virgin', 'Developing'])
        elif virgin_cpr_filter == "Bearish Virgin":
            mask &= df['Virgin CPR'].isin(['Bearish Virgin', 'Developing'])
        elif virgin_cpr_filter == "Any Virgin":
            mask &= df['Virgin CPR'].isin(['Bullish Virgin', 'Bearish Virgin', 'Developing'])

        if overlay_filter != "Any" and 'Overlay' in df.columns:
            mask &= df['Overlay'] == overlay_filter

        if open_vs_cpr_filter != "Any" and 'Open vs CPR' in df.columns:
            mask &= df['Open vs CPR'] == open_vs_cpr_filter

        if width_class_filter != "Any" and 'Width Class' in df.columns:
            mask &= df['Width Class'] == width_class_filter
        
        return df[mask].reset_index(drop=True)


def validate_cpr_formulas():
    """
    Validate CPR formulas with the provided test case.
    
    Test case:
    - Previous High = 110
    - Previous Low = 100
    - Previous Close = 106
    
    Expected:
    - Pivot = 105.333333...
    - BC = 105.00
    - TC = 105.666666...
    - CPR Bottom = 105.00
    - CPR Top = 105.666666...
    - CPR Width = 0.666666...
    - CPR Width % ≈ 0.6289%
    """
    engine = CPREngine()
    
    prev_high = 110.0
    prev_low = 100.0
    prev_close = 106.0
    
    result = engine.calculate_cpr(prev_high, prev_low, prev_close)
    
    print("=== CPR Formula Validation ===")
    print(f"Input: High={prev_high}, Low={prev_low}, Close={prev_close}")
    print()
    print(f"Pivot = {result['pivot']:.10f} (expected: 105.333333...)")
    print(f"BC = {result['bc']:.10f} (expected: 105.00)")
    print(f"TC = {result['tc']:.10f} (expected: 105.666666...)")
    print(f"CPR Bottom = {result['cpr_bottom']:.10f} (expected: 105.00)")
    print(f"CPR Top = {result['cpr_top']:.10f} (expected: 105.666666...)")
    print(f"CPR Width = {result['cpr_width']:.10f} (expected: 0.666666...)")
    print(f"CPR Width % = {result['cpr_width_pct']:.10f}% (expected: ~0.6289%)")
    print()
    
    # Assertions
    assert abs(result['pivot'] - 105.3333333333) < 0.0001, "Pivot mismatch"
    assert abs(result['bc'] - 105.0) < 0.0001, "BC mismatch"
    assert abs(result['tc'] - 105.6666666667) < 0.0001, "TC mismatch"
    assert abs(result['cpr_bottom'] - 105.0) < 0.0001, "CPR Bottom mismatch"
    assert abs(result['cpr_top'] - 105.6666666667) < 0.0001, "CPR Top mismatch"
    assert abs(result['cpr_width'] - 0.6666666667) < 0.0001, "CPR Width mismatch"
    assert abs(result['cpr_width_pct'] - 0.6289308176) < 0.0001, "CPR Width % mismatch"
    
    print("✓ All CPR formula validations PASSED")
    print()
    
    # Test edge cases
    print("=== Edge Case Tests ===")
    
    # Test zero previous close
    try:
        engine.calculate_cpr(110, 100, 0)
        print("✗ Zero close test FAILED (should raise ValueError)")
    except ValueError:
        print("✓ Zero close test PASSED (correctly raises ValueError)")
    
    # Test negative previous close
    try:
        engine.calculate_cpr(110, 100, -5)
        print("✗ Negative close test FAILED (should raise ValueError)")
    except ValueError:
        print("✓ Negative close test PASSED (correctly raises ValueError)")
    
    # Test bias determination
    bullish_bias = engine.determine_bias(106, 105)  # Pivot > BC
    assert bullish_bias == CPRBias.BULLISH
    print("✓ Bullish bias test PASSED")
    
    bearish_bias = engine.determine_bias(104, 105)  # Pivot < BC
    assert bearish_bias == CPRBias.BEARISH
    print("✓ Bearish bias test PASSED")
    
    neutral_bias = engine.determine_bias(105, 105)  # Pivot == BC
    assert neutral_bias == CPRBias.NEUTRAL
    print("✓ Neutral bias test PASSED")
    
    # Test Virgin CPR
    bullish_virgin = engine.determine_virgin_cpr(108, 106, 105.67, 105.0, is_session_open=False)
    assert bullish_virgin == VirginCPRStatus.BULLISH
    print("✓ Bullish Virgin CPR test PASSED")
    
    bearish_virgin = engine.determine_virgin_cpr(104, 103, 105.67, 105.0, is_session_open=False)
    assert bearish_virgin == VirginCPRStatus.BEARISH
    print("✓ Bearish Virgin CPR test PASSED")
    
    developing = engine.determine_virgin_cpr(108, 106, 105.67, 105.0, is_session_open=True)
    assert developing == VirginCPRStatus.DEVELOPING
    print("✓ Developing Virgin CPR test PASSED")
    
    print()
    print("=== All Tests PASSED ===")


if __name__ == "__main__":
    validate_cpr_formulas()