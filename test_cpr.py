"""
Unit Tests for CPR Engine

Run with: python test_cpr.py
"""

import unittest
import pandas as pd
import numpy as np
from cpr_engine import CPREngine, CPRBias, PricePosition, VirginCPRStatus, CPRResult


class TestCPRFormulas(unittest.TestCase):
    """Test CPR calculation formulas"""
    
    def setUp(self):
        self.engine = CPREngine()
    
    def test_standard_case(self):
        """Test with provided example: H=110, L=100, C=106"""
        result = self.engine.calculate_cpr(110, 100, 106)
        
        self.assertAlmostEqual(result['pivot'], 105.3333333333, places=4)
        self.assertAlmostEqual(result['bc'], 105.0, places=4)
        self.assertAlmostEqual(result['tc'], 105.6666666667, places=4)
        self.assertAlmostEqual(result['cpr_bottom'], 105.0, places=4)
        self.assertAlmostEqual(result['cpr_top'], 105.6666666667, places=4)
        self.assertAlmostEqual(result['cpr_width'], 0.6666666667, places=4)
        self.assertAlmostEqual(result['cpr_width_pct'], 0.6289308176, places=4)
    
    def test_zero_previous_close(self):
        """Test that zero previous close raises ValueError"""
        with self.assertRaises(ValueError):
            self.engine.calculate_cpr(110, 100, 0)
    
    def test_negative_previous_close(self):
        """Test that negative previous close raises ValueError"""
        with self.assertRaises(ValueError):
            self.engine.calculate_cpr(110, 100, -5)
    
    def test_bullish_bias(self):
        """Test bullish bias detection (Pivot > BC)"""
        bias = self.engine.determine_bias(106, 105)
        self.assertEqual(bias, CPRBias.BULLISH)
    
    def test_bearish_bias(self):
        """Test bearish bias detection (Pivot < BC)"""
        bias = self.engine.determine_bias(104, 105)
        self.assertEqual(bias, CPRBias.BEARISH)
    
    def test_neutral_bias(self):
        """Test neutral bias detection (Pivot == BC)"""
        bias = self.engine.determine_bias(105, 105)
        self.assertEqual(bias, CPRBias.NEUTRAL)


class TestPricePosition(unittest.TestCase):
    """Test price position relative to CPR"""
    
    def setUp(self):
        self.engine = CPREngine(near_cpr_distance_pct=0.5)
    
    def test_above_cpr(self):
        """Test price clearly above CPR and outside the Near threshold"""
        # Near threshold: 105.67 * (1 + 0.5/100) = 106.19835
        position = self.engine.determine_position(106.3, 105.0, 105.67)
        self.assertEqual(position, PricePosition.ABOVE)
    
    def test_below_cpr(self):
        """Test price below CPR"""
        position = self.engine.determine_position(104, 105.0, 105.67)
        self.assertEqual(position, PricePosition.BELOW)
    
    def test_inside_cpr(self):
        """Test price inside CPR"""
        position = self.engine.determine_position(105.3, 105.0, 105.67)
        self.assertEqual(position, PricePosition.INSIDE)
    
    def test_near_cpr_above(self):
        """Test price near CPR (just above)"""
        # 106.0 is above the CPR top but within the 0.5% Near threshold.
        position = self.engine.determine_position(106.0, 105.0, 105.67)
        self.assertEqual(position, PricePosition.NEAR)
    
    def test_none_values(self):
        """Test with None values"""
        position = self.engine.determine_position(None, 105.0, 105.67)
        self.assertEqual(position, PricePosition.UNKNOWN)


class TestVirginCPR(unittest.TestCase):
    """Test Virgin CPR detection"""
    
    def setUp(self):
        self.engine = CPREngine()
    
    def test_bullish_virgin_closed(self):
        """Test bullish Virgin CPR (session closed)"""
        # Current Low (106) > CPR Top (105.67)
        status = self.engine.determine_virgin_cpr(
            current_high=108,
            current_low=106,
            cpr_top=105.67,
            cpr_bottom=105.0,
            is_session_open=False
        )
        self.assertEqual(status, VirginCPRStatus.BULLISH)
    
    def test_bearish_virgin_closed(self):
        """Test bearish Virgin CPR (session closed)"""
        # Current High (104) < CPR Bottom (105.0)
        status = self.engine.determine_virgin_cpr(
            current_high=104,
            current_low=103,
            cpr_top=105.67,
            cpr_bottom=105.0,
            is_session_open=False
        )
        self.assertEqual(status, VirginCPRStatus.BEARISH)
    
    def test_bullish_virgin_developing(self):
        """Test bullish Virgin CPR (session open - developing)"""
        status = self.engine.determine_virgin_cpr(
            current_high=108,
            current_low=106,
            cpr_top=105.67,
            cpr_bottom=105.0,
            is_session_open=True
        )
        self.assertEqual(status, VirginCPRStatus.DEVELOPING)
    
    def test_no_virgin(self):
        """Test no Virgin CPR"""
        status = self.engine.determine_virgin_cpr(
            current_high=107,
            current_low=104,
            cpr_top=105.67,
            cpr_bottom=105.0,
            is_session_open=False
        )
        self.assertEqual(status, VirginCPRStatus.NONE)
    
    def test_higher_overlay(self):
        overlay = self.engine.determine_overlay(110, 108, 105, 104)
        self.assertEqual(overlay.value, "Higher CPR")

    def test_lower_overlay(self):
        overlay = self.engine.determine_overlay(100, 98, 105, 104)
        self.assertEqual(overlay.value, "Lower CPR")

    def test_none_current_data(self):
        """Test with None current data"""
        status = self.engine.determine_virgin_cpr(
            current_high=None,
            current_low=None,
            cpr_top=105.67,
            cpr_bottom=105.0,
            is_session_open=False
        )
        self.assertEqual(status, VirginCPRStatus.NONE)


