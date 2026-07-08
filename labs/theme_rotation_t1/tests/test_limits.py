"""涨跌停价推导单测（合成昨收，非行情伪造）。"""

import pytest
from ingestion.limits import board_limit_pct, derive_limit_prices


class TestLimitDerivation:
    def test_main_board_10pct(self):
        d = derive_limit_prices(10.0, "600519", is_st=False)
        assert d.limit_up_price == 11.0
        assert d.limit_down_price == 9.0
        assert d.limit_pct == 0.10

    def test_chi_next_20pct(self):
        assert board_limit_pct("300750") == 0.20
        d = derive_limit_prices(100.0, "300750")
        assert d.limit_up_price == 120.0
        assert d.limit_down_price == 80.0

    def test_star_20pct(self):
        assert board_limit_pct("688981") == 0.20

    def test_st_5pct_when_known(self):
        d = derive_limit_prices(10.0, "000001", is_st=True)
        assert d.limit_up_price == 10.5
        assert d.st_status == "known_true"

    def test_st_missing_does_not_assume(self):
        d = derive_limit_prices(10.0, "000001", is_st=None)
        assert d.st_status == "[MISSING]"
        assert d.limit_pct == 0.10

    def test_invalid_prev_close(self):
        with pytest.raises(ValueError):
            derive_limit_prices(0.0, "000001")
