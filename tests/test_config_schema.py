"""Config YAML schema validation tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load_yaml(name: str) -> Any:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _require_keys(data: dict[str, Any], keys: set[str], label: str) -> None:
    missing = keys - set(data.keys())
    assert not missing, f"{label} missing keys: {sorted(missing)}"


def _require_type(value: Any, expected: type | tuple[type, ...], field: str) -> None:
    assert isinstance(value, expected), f"{field}: expected {expected}, got {type(value).__name__}"


class TestCostsYaml:
    def test_loads_and_schema(self) -> None:
        data = _load_yaml("costs.yaml")
        _require_type(data, dict, "costs.yaml root")
        _require_keys(
            data,
            {
                "schema_version",
                "initial_account",
                "lot_size",
                "stock",
                "etf",
                "trading_rules",
            },
            "costs.yaml",
        )
        _require_type(data["schema_version"], int, "schema_version")
        _require_type(data["initial_account"], int, "initial_account")
        assert data["initial_account"] == 100_000
        _require_type(data["lot_size"], int, "lot_size")
        assert data["lot_size"] == 100

        for side in ("stock", "etf"):
            side_data = data[side]
            _require_type(side_data, dict, side)
            _require_keys(
                side_data,
                {"commission_rate", "commission_min", "stamp_tax_rate", "slippage_rate"},
                f"costs.{side}",
            )
            for key in ("commission_rate", "commission_min", "stamp_tax_rate", "slippage_rate"):
                _require_type(side_data[key], (int, float), f"costs.{side}.{key}")

        rules = data["trading_rules"]
        _require_type(rules, dict, "trading_rules")
        _require_keys(rules, {"t_plus", "limit_up_down_enabled"}, "trading_rules")
        _require_type(rules["t_plus"], int, "trading_rules.t_plus")
        _require_type(rules["limit_up_down_enabled"], bool, "trading_rules.limit_up_down_enabled")


class TestRiskYaml:
    def test_loads_and_schema(self) -> None:
        data = _load_yaml("risk.yaml")
        _require_type(data, dict, "risk.yaml root")
        _require_keys(
            data,
            {
                "schema_version",
                "initial_account",
                "position_limits",
                "max_stock_positions",
                "one_lot_amount_etf_only_threshold",
                "target_max_annual_turnover_pct",
            },
            "risk.yaml",
        )
        _require_type(data["initial_account"], int, "initial_account")
        assert data["initial_account"] == 100_000

        limits = data["position_limits"]
        _require_type(limits, dict, "position_limits")
        limit_keys = {
            "single_stock_max_pct",
            "single_etf_max_pct",
            "tech_sector_max_pct",
            "total_position_max_pct",
            "cash_min_pct",
        }
        _require_keys(limits, limit_keys, "position_limits")
        for key in limit_keys:
            _require_type(limits[key], (int, float), f"position_limits.{key}")

        _require_type(data["max_stock_positions"], int, "max_stock_positions")
        _require_type(
            data["one_lot_amount_etf_only_threshold"],
            int,
            "one_lot_amount_etf_only_threshold",
        )
        _require_type(
            data["target_max_annual_turnover_pct"],
            int,
            "target_max_annual_turnover_pct",
        )


class TestUniverseEtfYaml:
    def test_loads_and_schema_empty_allowed(self) -> None:
        data = _load_yaml("universe_etf.yaml")
        _require_type(data, dict, "universe_etf.yaml root")
        _require_keys(data, {"schema_version", "domains"}, "universe_etf.yaml")
        _require_type(data["schema_version"], int, "schema_version")
        _require_type(data["domains"], list, "domains")

        for i, domain in enumerate(data["domains"]):
            label = f"domains[{i}]"
            _require_type(domain, dict, label)
            _require_keys(domain, {"name", "etfs"}, label)
            _require_type(domain["name"], str, f"{label}.name")
            _require_type(domain["etfs"], list, f"{label}.etfs")

            for j, etf in enumerate(domain["etfs"]):
                etf_label = f"{label}.etfs[{j}]"
                _require_type(etf, dict, etf_label)
                _require_keys(
                    etf,
                    {"code", "tracking_index", "avg_daily_turnover", "management_fee"},
                    etf_label,
                )
                _require_type(etf["code"], str, f"{etf_label}.code")
                _require_type(etf["tracking_index"], str, f"{etf_label}.tracking_index")
                _require_type(
                    etf["avg_daily_turnover"],
                    (int, float),
                    f"{etf_label}.avg_daily_turnover",
                )
                _require_type(
                    etf["management_fee"],
                    (int, float),
                    f"{etf_label}.management_fee",
                )


class TestUniverseStocksYaml:
    def test_loads_and_schema_empty_allowed(self) -> None:
        data = _load_yaml("universe_stocks.yaml")
        _require_type(data, dict, "universe_stocks.yaml root")
        _require_keys(data, {"schema_version", "stocks"}, "universe_stocks.yaml")
        _require_type(data["schema_version"], int, "schema_version")
        _require_type(data["stocks"], list, "stocks")

        for i, stock in enumerate(data["stocks"]):
            label = f"stocks[{i}]"
            _require_type(stock, dict, label)
            _require_keys(
                stock,
                {"code", "name", "domain", "one_lot_amount", "etf_only"},
                label,
            )
            _require_type(stock["code"], str, f"{label}.code")
            _require_type(stock["name"], str, f"{label}.name")
            _require_type(stock["domain"], str, f"{label}.domain")
            _require_type(
                stock["one_lot_amount"],
                (int, float),
                f"{label}.one_lot_amount",
            )
            _require_type(stock["etf_only"], bool, f"{label}.etf_only")
