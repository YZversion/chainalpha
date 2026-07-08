"""成本模型：从 config/costs.yaml 加载，禁止自行发明参数。

股票：佣金万 2.5 + 最低 5 元 + 卖出印花税 0.05% + 滑点 0.15%。
滑点按成交价不利方向调整（买入抬价、卖出压价），并单独记账。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "costs.yaml"


@dataclass(frozen=True)
class TradeCosts:
    fill_price: float
    notional: float
    commission: float
    stamp_tax: float
    slippage_cash: float

    @property
    def total_friction(self) -> float:
        return self.commission + self.stamp_tax + self.slippage_cash


@dataclass(frozen=True)
class CostModel:
    commission_rate: float
    commission_min: float
    stamp_tax_rate: float
    slippage_rate: float
    lot_size: int
    initial_account: float

    @classmethod
    def load_stock(cls, path: Path = CONFIG_PATH) -> CostModel:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        stock = data["stock"]
        return cls(
            commission_rate=float(stock["commission_rate"]),
            commission_min=float(stock["commission_min"]),
            stamp_tax_rate=float(stock["stamp_tax_rate"]),
            slippage_rate=float(stock["slippage_rate"]),
            lot_size=int(data["lot_size"]),
            initial_account=float(data["initial_account"]),
        )

    def commission(self, notional: float) -> float:
        return max(notional * self.commission_rate, self.commission_min)

    def buy_fill_price(self, price: float) -> float:
        return price * (1 + self.slippage_rate)

    def sell_fill_price(self, price: float) -> float:
        return price * (1 - self.slippage_rate)

    def buy_costs(self, price: float, shares: int) -> TradeCosts:
        fill = self.buy_fill_price(price)
        notional = fill * shares
        return TradeCosts(
            fill_price=fill,
            notional=notional,
            commission=self.commission(notional),
            stamp_tax=0.0,
            slippage_cash=(fill - price) * shares,
        )

    def sell_costs(self, price: float, shares: int) -> TradeCosts:
        fill = self.sell_fill_price(price)
        notional = fill * shares
        return TradeCosts(
            fill_price=fill,
            notional=notional,
            commission=self.commission(notional),
            stamp_tax=notional * self.stamp_tax_rate,
            slippage_cash=(price - fill) * shares,
        )

    def buy_cash_outflow(self, price: float, shares: int) -> float:
        costs = self.buy_costs(price, shares)
        return costs.notional + costs.commission

    def sell_cash_inflow(self, price: float, shares: int) -> float:
        costs = self.sell_costs(price, shares)
        return costs.notional - costs.commission - costs.stamp_tax
