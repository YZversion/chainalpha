"""akshare_panel universe 发现与符号工具测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from chainalpha.ingest import akshare_panel as ap


class TestSymbolHelpers:
    def test_qlib_roundtrip(self) -> None:
        assert ap.qlib_to_raw("SH600519") == "600519"
        assert ap.qlib_to_raw("SZ000001") == "000001"
        assert ap.symbol_to_qlib("600519") == "SH600519"
        assert ap.symbol_to_qlib("000001") == "SZ000001"

    @patch("chainalpha.ingest.akshare_panel.UNIVERSE_PATH")
    def test_get_all_a_share_symbols_excludes_b_share(self, mock_path: MagicMock) -> None:
        mock_path.is_file.return_value = False
        fake_df = pd.DataFrame(
            {
                "code": ["000001", "600519", "900901", "200002", "300750"],
                "name": ["平安", "茅台", "B股1", "B股2", "宁德"],
            }
        )
        with patch("akshare.stock_info_a_code_name", return_value=fake_df):
            symbols = ap.get_all_a_share_symbols(refresh=True)
        assert "900901" not in symbols
        assert "200002" not in symbols
        assert "000001" in symbols
        assert "600519" in symbols
