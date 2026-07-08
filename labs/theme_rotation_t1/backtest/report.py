"""回测报告写入 reports/lab_theme_rotation_t1.md。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from backtest.loop import TRAIN_END, TRAIN_START, VAL_END, VAL_START, BacktestResult
from ingestion.daily_bars import IngestReport


def write_backtest_report(
    results: list[BacktestResult],
    *,
    ingest: IngestReport,
    universe_note: str,
    path: Path,
) -> None:
    title = results[0].title if results else "非完整可执行回测"
    lines = [
        f"# theme_rotation_t1 — {title}",
        "",
        "> 仅供学习研究，不构成投资建议。",
        "",
        f"报告日期：{date.today().isoformat()}",
        "",
        "## 1. 数据覆盖与 [MISSING] 字段",
        "",
        "- 数据源：AkShare `stock_zh_a_hist`（未复权日线）",
        f"- 标的范围：`{universe_note}`（请求 {ingest.symbols_requested}，"
        f"成功 {ingest.symbols_loaded}）",
        f"- 缓存目录：`{ingest.cache_dir or '[MISSING]'}`",
        f"- 接入行数：{ingest.rows_total}",
        "",
        "| 字段 | 状态 | 说明 |",
        "| --- | --- | --- |",
        f"| daily_ohlcv | {'OK' if ingest.symbols_loaded else '[MISSING]'} | 网络失败时无数据 |",
        "| intraday_breadth | [MISSING] | 无历史决策时点快照；买入门槛阻断 |",
        "| minute_bars | [MISSING] | 无历史分钟线 |",
        "| limit_prices | 推导 | 昨收+板块规则；ST 状态 [MISSING] |",
        "| free_float_market_cap | [MISSING] | 一进二 setup 无法完整验证 |",
        "| theme_id (as-of) | [MISSING] | 相关性保守计数 |",
        "| event_risk 全字段 | [MISSING] | 保守排除 |",
        "| tolerated_account_drawdown_pct | [MISSING] | rules.yaml 未冻结 |",
        "",
        "## 2. 样本切分",
        "",
        f"- 训练/规则冻结：{TRAIN_START} – {TRAIN_END}",
        f"- 验证：{VAL_START} – {VAL_END}",
        "- 最终 holdout：`[MISSING]`（未运行）",
        "- 主项目 OOS 2024–2026.06：**未触碰**",
        "",
        "## 3. 参数版本",
        "",
        "- `rules.yaml` / `strategy_spec.md`：未修改（draft_unvalidated）",
        "- 成本：`config/costs.yaml`（account=100000, lot=100, "
        "佣金万2.5/最低5元/印花税0.05%/滑点0.15%）",
        "",
        "## 4. 全系统绩效（降级口径）",
        "",
    ]

    for r in results:
        ret_pct = (r.final_equity / 100_000 - 1) * 100 if r.final_equity else 0.0
        lines.extend(
            [
                f"### {r.split}",
                "",
                f"- 交易日数：{r.trading_days}",
                f"- 期末权益：{r.final_equity:,.2f}（{ret_pct:+.2f}%）",
                f"- 成交笔数：{len(r.trades)}",
                f"- 涨跌停未成交事件：{r.limit_unfilled_events}",
                f"- 买入被盘中宽度阻断：{r.entries_blocked_breadth}",
                f"- 买入被仓位参数阻断：{r.entries_blocked_sizing}",
                f"- 买入被事件过滤阻断：{r.entries_blocked_event}",
                "",
            ]
        )

    lines.extend(
        [
            "## 5. setup 分项（信号扫描，非成交）",
            "",
        ]
    )
    for r in results:
        lines.append(f"### {r.split}")
        lines.append("")
        if not r.setup_signal_counts:
            lines.append("- 无触发（数据不足或样本为空）")
        else:
            for sid, cnt in sorted(r.setup_signal_counts.items()):
                miss = r.setup_missing_counts.get(sid, 0)
                lines.append(f"- `{sid}`：触发 {cnt} 次；缺失字段阻断 {miss} 次")
        lines.append("")

    lines.extend(
        [
            "## 6. 成本与敏感性",
            "",
            "- 本次无成交，摩擦成本占比 N/A",
            "- 完整可执行回测需分钟数据 + 盘中宽度 + 冻结仓位参数后方可评估",
            "",
            "## 7. 涨跌停未成交影响",
            "",
        ]
    )
    for r in results:
        lines.append(f"- {r.split}：{r.limit_unfilled_events} 次")

    lines.extend(
        [
            "",
            "## 8. 冷却期与停用",
            "",
            "- 无成交样本，滚动期望停用规则未触发",
            "",
            "## 9. 降级说明",
            "",
        ]
    )
    if results:
        for note in results[0].degraded_notes:
            lines.append(f"- {note}")

    if ingest.symbols_loaded == 0:
        ingest_msg = "失败（网络）。"
    else:
        ingest_msg = f"仅覆盖 {ingest.symbols_loaded} 只股票，不足以代表全市场。"
    lines.extend(
        [
            "",
            "## 10. Go/No-Go 结论",
            "",
            "**NO-GO**（不得进入实盘或模拟加仓）",
            "",
            "理由：",
            "",
            "1. 非完整可执行回测：缺分钟线、缺盘中上涨家数、缺历史 as-of 题材标签。",
            f"2. 本次 AkShare 日线接入{ingest_msg}",
            "3. `rules.yaml` 仓位参数 `tolerated_account_drawdown_pct` 仍为 [MISSING]。",
            "4. 未满足 backtest_protocol.md 完整可执行回测与净期望 > 0 等全部门槛。",
            "",
            "建议：",
            "",
            "- 稳定网络下复跑 `probe_akshare.py` 与日线接入；",
            "- 启动 `forward_collect/` 脚本积累分钟线、盘中宽度、概念成份快照；",
            "- 冻结缺失仓位参数后再做可执行回测。",
            "",
            "本报告仅供学习研究，不构成投资建议。",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")