class TestScreening(unittest.TestCase):
    """Test symbol screening"""
    
    def setUp(self):
        self.engine = CPREngine(
            narrow_max_pct=0.25,
            wide_min_pct=0.75
        )
    
    def test_valid_symbol(self):
        """Test screening a valid symbol"""
        result = self.engine.screen_symbol(
            symbol="TEST.NS",
            company_name="Test Company",
            prev_high=110,
            prev_low=100,
            prev_close=106,
            current_price=107,
            current_high=108,
            current_low=106,
            data_status="OK"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.symbol, "TEST.NS")
        self.assertEqual(result.bias, CPRBias.BULLISH)
        self.assertIsNotNone(result.cpr_top)
        self.assertIsNotNone(result.cpr_bottom)
    
    def test_missing_data(self):
        """Test screening with missing data"""
        result = self.engine.screen_symbol(
            symbol="MISSING.NS",
            company_name=None,
            prev_high=None,
            prev_low=None,
            prev_close=None,
            data_status="Data unavailable"
        )
        
        self.assertIsNotNone(result)  # Should return result with unavailable status
        self.assertEqual(result.data_status, "Data unavailable")
        self.assertIsNone(result.pivot)
    
    def test_zero_close(self):
        """Test screening with zero previous close"""
        result = self.engine.screen_symbol(
            symbol="ZERO.NS",
            company_name=None,
            prev_high=110,
            prev_low=100,
            prev_close=0,
            data_status="Invalid data"
        )
        
        self.assertIsNotNone(result)
        self.assertIn("Invalid", result.data_status)
    
    def test_empty_symbol_list(self):
        """Test screening with empty symbol list"""
        # This is handled at the DataFrame level
        df = pd.DataFrame()
        filtered = self.engine.screen_dataframe(df)
        self.assertTrue(filtered.empty)


class TestDataFrameScreening(unittest.TestCase):
    """Test DataFrame-based screening"""
    
    def setUp(self):
        self.engine = CPREngine(
            narrow_max_pct=0.25,
            wide_min_pct=0.75
        )
        
        # Create test DataFrame
        self.test_df = pd.DataFrame([
            {
                'Symbol': 'NARROW.NS',
                'Width %': 0.20,
                'Bias': 'Bullish',
                'Position': 'Above CPR',
                'Virgin CPR': 'Bullish Virgin'
            },
            {
                'Symbol': 'WIDE.NS',
                'Width %': 0.80,
                'Bias': 'Bearish',
                'Position': 'Below CPR',
                'Virgin CPR': 'None'
            },
            {
                'Symbol': 'MEDIUM.NS',
                'Width %': 0.50,
                'Bias': 'Neutral',
                'Position': 'Inside CPR',
                'Virgin CPR': 'None'
            }
        ])
    
    def test_filter_narrow(self):
        """Test filtering for narrow CPR"""
        filtered = self.engine.screen_dataframe(
            self.test_df,
            cpr_width_filter="Narrow"
        )
        
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]['Symbol'], 'NARROW.NS')
    
    def test_filter_wide(self):
        """Test filtering for wide CPR"""
        filtered = self.engine.screen_dataframe(
            self.test_df,
            cpr_width_filter="Wide"
        )
        
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]['Symbol'], 'WIDE.NS')
    
    def test_filter_bullish_bias(self):
        """Test filtering for bullish bias"""
        filtered = self.engine.screen_dataframe(
            self.test_df,
            bias_filter="Bullish"
        )
        
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]['Symbol'], 'NARROW.NS')
    
    def test_filter_bullish_virgin(self):
        """Test filtering for bullish Virgin CPR"""
        filtered = self.engine.screen_dataframe(
            self.test_df,
            virgin_cpr_filter="Bullish Virgin"
        )
        
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]['Symbol'], 'NARROW.NS')
    
    def test_combined_filters(self):
        """Test combined filters"""
        filtered = self.engine.screen_dataframe(
            self.test_df,
            cpr_width_filter="Any",
            position_filter="Above CPR",
            bias_filter="Bullish"
        )
        
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]['Symbol'], 'NARROW.NS')
    
    def test_no_matches(self):
        """Test filters with no matches"""
        filtered = self.engine.screen_dataframe(
            self.test_df,
            cpr_width_filter="Narrow",
            bias_filter="Bearish"
        )
        
        self.assertEqual(len(filtered), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)