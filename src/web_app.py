#!/usr/bin/env python3
"""仓位管理计算工具。"""

from __future__ import annotations

import json
import math
import html
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "assumptions.json"
CONFIG_EXAMPLE_PATH = BASE_DIR / "config" / "assumptions.example.json"
RULES_CONFIG_PATH = BASE_DIR / "config" / "position_management_rules.json"
STOCK_POSITIONS_PATH = BASE_DIR / "data" / "stock_positions.csv"
STOCK_POSITIONS_EXAMPLE_PATH = BASE_DIR / "data" / "stock_positions.example.csv"
PLANS_PATH = BASE_DIR / "data" / "trade_plans.csv"
JOURNAL_PATH = BASE_DIR / "data" / "trade_journal.csv"
MARKET_STATUS_PATH = BASE_DIR / "data" / "market_data_status.json"


DEFAULT_POSITIONS = [
    ["510300", "沪深300ETF", "ETF", "宽基指数", "old", 1000, 4.0, 4.05, 3.7, "持有"],
    ["512880", "证券ETF", "ETF", "券商金融", "old", 2000, 1.0, 1.02, 0.9, "持有"],
]
POSITION_COLUMNS = [
    "symbol",
    "name",
    "asset_type",
    "sector",
    "strategy",
    "quantity",
    "cost_price",
    "current_price",
    "risk_price",
    "status",
]


st.set_page_config(page_title="Trading OS · 长期资金风险控制台", layout="wide")


def css() -> None:
    st.markdown(
        """
        <style>
        :root { --ink:#17211b; --muted:#66736a; --line:#dfe6e1; --paper:#fbfcfa; --green:#166534; }
        .stApp { background: #f4f7f4; color: var(--ink); }
        .block-container { padding-top: 1.35rem; padding-bottom: 3rem; max-width: 1360px; }
        h1, h2, h3 { color: var(--ink); letter-spacing: -0.025em; }
        h1 { font-size: 2rem !important; }
        [data-testid="stCaptionContainer"] { color: var(--muted); }
        div[data-testid="stMetric"] {
            border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px;
            background: #ffffff; color: var(--ink); box-shadow: 0 1px 2px rgba(20,40,26,.03);
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] [data-testid="stMetricValue"],
        div[data-testid="stMetric"] [data-testid="stMetricDelta"] { color: #111827; }
        div[data-testid="stMetric"] label p { color: #4b5563; }
        .status-safe, .status-warn, .status-danger {
            border-radius: 12px; padding: 14px 16px; margin: 0.6rem 0 1rem 0;
        }
        .status-safe { border-left: 5px solid #0f9f6e; background: #ecfdf5; color: #064e3b; }
        .status-warn { border-left: 5px solid #d97706; background: #fffbeb; color: #78350f; }
        .status-danger { border-left: 5px solid #dc2626; background: #fef2f2; color: #7f1d1d; }
        section[data-testid="stSidebar"] { background: #17211b; }
        section[data-testid="stSidebar"] * { color: #eef4ef; }
        section[data-testid="stSidebar"] [data-baseweb="radio"] label { padding: 6px 0; }
        section[data-testid="stSidebar"] input { color: #17211b; }
        [data-testid="stMain"] [data-testid="stWidgetLabel"],
        [data-testid="stMain"] [data-testid="stWidgetLabel"] *,
        [data-testid="stMain"] [data-baseweb="radio"] label,
        [data-testid="stMain"] [data-baseweb="radio"] label *,
        [data-testid="stMain"] [data-testid="stCheckbox"] label,
        [data-testid="stMain"] [data-testid="stCheckbox"] label * {
            color: #46564c !important;
            opacity: 1 !important;
            font-weight: 620;
        }
        [data-testid="stMain"] [data-testid="stSlider"] [data-testid="stWidgetLabel"] * {
            color: #46564c !important;
        }
        .hero { background:linear-gradient(135deg,#13251a,#244b32); color:white; padding:26px 28px;
            border-radius:18px; margin:0 0 18px; box-shadow:0 12px 35px rgba(20,45,29,.12); }
        .hero h2 { color:white; margin:0 0 6px; font-size:1.55rem; }
        .hero p { color:#cfe1d3; margin:0; }
        .eyebrow { text-transform:uppercase; letter-spacing:.12em; font-size:.72rem; font-weight:700; color:#8bbd98; margin-bottom:8px; }
        .section-label { color:#66736a; font-size:.78rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; margin:22px 0 8px; }
        .action-card { background:#fff; border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin:8px 0; }
        .action-card strong { color:var(--ink); }
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] { border-radius:14px; overflow:hidden; }
        .stButton > button, .stFormSubmitButton > button { border-radius:10px; font-weight:650; }
        .os-shell { max-width:1120px; margin:0 auto; }
        .os-head { display:flex; align-items:flex-end; justify-content:space-between; border-bottom:1px solid #cfd8d1;
            padding:10px 2px 20px; margin-bottom:22px; }
        .os-brand { font-size:2.15rem; font-weight:760; letter-spacing:-.055em; color:#132119; }
        .os-date { color:#718077; font-size:.86rem; }
        .os-grid { display:grid; grid-template-columns:1.08fr .92fr; gap:18px; margin-bottom:18px; }
        .os-card { background:#fff; border:1px solid #dce4de; border-radius:16px; padding:22px 24px;
            box-shadow:0 6px 24px rgba(30,50,36,.045); }
        .os-card-wide { grid-column:1 / -1; }
        .os-title { font-size:.78rem; font-weight:740; letter-spacing:.1em; color:#718077; text-transform:uppercase;
            padding-bottom:14px; margin-bottom:16px; border-bottom:1px solid #edf1ee; }
        .os-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
        .os-kicker { color:#7a887f; font-size:.78rem; margin-bottom:6px; }
        .os-value { font-size:1.55rem; font-weight:730; color:#142219; letter-spacing:-.035em; }
        .os-value.accent { color:#166534; }
        .plan-row,.rule-row { display:flex; align-items:center; justify-content:space-between; gap:18px;
            padding:11px 0; border-bottom:1px solid #f0f3f1; }
        .plan-row:last-child,.rule-row:last-child { border-bottom:0; }
        .plan-name { font-weight:670; color:#1c2921; }
        .plan-meta { color:#849087; font-size:.82rem; margin-left:8px; }
        .pill { border-radius:999px; padding:5px 10px; font-size:.76rem; font-weight:670; background:#eef3ef; color:#4d5f52; white-space:nowrap; }
        .pill.ready { background:#e8f5eb; color:#166534; }
        .pill.wait { background:#fff5dd; color:#8a5a0a; }
        .check { color:#168044; font-weight:780; margin-right:9px; }
        .cross { color:#c2413b; font-weight:780; margin-right:9px; }
        .ai-note { border-left:3px solid #1d6d3b; padding:2px 0 2px 16px; color:#33443a; line-height:1.75; }
        .empty-note { color:#849087; padding:8px 0; }
        @media (max-width:800px) { .os-grid { grid-template-columns:1fr; } .os-card-wide { grid-column:auto; }
            .os-stats { grid-template-columns:1fr; } .os-date { display:none; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def money(value: float) -> str:
    return f"{value:,.0f}"


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def floor_lot(value: float, lot_size: int = 1) -> int:
    if value <= 0:
        return 0
    return int(math.floor(value / lot_size) * lot_size)


def status_box(level: str, text: str) -> None:
    klass = {"safe": "status-safe", "warn": "status-warn", "danger": "status-danger"}[level]
    st.markdown(f'<div class="{klass}">{text}</div>', unsafe_allow_html=True)


def load_assumptions() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(CONFIG_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_rules() -> dict:
    return json.loads(RULES_CONFIG_PATH.read_text(encoding="utf-8"))


def load_positions() -> pd.DataFrame:
    if STOCK_POSITIONS_PATH.exists():
        df = pd.read_csv(STOCK_POSITIONS_PATH, dtype={"symbol": str})
    elif STOCK_POSITIONS_EXAMPLE_PATH.exists():
        df = pd.read_csv(STOCK_POSITIONS_EXAMPLE_PATH, dtype={"symbol": str})
    else:
        df = pd.DataFrame(DEFAULT_POSITIONS, columns=POSITION_COLUMNS)
    return normalize_positions(df)


def normalize_positions(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in POSITION_COLUMNS:
        if col not in result.columns:
            result[col] = "" if col not in ["quantity", "cost_price", "current_price", "risk_price"] else 0
    result = result[POSITION_COLUMNS]
    result["symbol"] = result["symbol"].astype(str).str.strip()
    result = result[result["symbol"].str.fullmatch(r"\d{6}", na=False)].copy()
    result["symbol"] = result["symbol"].str.zfill(6)
    result["quantity"] = pd.to_numeric(result["quantity"], errors="coerce").fillna(0).astype(int)
    for col in ["cost_price", "current_price", "risk_price"]:
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0.0).astype(float)
    for col in ["name", "asset_type", "sector", "strategy", "status"]:
        result[col] = result[col].fillna("").astype(str)
    result["strategy"] = result["strategy"].replace({"trend": "old", "": "old"})
    return result


def save_positions(df: pd.DataFrame) -> None:
    STOCK_POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalize_positions(df).to_csv(STOCK_POSITIONS_PATH, index=False)


def cash_balance(raw: dict | None = None, positions: pd.DataFrame | None = None) -> float:
    raw = raw or load_assumptions()
    if "cash_balance" in raw:
        return float(raw["cash_balance"])
    positions = load_positions() if positions is None else positions
    market_value = float((positions["quantity"] * positions["current_price"]).sum())
    return float(raw["account_equity"]) - market_value


def refresh_market_prices() -> dict:
    """Refresh A-share and ETF prices; keep existing values when a source fails."""
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("行情组件尚未安装，请重新安装 requirements.txt。") from exc

    positions = load_positions()
    quotes: dict[str, float] = {}
    errors = []
    if (positions["asset_type"] == "股票").any():
        try:
            stocks = ak.stock_zh_a_spot()
            for _, row in stocks[["代码", "最新价"]].iterrows():
                price = pd.to_numeric(row["最新价"], errors="coerce")
                if pd.notna(price) and float(price) > 0:
                    quotes[str(row["代码"])[-6:]] = float(price)
        except Exception as exc:
            errors.append(f"股票行情失败：{exc}")
    if (positions["asset_type"] == "ETF").any():
        try:
            funds = ak.fund_etf_spot_em()
            for _, row in funds[["代码", "最新价"]].iterrows():
                price = pd.to_numeric(row["最新价"], errors="coerce")
                if pd.notna(price) and float(price) > 0:
                    quotes[str(row["代码"]).zfill(6)] = float(price)
        except Exception as exc:
            errors.append(f"ETF 行情失败：{exc}")

    updated = 0
    for index, row in positions.iterrows():
        price = quotes.get(row["symbol"])
        if price is not None:
            positions.at[index, "current_price"] = price
            updated += 1
    if updated:
        save_positions(positions)
    status = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "AKShare 聚合公开行情",
        "updated_count": updated,
        "errors": errors,
    }
    MARKET_STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def quote_refresh_control(key: str) -> None:
    c1, c2 = st.columns([1, 4])
    with c1:
        refresh = st.button("刷新 A股 / ETF 行情", key=key, type="primary", width="stretch")
    with c2:
        if MARKET_STATUS_PATH.exists():
            status = json.loads(MARKET_STATUS_PATH.read_text(encoding="utf-8"))
            st.caption(f"最近更新：{status.get('updated_at', '-')} · {status.get('source', '-')} · 更新 {status.get('updated_count', 0)} 个品种")
        else:
            st.caption("尚未获取行情。点击后更新持仓中的当前价；失败时保留原价格。")
    if refresh:
        try:
            with st.spinner("正在获取最新行情…"):
                status = refresh_market_prices()
            if status["updated_count"]:
                st.success(f"已更新 {status['updated_count']} 个持仓价格。")
                st.rerun()
            else:
                details = "；".join(status["errors"]) or "没有匹配到持仓代码。"
                st.warning(f"本次没有更新价格：{details}")
        except Exception as exc:
            st.error(f"行情更新失败，原价格未改变。原因：{exc}")


def sidebar_defaults() -> dict:
    raw = load_assumptions()
    st.sidebar.markdown("## 守仓")
    st.sidebar.caption("长期资金风险控制台")
    st.sidebar.markdown("---")
    return {
        "account_equity": float(raw["account_equity"]),
        "risk_ratio": float(raw["trend_risk_per_trade_ratio"]),
        "breakeven_r": float(raw["breakeven_trigger_r_multiple"]),
        "normal_limit": float(raw["normal_max_exposure_ratio"]),
        "holiday_limit": float(raw["holiday_max_exposure_ratio"]),
        "cash_balance": cash_balance(raw),
    }


def save_assumptions(values: dict) -> None:
    raw = load_assumptions()
    raw.update(values)
    CONFIG_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_table(path: Path, columns: list[str]) -> pd.DataFrame:
    if path.exists():
        frame = pd.read_csv(path, dtype=str).fillna("")
    else:
        frame = pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame[columns]


def save_table(path: Path, frame: pd.DataFrame, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame[columns].fillna("").to_csv(path, index=False)


def portfolio_snapshot(positions: pd.DataFrame, defaults: dict) -> dict:
    enriched = enrich_positions(positions, defaults["account_equity"])
    market_value = float(enriched["市值"].sum())
    cost_value = float(enriched["成本"].sum())
    pnl = float(enriched["浮盈亏"].sum())
    open_risk = float(enriched["单仓风险"].sum())
    cash = float(defaults.get("cash_balance", cash_balance(positions=positions)))
    actions = []
    for _, row in enriched.iterrows():
        level, action, reason = holding_action(row, defaults)
        if level != "safe":
            actions.append({"level": level, "symbol": row["symbol"], "name": row["name"], "action": action, "reason": reason})
    return {
        "enriched": enriched,
        "market_value": market_value,
        "cost_value": cost_value,
        "pnl": pnl,
        "open_risk": open_risk,
        "cash": cash,
        "total_assets": cash + market_value,
        "exposure": market_value / defaults["account_equity"] if defaults["account_equity"] else 0,
        "actions": actions,
    }


def overview(defaults: dict, positions: pd.DataFrame) -> None:
    snap = portfolio_snapshot(positions, defaults)
    exposure_limit = defaults["normal_limit"]
    capacity = defaults["account_equity"] * exposure_limit - snap["market_value"]
    danger_count = sum(item["level"] == "danger" for item in snap["actions"])
    if danger_count:
        headline, subline = f"今天有 {danger_count} 项风险需要处理", "先处理触发风控的仓位，再考虑新增交易。"
    elif snap["actions"]:
        headline, subline = f"今天有 {len(snap['actions'])} 项需要确认", "账户没有失控，但有仓位需要补充信息或执行动作。"
    else:
        headline, subline = "账户处于规则范围内", "当前没有触发止损、推保本或仓位上限提醒。"
    st.markdown(
        f'<div class="hero"><div class="eyebrow">今日风险结论</div><h2>{headline}</h2><p>{subline}</p></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("账户权益", f"¥{money(defaults['account_equity'])}")
    c2.metric("当前仓位", percent(snap["exposure"]), f"上限 {percent(exposure_limit)}")
    c3.metric("持仓浮盈亏", f"¥{money(snap['pnl'])}", percent(snap["pnl"] / snap["cost_value"]) if snap["cost_value"] else "0.0%")
    c4.metric("剩余建仓额度", f"¥{money(max(capacity, 0))}", "已超限" if capacity < 0 else "按总仓位上限")

    st.markdown('<div class="section-label">今日动作</div>', unsafe_allow_html=True)
    if snap["actions"]:
        for item in snap["actions"]:
            icon = "🔴" if item["level"] == "danger" else "🟠"
            st.markdown(
                f'<div class="action-card">{icon} <strong>{item["symbol"]} {item["name"]} · {item["action"]}</strong><br><span style="color:#66736a">{item["reason"]}</span></div>',
                unsafe_allow_html=True,
            )
    else:
        status_box("safe", "暂无待处理动作。保持当前仓位纪律，新增交易继续按止损位反推数量。")

    st.markdown('<div class="section-label">持仓结构</div>', unsafe_allow_html=True)
    summary = snap["enriched"][["symbol", "name", "sector", "市值", "仓位占比", "浮盈亏"]].copy()
    summary.columns = ["代码", "名称", "行业/主题", "市值", "仓位占比", "浮盈亏"]
    st.dataframe(summary, width="stretch", hide_index=True, column_config={
        "市值": st.column_config.NumberColumn(format="¥ %.0f"),
        "仓位占比": st.column_config.NumberColumn(format="%.1%"),
        "浮盈亏": st.column_config.NumberColumn(format="¥ %.0f"),
    })


def trade_planner(defaults: dict, positions: pd.DataFrame) -> None:
    market = st.radio("选择市场", ["股票 / ETF", "期货"], horizontal=True)
    if market == "股票 / ETF":
        tabs = st.tabs(["新仓计划", "老仓容量"])
        with tabs[0]: stock_new_calculator(defaults)
        with tabs[1]: stock_old_calculator(defaults, positions)
    else:
        tabs = st.tabs(["新仓计划", "老仓容量", "网格压力测试"])
        with tabs[0]: futures_new_calculator(defaults)
        with tabs[1]: futures_old_calculator(defaults)
        with tabs[2]: futures_grid_calculator()


def rules_center(rules: dict) -> None:
    st.title("规则中心")
    st.caption("所有计算和提醒都应能追溯到这里。规则变化后，先更新规则，再更新计算逻辑。")
    status_box("warn", "当前版本只执行仓位与风险规则，不预测市场方向，也不替代交易决策。")
    rules_detail(rules)


def stock_old_calculator(defaults: dict, positions: pd.DataFrame) -> None:
    st.subheader("股票老仓计算器")
    ratios = {"大盘": 0.40, "中盘": 0.30, "小盘": 0.25, "微盘": 0.10}
    stock_positions = positions[
        (positions["quantity"] > 0)
        & (positions["asset_type"].isin(["股票", "ETF"]))
    ].copy()
    options = ["手动输入"] + [
        f"{row.symbol} {row.name}" for row in stock_positions.itertuples(index=False)
    ]
    selected = st.selectbox("从当前持仓同步", options)
    selected_row = None
    if selected != "手动输入":
        selected_symbol = selected.split(" ", 1)[0]
        selected_row = stock_positions[stock_positions["symbol"] == selected_symbol].iloc[0]
        st.caption("已从持仓检查数据同步当前价格、买入价格和持仓数量。")

    default_current_price = float(selected_row["current_price"]) if selected_row is not None else 10.0
    default_buy_price = float(selected_row["cost_price"]) if selected_row is not None else 10.0
    default_quantity = int(selected_row["quantity"]) if selected_row is not None else 0

    with st.form("stock_old_form"):
        c1, c2, c3 = st.columns(3)
        total = c1.number_input("总资金", min_value=1_000.0, value=float(defaults["account_equity"]), step=10_000.0, format="%.0f")
        cap_type = c2.selectbox("股票市值类型", list(ratios.keys()))
        current_price = c3.number_input("当前价格", min_value=0.0, value=default_current_price, step=0.01, format="%.3f")
        c4, c5 = st.columns(2)
        buy_price = c4.number_input("买入价格", min_value=0.0, value=default_buy_price, step=0.01, format="%.3f")
        quantity = c5.number_input("当前持仓数量", min_value=0, value=default_quantity, step=100)
        submitted = st.form_submit_button("计算股票老仓")
    if not submitted:
        return
    ratio = ratios[cap_type]
    max_amount = total * ratio
    current_amount = current_price * quantity
    remaining = max_amount - current_amount
    is_over = current_amount > max_amount
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("最大仓位比例", percent(ratio))
    c2.metric("最大可投入金额", money(max_amount))
    c3.metric("当前已占用金额", money(current_amount))
    c4.metric("剩余可加仓金额", money(max(remaining, 0)))
    pnl = (current_price - buy_price) * quantity
    st.metric("当前浮盈亏", money(pnl), percent(pnl / (buy_price * quantity)) if buy_price * quantity > 0 else "0.0%")
    if is_over:
        status_box("danger", f"超仓：当前占用 {percent(current_amount / total)}，超过 {cap_type} 老仓上限 {percent(ratio)}。")
    elif remaining <= max_amount * 0.1:
        status_box("warn", "接近仓位上限：可以继续持有，但新增买入空间已经不多。")
    else:
        status_box("safe", "安全：当前老仓未超过该市值类型对应的仓位上限。")


def stock_new_calculator(defaults: dict) -> None:
    st.subheader("股票新仓计算器")
    with st.form("stock_new_form"):
        c1, c2, c3 = st.columns(3)
        total = c1.number_input("总资金", min_value=1_000.0, value=float(defaults["account_equity"]), step=10_000.0, format="%.0f", key="stock_new_total")
        entry = c2.number_input("入场价", min_value=0.0, value=10.0, step=0.01, format="%.3f")
        stop = c3.number_input("止损价", min_value=0.0, value=9.0, step=0.01, format="%.3f")
        c4, c5, c6 = st.columns(3)
        share_price = c4.number_input("单股价格", min_value=0.0, value=10.0, step=0.01, format="%.3f")
        risk_ratio = c5.number_input("单笔最大风险比例", min_value=0.001, max_value=0.10, value=float(defaults["risk_ratio"]), step=0.001, format="%.3f")
        near_threshold = c6.number_input("太近阈值", min_value=0.001, max_value=0.20, value=0.03, step=0.005, format="%.3f")
        far_threshold = st.number_input("太远阈值", min_value=0.05, max_value=0.80, value=0.20, step=0.01, format="%.2f")
        submitted = st.form_submit_button("计算股票新仓")
    if not submitted:
        return
    per_share_risk = entry - stop
    max_loss = total * risk_ratio
    qty = floor_lot(max_loss / per_share_risk, 100) if per_share_risk > 0 else 0
    buy_amount = qty * share_price
    risk_distance = per_share_risk / entry if entry > 0 else 0
    target_2r = entry + 2 * per_share_risk
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("单股风险", f"{per_share_risk:.3f}")
    c2.metric("最大可亏金额", money(max_loss))
    c3.metric("建议买入数量", f"{qty:,} 股")
    c4.metric("对应买入金额", money(buy_amount))
    c5, c6 = st.columns(2)
    c5.metric("盈利达到 2R 价格", f"{target_2r:.3f}" if per_share_risk > 0 else "-")
    c6.metric("保本止损价", f"{entry:.3f}")
    if per_share_risk <= 0:
        status_box("danger", "超限：止损价必须低于入场价。")
    elif risk_distance < near_threshold:
        status_box("warn", f"警戒：止损距离 {percent(risk_distance)}，低于你设置的太近阈值 {percent(near_threshold)}。")
    elif risk_distance > far_threshold:
        status_box("warn", f"警戒：止损距离 {percent(risk_distance)}，高于你设置的太远阈值 {percent(far_threshold)}，建议缩小买入数量或重新设计位置。")
    else:
        status_box("safe", "安全：止损距离在你设置的区间内，买入数量按 1% 风险反推。")


def futures_old_calculator(defaults: dict) -> None:
    st.subheader("期货老仓计算器")
    with st.form("futures_old_form"):
        c1, c2, c3 = st.columns(3)
        total = c1.number_input("总资金", min_value=1_000.0, value=float(defaults["account_equity"]), step=10_000.0, format="%.0f", key="futures_old_total")
        futures_ratio = c2.number_input("期货账户资金比例", min_value=0.01, max_value=1.0, value=0.30, step=0.01, format="%.2f")
        current_price = c3.number_input("当前品种价格", min_value=0.0, value=10000.0, step=10.0, format="%.2f")
        c4, c5, c6 = st.columns(3)
        multiplier = c4.number_input("合约乘数", min_value=0.0, value=10.0, step=1.0, format="%.2f")
        margin = c5.number_input("保证金/手", min_value=0.0, value=10000.0, step=100.0, format="%.0f")
        extreme_price = c6.number_input("极端风险价格", min_value=0.0, value=8000.0, step=10.0, format="%.2f")
        c7, c8, c9 = st.columns(3)
        current_lots = c7.number_input("当前持仓手数", min_value=0, value=0, step=1)
        is_holiday = c8.checkbox("是否节假日前")
        is_long_holiday = c9.checkbox("是否长假 8 天以上")
        submitted = st.form_submit_button("计算期货老仓")
    if not submitted:
        return
    futures_funds = total * futures_ratio
    per_lot_extreme = abs(current_price - extreme_price) * multiplier + margin
    full_lots = floor_lot(futures_funds / per_lot_extreme) if per_lot_extreme > 0 else 0
    first_lots = floor_lot(full_lots * 0.5)
    holiday_lots = floor_lot(full_lots * 0.5)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("期货账户可用资金", money(futures_funds))
    c2.metric("每手极端占用", money(per_lot_extreme))
    c3.metric("去杠杆满仓手数", f"{full_lots:,} 手")
    c4.metric("首次建议开仓手数", f"{first_lots:,} 手")
    c5, c6 = st.columns(2)
    c5.metric("节假日前建议手数", f"{holiday_lots:,} 手")
    c6.metric("当前持仓手数", f"{current_lots:,} 手")
    if is_long_holiday and current_lots > 0:
        status_box("danger", "超限：8 天以上长假最好不留仓，建议清仓或降到 0。")
    elif is_holiday and current_lots > holiday_lots:
        status_box("danger", f"超限：节假日前建议降到 {holiday_lots} 手以内。")
    elif current_lots > full_lots:
        status_box("danger", "超限：当前持仓超过去杠杆满仓手数。")
    elif current_lots > first_lots:
        status_box("warn", "警戒：当前持仓超过首次建议开仓手数，后续加仓空间变少。")
    else:
        status_box("safe", "安全：当前持仓没有超过老仓计算边界。")


def futures_new_calculator(defaults: dict) -> None:
    st.subheader("期货新仓计算器")
    with st.form("futures_new_form"):
        c1, c2, c3 = st.columns(3)
        total = c1.number_input("总资金", min_value=1_000.0, value=float(defaults["account_equity"]), step=10_000.0, format="%.0f", key="futures_new_total")
        entry = c2.number_input("入场价", min_value=0.0, value=10000.0, step=10.0, format="%.2f", key="futures_new_entry")
        stop = c3.number_input("止损价", min_value=0.0, value=9800.0, step=10.0, format="%.2f", key="futures_new_stop")
        c4, c5, c6 = st.columns(3)
        multiplier = c4.number_input("合约乘数", min_value=0.0, value=10.0, step=1.0, format="%.2f", key="futures_new_multiplier")
        risk_ratio = c5.number_input("单笔最大风险比例", min_value=0.001, max_value=0.10, value=float(defaults["risk_ratio"]), step=0.001, format="%.3f", key="futures_new_risk")
        stopped_count = c6.number_input("连续被止损新仓数量", min_value=0, value=0, step=1)
        submitted = st.form_submit_button("计算期货新仓")
    if not submitted:
        return
    per_lot_risk = abs(entry - stop) * multiplier
    max_loss = total * risk_ratio
    lots = floor_lot(max_loss / per_lot_risk) if per_lot_risk > 0 else 0
    direction = 1 if entry >= stop else -1
    target_2r = entry + direction * 2 * abs(entry - stop)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("每手风险", money(per_lot_risk))
    c2.metric("最大可亏金额", money(max_loss))
    c3.metric("建议开仓手数", f"{lots:,} 手")
    c4.metric("盈利达到 2R 价格", f"{target_2r:.2f}" if per_lot_risk > 0 else "-")
    st.metric("保本止损价", f"{entry:.2f}")
    if per_lot_risk <= 0:
        status_box("danger", "超限：入场价和止损价不能相同。")
    elif stopped_count >= 2:
        status_box("danger", "超限：后续新仓连续 2 个被打掉，应暂停继续加仓或考虑退出。")
    elif lots <= 0:
        status_box("warn", "警戒：按 1% 风险反推不足 1 手，需要放弃或重新设计止损。")
    else:
        status_box("safe", "安全：新仓手数已按单笔最大风险反推。")


def futures_grid_calculator() -> None:
    st.subheader("期货网格仓计算器")
    with st.form("futures_grid_form"):
        c1, c2, c3 = st.columns(3)
        grid_funds = c1.number_input("分配给网格的资金", min_value=0.0, value=50000.0, step=5000.0, format="%.0f")
        entry = c2.number_input("入场价", min_value=0.0, value=10000.0, step=10.0, format="%.2f", key="grid_entry")
        pressure = c3.number_input("压力测试价格", min_value=0.0, value=8000.0, step=10.0, format="%.2f")
        c4, c5, c6 = st.columns(3)
        multiplier = c4.number_input("合约乘数", min_value=0.0, value=10.0, step=1.0, format="%.2f", key="grid_multiplier")
        margin = c5.number_input("保证金/手", min_value=0.0, value=10000.0, step=100.0, format="%.0f", key="grid_margin")
        grid_step = c6.number_input("网格间距", min_value=0.0, value=200.0, step=10.0, format="%.2f")
        lots_per_grid = st.number_input("每格加仓手数", min_value=1, value=1, step=1)
        submitted = st.form_submit_button("计算期货网格")
    if not submitted:
        return
    per_lot_pressure = abs(entry - pressure) * multiplier + margin
    max_lots = floor_lot(grid_funds / per_lot_pressure) if per_lot_pressure > 0 else 0
    grid_count = floor_lot(abs(entry - pressure) / grid_step) if grid_step > 0 else 0
    planned_lots = grid_count * lots_per_grid
    needed_funds = planned_lots * per_lot_pressure
    enough = grid_funds >= needed_funds
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("每手压力测试资金占用", money(per_lot_pressure))
    c2.metric("最多可承受手数", f"{max_lots:,} 手")
    c3.metric("压力区间网格数", f"{grid_count:,} 格")
    c4.metric("计划需要手数", f"{planned_lots:,} 手")
    st.metric("完整网格所需资金", money(needed_funds))
    if not enough:
        status_box("danger", "超限：分配资金不足以覆盖完整网格压力测试。")
    elif planned_lots > max_lots * 0.8:
        status_box("warn", "警戒：完整网格接近资金承受上限。")
    else:
        status_box("safe", "安全：当前资金可以覆盖完整网格压力测试。")
    st.info("底部区间：只买入；中间区间：买入加卖出；上方区间：逐步卖出或停止加仓。")


def positions_editor(df: pd.DataFrame) -> pd.DataFrame:
    edited = st.data_editor(
        normalize_positions(df),
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": "代码",
            "name": "名称",
            "asset_type": st.column_config.SelectboxColumn("类型", options=["股票", "ETF", "现金观察"]),
            "sector": "行业/主题",
            "strategy": st.column_config.SelectboxColumn("仓位类型", options=["old", "new", "grid"]),
            "quantity": st.column_config.NumberColumn("数量", min_value=0, step=100),
            "cost_price": st.column_config.NumberColumn("成本价", min_value=0.0, format="%.3f"),
            "current_price": st.column_config.NumberColumn("现价", min_value=0.0, format="%.3f"),
            "risk_price": st.column_config.NumberColumn("风控价", min_value=0.0, format="%.3f"),
            "status": st.column_config.SelectboxColumn("状态", options=["持有", "观察", "减仓", "已清仓"]),
        },
    )
    return normalize_positions(edited)


def position_maintenance(raw: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">维护持仓</div>', unsafe_allow_html=True)
    mode = st.radio("操作", ["修改现有持仓", "新增持仓"], horizontal=True, key="position_mode")
    selected_row = None
    selected_symbol = "new"
    if mode == "修改现有持仓":
        if raw.empty:
            st.info("当前没有持仓，请切换到“新增持仓”。")
            return
        labels = {f"{row.symbol} · {row.name}": row.symbol for row in raw.itertuples(index=False)}
        selected_label = st.selectbox("选择持仓", list(labels.keys()), key="position_selector")
        selected_symbol = labels[selected_label]
        selected_row = raw[raw["symbol"] == selected_symbol].iloc[0]

    defaults = {
        "symbol": str(selected_row["symbol"]) if selected_row is not None else "",
        "name": str(selected_row["name"]) if selected_row is not None else "",
        "asset_type": str(selected_row["asset_type"]) if selected_row is not None else "股票",
        "sector": str(selected_row["sector"]) if selected_row is not None else "",
        "strategy": str(selected_row["strategy"]) if selected_row is not None else "old",
        "quantity": int(selected_row["quantity"]) if selected_row is not None else 0,
        "cost_price": float(selected_row["cost_price"]) if selected_row is not None else 0.0,
        "current_price": float(selected_row["current_price"]) if selected_row is not None else 0.0,
        "risk_price": float(selected_row["risk_price"]) if selected_row is not None else 0.0,
        "status": str(selected_row["status"]) if selected_row is not None else "持有",
    }
    with st.form(f"position_form_{mode}_{selected_symbol}"):
        c1, c2, c3, c4 = st.columns(4)
        symbol = c1.text_input("代码（6 位）", value=defaults["symbol"], disabled=selected_row is not None)
        name = c2.text_input("名称", value=defaults["name"])
        asset_type = c3.selectbox("类型", ["股票", "ETF", "现金观察"], index=["股票", "ETF", "现金观察"].index(defaults["asset_type"]) if defaults["asset_type"] in ["股票", "ETF", "现金观察"] else 0)
        sector = c4.text_input("行业 / 主题", value=defaults["sector"])
        c5, c6, c7, c8 = st.columns(4)
        strategy_options = ["old", "new", "grid"]
        strategy = c5.selectbox("仓位类型", strategy_options, index=strategy_options.index(defaults["strategy"]) if defaults["strategy"] in strategy_options else 0)
        quantity = c6.number_input("持仓数量", min_value=0, value=defaults["quantity"], step=100)
        cost_price = c7.number_input("成本价", min_value=0.0, value=defaults["cost_price"], step=.01, format="%.3f")
        current_price = c8.number_input("当前价", min_value=0.0, value=defaults["current_price"], step=.01, format="%.3f")
        c9, c10, c11 = st.columns(3)
        risk_price = c9.number_input("风控价", min_value=0.0, value=defaults["risk_price"], step=.01, format="%.3f")
        status_options = ["持有", "观察", "减仓", "已清仓"]
        status = c10.selectbox("状态", status_options, index=status_options.index(defaults["status"]) if defaults["status"] in status_options else 0)
        transaction_price = c11.number_input(
            "本次成交价",
            min_value=0.0,
            value=defaults["current_price"] if defaults["current_price"] > 0 else defaults["cost_price"],
            step=.01,
            format="%.3f",
            help="数量变化时，用这个价格同步增加或减少现金。",
        )
        sync_cash = st.checkbox("数量变化时同步调整现金余额", value=True)
        submitted = st.form_submit_button("保存这笔持仓", type="primary")
    if submitted:
        clean_symbol = str(symbol).strip().zfill(6)
        if not clean_symbol.isdigit() or len(clean_symbol) != 6:
            st.error("代码必须是 6 位数字。")
            return
        if not name.strip():
            st.error("请填写名称。")
            return
        latest = load_positions()
        saved_quantity = 0 if status == "已清仓" else quantity
        old_quantity = int(selected_row["quantity"]) if selected_row is not None else 0
        quantity_change = saved_quantity - old_quantity
        if sync_cash and quantity_change != 0:
            if transaction_price <= 0:
                st.error("数量发生变化时，请填写本次成交价，系统才能同步现金。")
                return
            raw_assumptions = load_assumptions()
            old_cash = cash_balance(raw_assumptions, latest)
            save_assumptions({"cash_balance": old_cash - quantity_change * transaction_price})
        row = pd.DataFrame([{
            "symbol": clean_symbol, "name": name.strip(), "asset_type": asset_type,
            "sector": sector.strip(), "strategy": strategy, "quantity": saved_quantity,
            "cost_price": cost_price, "current_price": current_price,
            "risk_price": risk_price, "status": status,
        }])
        latest = latest[latest["symbol"] != clean_symbol]
        latest = pd.concat([latest, row], ignore_index=True)
        save_positions(latest)
        st.success(f"{clean_symbol} {name.strip()} 已保存，现金余额已按本次成交数量同步。")
        st.rerun()


def enrich_positions(df: pd.DataFrame, account_equity: float) -> pd.DataFrame:
    result = df.copy()
    result["市值"] = result["quantity"] * result["current_price"]
    result["成本"] = result["quantity"] * result["cost_price"]
    result["浮盈亏"] = result["市值"] - result["成本"]
    result["仓位占比"] = result["市值"] / account_equity
    result["单仓风险"] = result.apply(
        lambda row: max(row["cost_price"] - row["risk_price"], 0) * row["quantity"] if row["risk_price"] > 0 else 0.0,
        axis=1,
    )
    return result


def holding_action(row: pd.Series, settings: dict) -> tuple[str, str, str]:
    if row["quantity"] <= 0:
        return "safe", "未持仓", "数量为 0。"
    if row["current_price"] <= 0:
        return "warn", "缺少现价", "无法计算市值。"
    if row["strategy"] == "new":
        if row["risk_price"] <= 0:
            return "warn", "缺少止损价", "新仓必须有止损。"
        if row["current_price"] <= row["risk_price"]:
            return "danger", "触发止损", "当前价到达或跌破风控价。"
        one_r = row["cost_price"] - row["risk_price"]
        if one_r > 0 and row["current_price"] >= row["cost_price"] + 2 * one_r:
            return "warn", "推保本", "盈利达到 2R，应把止损推到开仓价。"
    if row["strategy"] == "grid":
        return "warn", "网格仓", "需要用网格计算器确认资金是否覆盖压力测试。"
    return "safe", "持有", "未触发当前持仓检查条件。"


def holding_check(defaults: dict) -> None:
    st.subheader("持仓检查")
    quote_refresh_control("checker_quote_refresh")
    raw = load_positions()
    position_maintenance(raw)
    with st.expander("批量编辑持仓表"):
        edited = positions_editor(raw)
        if st.button("保存批量修改", type="primary", width="stretch"):
            save_positions(edited)
            st.success("批量修改已保存。")
            st.rerun()
    st.caption("保存后，系统立即检查总仓位、风控价、2R 保本和网格资金提示。")
    total = st.number_input("用于检查的总资金", min_value=1_000.0, value=float(defaults["account_equity"]), step=10_000.0, format="%.0f")
    limit = st.slider("总仓位上限", min_value=0.1, max_value=1.0, value=float(defaults["normal_limit"]), step=0.05)
    enriched = enrich_positions(edited, total)
    total_market_value = float(enriched["市值"].sum())
    c3, c4, c5 = st.columns(3)
    c3.metric("持仓市值", money(total_market_value), percent(total_market_value / total))
    c4.metric("仓位上限金额", money(total * limit), percent(limit))
    c5.metric("超出/剩余额度", money(total * limit - total_market_value))
    if total_market_value > total * limit:
        status_box("danger", "超限：当前总仓位超过上限，需要降仓或停止新开仓。")
    elif total_market_value > total * limit * 0.9:
        status_box("warn", "警戒：当前总仓位接近上限。")
    else:
        status_box("safe", "安全：当前总仓位未超过上限。")
    rows = []
    for _, row in enriched.iterrows():
        level, action, reason = holding_action(row, defaults)
        rows.append(
            {
                "代码": row["symbol"],
                "名称": row["name"],
                "仓位类型": row["strategy"],
                "市值": row["市值"],
                "仓位占比": row["仓位占比"],
                "动作": action,
                "说明": reason,
                "状态": {"safe": "安全", "warn": "警戒", "danger": "超限"}[level],
            }
        )
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        column_config={
            "市值": st.column_config.NumberColumn(format="%.0f"),
            "仓位占比": st.column_config.NumberColumn(format="%.1%"),
        },
    )


def rule_items(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        items = []
        for name, detail in value.items():
            if isinstance(detail, dict):
                ratio = detail.get("target_position_ratio", "")
                ratio_text = percent(float(ratio)) if isinstance(ratio, (int, float)) else str(ratio)
                items.append(f"{name}：{detail.get('market_cap_cny', '')}，约 {ratio_text} 仓位")
            else:
                items.append(f"{name}：{detail}")
        return items
    return [str(value)] if value else []


def rules_detail(rules: dict) -> None:
    for market_key in ["stocks", "futures"]:
        market = rules["markets"][market_key]
        st.markdown(f"**{market['label']}**")
        for position_key in ["old_position", "new_position", "grid_position"]:
            position = market["position_types"][position_key]
            with st.expander(f"{market['label']} - {position['label']}"):
                for label, key in [
                    ("入场/建仓逻辑", "entry_logic"),
                    ("最大资金占比/仓位限制", "max_capital_ratio_or_position_limit"),
                    ("风险控制方式", "risk_control"),
                    ("止盈/退出规则", "take_profit_or_exit_rules"),
                ]:
                    st.markdown(f"**{label}**")
                    for item in rule_items(position.get(key)):
                        st.write(f"- {item}")
    with st.expander("全局规则"):
        for item in rule_items(rules.get("global_rules")):
            st.write(f"- {item}")


PLAN_COLUMNS = ["created_at", "market", "symbol", "name", "direction", "entry", "stop", "target", "quantity", "risk_amount", "status", "notes"]
JOURNAL_COLUMNS = ["trade_date", "market", "symbol", "name", "direction", "entry", "exit", "quantity", "outcome_r", "followed_plan", "followed_stop", "emotion", "notes", "lesson"]


def config_page(rules: dict) -> None:
    raw = load_assumptions()
    st.header("规则设置", divider="green")
    st.caption("账户资金、现金与风险上限都在这里维护；首页、持仓管理和风险复盘统一读取。")
    with st.form("config_form"):
        c1, c2, c3, c4 = st.columns(4)
        equity = c1.number_input("风控基准资金", min_value=1_000.0, value=float(raw["account_equity"]), step=10_000.0, format="%.0f")
        cash = c2.number_input("现金余额", value=cash_balance(raw), step=1_000.0, format="%.0f", help="卖出持仓后增加，买入持仓后减少；也可以按券商账户手工校准。")
        risk = c3.number_input("单笔最大风险", min_value=.001, max_value=.1, value=float(raw["trend_risk_per_trade_ratio"]), step=.001, format="%.3f")
        breakeven = c4.number_input("保本触发 R", min_value=.5, max_value=5.0, value=float(raw["breakeven_trigger_r_multiple"]), step=.25)
        c4, c5, c6 = st.columns(3)
        normal = c4.slider("平时仓位上限", .1, 1.0, float(raw["normal_max_exposure_ratio"]), .05)
        holiday = c5.slider("节假日仓位上限", .05, 1.0, float(raw["holiday_max_exposure_ratio"]), .05)
        extreme = c6.slider("单品种极端损失上限", .05, .5, float(raw["max_extreme_loss_per_instrument_ratio"]), .05)
        holiday_mode = st.checkbox("启用节假日模式", value=bool(raw["is_holiday_mode"]))
        if st.form_submit_button("保存规则", type="primary"):
            save_assumptions({
                "account_equity": equity,
                "cash_balance": cash,
                "trend_risk_per_trade_ratio": risk,
                "breakeven_trigger_r_multiple": breakeven,
                "normal_max_exposure_ratio": normal,
                "holiday_max_exposure_ratio": holiday,
                "max_extreme_loss_per_instrument_ratio": extreme,
                "is_holiday_mode": holiday_mode,
            })
            st.success("规则已保存。刷新后，所有模块将使用新参数。")
    with st.expander("查看完整仓位纪律"):
        rules_detail(rules)


def calculator_page(defaults: dict, positions: pd.DataFrame) -> None:
    st.title("Calculator · 计算")
    st.caption("只回答数字问题：最多做多少、错了亏多少、到哪里推保本。")
    trade_planner(defaults, positions)


def checker_page(defaults: dict) -> None:
    st.header("持仓管理", divider="green")
    st.caption("新增或修改持仓，并检查超仓、止损和保本动作。")
    holding_check(defaults)


def planner_page(defaults: dict) -> None:
    st.title("Planner · 加仓规划")
    st.caption("计算只是答案；计划要把入场、止损、目标和数量一起锁定。")
    plans = load_table(PLANS_PATH, PLAN_COLUMNS)
    with st.form("plan_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        market = c1.selectbox("市场", ["股票/ETF", "期货"])
        symbol = c2.text_input("代码")
        name = c3.text_input("名称")
        direction = c4.selectbox("方向", ["做多", "做空"])
        c5, c6, c7, c8 = st.columns(4)
        entry = c5.number_input("计划入场价", min_value=0.0, step=.01, format="%.3f")
        stop = c6.number_input("止损价", min_value=0.0, step=.01, format="%.3f")
        target = c7.number_input("目标价", min_value=0.0, step=.01, format="%.3f")
        quantity = c8.number_input("数量/手数", min_value=0, step=1)
        notes = st.text_area("入场理由与失效条件", placeholder="为什么做？什么情况说明判断失效？")
        submitted = st.form_submit_button("保存交易计划", type="primary")
    if submitted:
        distance = abs(entry - stop)
        risk_amount = distance * quantity
        row = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "market": market,
            "symbol": symbol.strip(), "name": name.strip(), "direction": direction,
            "entry": entry, "stop": stop, "target": target, "quantity": quantity,
            "risk_amount": risk_amount, "status": "待执行", "notes": notes.strip(),
        }
        plans = pd.concat([plans, pd.DataFrame([row])], ignore_index=True)
        save_table(PLANS_PATH, plans, PLAN_COLUMNS)
        st.success("交易计划已保存。执行后可在下方更新状态。")
    st.markdown('<div class="section-label">计划清单</div>', unsafe_allow_html=True)
    edited = st.data_editor(plans, width="stretch", hide_index=True, num_rows="dynamic", column_config={
        "status": st.column_config.SelectboxColumn("状态", options=["待执行", "已执行", "已取消", "已完成"]),
        "created_at": "创建时间", "market": "市场", "symbol": "代码", "name": "名称",
        "direction": "方向", "entry": "入场", "stop": "止损", "target": "目标", "quantity": "数量",
        "risk_amount": "计划风险", "notes": "理由/失效条件",
    })
    if st.button("保存计划状态"):
        save_table(PLANS_PATH, edited, PLAN_COLUMNS)
        st.success("计划清单已更新。")


def journal_page() -> None:
    st.title("Journal · 交易日志")
    st.caption("记录事实，不美化结果。复盘质量取决于日志是否完整。")
    journal = load_table(JOURNAL_PATH, JOURNAL_COLUMNS)
    with st.form("journal_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        trade_date = c1.date_input("交易日期", value=date.today())
        market = c2.selectbox("市场", ["股票/ETF", "期货"], key="journal_market")
        symbol = c3.text_input("代码", key="journal_symbol")
        name = c4.text_input("名称", key="journal_name")
        c5, c6, c7, c8 = st.columns(4)
        direction = c5.selectbox("方向", ["做多", "做空"], key="journal_direction")
        entry = c6.number_input("入场价", min_value=0.0, step=.01, format="%.3f", key="journal_entry")
        exit_price = c7.number_input("退出价", min_value=0.0, step=.01, format="%.3f")
        quantity = c8.number_input("数量/手数", min_value=0, step=1, key="journal_quantity")
        c9, c10, c11, c12 = st.columns(4)
        outcome_r = c9.number_input("结果（R）", step=.1, format="%.2f")
        followed_plan = c10.selectbox("按计划执行", ["是", "否"])
        followed_stop = c11.selectbox("遵守止损", ["是", "否", "不适用"])
        emotion = c12.selectbox("主要情绪", ["平静", "犹豫", "恐惧", "贪婪", "冲动"])
        notes = st.text_area("过程记录")
        lesson = st.text_area("本次教训 / 可复用经验")
        submitted = st.form_submit_button("写入日志", type="primary")
    if submitted:
        row = {"trade_date": str(trade_date), "market": market, "symbol": symbol.strip(), "name": name.strip(),
               "direction": direction, "entry": entry, "exit": exit_price, "quantity": quantity,
               "outcome_r": outcome_r, "followed_plan": followed_plan, "followed_stop": followed_stop,
               "emotion": emotion, "notes": notes.strip(), "lesson": lesson.strip()}
        journal = pd.concat([journal, pd.DataFrame([row])], ignore_index=True)
        save_table(JOURNAL_PATH, journal, JOURNAL_COLUMNS)
        st.success("交易日志已写入。")
    st.markdown('<div class="section-label">历史日志</div>', unsafe_allow_html=True)
    st.dataframe(journal.iloc[::-1], width="stretch", hide_index=True)


def trading_os_page(defaults: dict, positions: pd.DataFrame) -> None:
    st.title("Trading OS")
    st.caption(f"长期资金风险控制台 · {datetime.now().strftime('%Y 年 %m 月 %d 日')}")
    quote_refresh_control("home_quote_refresh")
    positions = load_positions()
    snap = portfolio_snapshot(positions, defaults)
    risk_utilization = snap["open_risk"] / defaults["account_equity"] if defaults["account_equity"] else 0
    max_exposure = defaults["holiday_limit"] if load_assumptions().get("is_holiday_mode") else defaults["normal_limit"]
    exposure_ok = snap["exposure"] <= max_exposure
    danger_actions = [item for item in snap["actions"] if item["level"] == "danger"]
    can_trade = exposure_ok and not danger_actions
    remaining_risk = max(defaults["account_equity"] * .05 - snap["open_risk"], 0)
    trade_risk = defaults["account_equity"] * defaults["risk_ratio"]
    slots = min(5, math.floor(remaining_risk / trade_risk)) if trade_risk else 0
    advice = f"还能新开 {slots} 笔" if can_trade and slots > 0 else ("可继续交易" if can_trade else "暂停新增风险")

    rules = [
        (exposure_ok, "未超过仓位" if exposure_ok else f"仓位超过 {percent(max_exposure)} 上限"),
        (can_trade, "可继续交易" if can_trade else "暂停新增交易"),
        (not danger_actions, "未违反规则" if not danger_actions else f"有 {len(danger_actions)} 项规则需要处理"),
    ]
    rule_rows = "".join(
        f'<div class="rule-row"><span><span class="{"check" if ok else "cross"}">{"✓" if ok else "×"}</span>{text}</span></div>'
        for ok, text in rules
    )

    sector_value = snap["enriched"].groupby("sector")["市值"].sum().sort_values(ascending=False)
    sector_counts = positions[positions["quantity"] > 0].groupby("sector").size().sort_values(ascending=False)
    if not sector_counts.empty and int(sector_counts.iloc[0]) >= 2:
        sector = html.escape(str(sector_counts.index[0]))
        ai_message = f"今天已有 {int(sector_counts.iloc[0])} 个高相关的 {sector} 品种。<br>建议不要继续增加该板块风险。"
    elif not sector_value.empty and snap["market_value"] > 0:
        sector = html.escape(str(sector_value.index[0]))
        share = float(sector_value.iloc[0] / snap["market_value"])
        ai_message = f"当前最大风险来源是 {sector}，占持仓 {percent(share)}。<br>新增计划应优先避开同方向暴露。"
    else:
        ai_message = "当前持仓数据不足。<br>补齐行业与风控价后，AI 提醒会更准确。"

    st.subheader("账户概览")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("账户总资产", f"¥{money(snap['total_assets'])}", help="现金余额加当前持仓市值。")
    c1.caption(f"现金 ¥{money(snap['cash'])} ＋ 持仓 ¥{money(snap['market_value'])}")
    c2.metric("现金余额", f"¥{money(snap['cash'])}", help="卖出增加、买入减少，也可以在规则设置中手工校准。")
    c2.caption("来源：持仓数量变化与成交价")
    c3.metric("计划亏损风险占资金", percent(risk_utilization), help="所有持仓按成本价到风控价计算的计划亏损，除以风控基准资金。")
    c3.caption(f"计划亏损 ¥{money(snap['open_risk'])} ÷ 基准资金 ¥{money(defaults['account_equity'])}")
    c4.metric("今天能否新增交易", advice, help="同时检查总仓位上限、持仓风控和剩余风险预算。")
    c4.caption(f"规则：仓位上限 {percent(max_exposure)}；单笔风险 {percent(defaults['risk_ratio'])}")

    left, right = st.columns(2)
    with left:
        st.subheader("当前持仓")
        held = positions[positions["quantity"] > 0][["symbol", "name", "quantity", "current_price", "status"]].copy()
        held.columns = ["代码", "品种", "数量", "最新价", "状态"]
        st.dataframe(held, width="stretch", hide_index=True)
        st.caption("价格来自最近一次行情刷新；持仓数量来自“持仓管理”。")
    with right:
        st.subheader("今日纪律")
        for ok, text in rules:
            if ok:
                st.success(f"✓ {text}")
            else:
                st.error(f"× {text}")
        st.caption("来源：Config 规则与 Checker 持仓检查。")

    st.subheader("AI 风险提醒")
    st.markdown(f'<div class="ai-note">{ai_message}</div>', unsafe_allow_html=True)
    st.caption("提醒只解释风险集中度，不预测行情，也不会自动下单。")


def review_page(defaults: dict, positions: pd.DataFrame) -> None:
    st.title("风险复盘")
    st.caption("只复盘当前持仓风险，不评价行情方向，也不依赖交易日志。")
    quote_refresh_control("review_quote_refresh")
    positions = load_positions()
    snap = portfolio_snapshot(positions, defaults)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("账户总资产", f"¥{money(snap['total_assets'])}", help="现金余额加当前持仓市值。")
    c2.metric("现金余额", f"¥{money(snap['cash'])}")
    c3.metric("持仓市值", f"¥{money(snap['market_value'])}", percent(snap["exposure"]))
    c4.metric("计划亏损风险", f"¥{money(snap['open_risk'])}", percent(snap["open_risk"] / defaults["account_equity"]) if defaults["account_equity"] else "-")
    st.caption(f"持仓浮盈亏：¥{money(snap['pnl'])} · 仓位规则上限：{percent(defaults['normal_limit'])}")

    findings = []
    if snap["exposure"] > defaults["normal_limit"]:
        findings.append(("danger", "总仓位超限", f"当前仓位 {percent(snap['exposure'])}，高于规则上限 {percent(defaults['normal_limit'])}。先降低仓位，再考虑新增风险。"))
    missing_risk = positions[(positions["quantity"] > 0) & (positions["risk_price"] <= 0)]
    if not missing_risk.empty:
        names = "、".join(missing_risk["name"].astype(str).tolist())
        findings.append(("warn", "缺少风控价", f"{names} 尚未填写风控价，因此计划亏损风险可能被低估。"))
    sectors = snap["enriched"].groupby("sector")["市值"].sum().sort_values(ascending=False)
    if not sectors.empty and snap["market_value"] > 0:
        top_sector = str(sectors.index[0]) or "未分类"
        top_share = float(sectors.iloc[0] / snap["market_value"])
        if top_share >= .35:
            findings.append(("warn", "板块集中", f"{top_sector} 占持仓 {percent(top_share)}。新增持仓应避免继续扩大同方向风险。"))
    for item in snap["actions"]:
        if item["level"] == "danger":
            findings.append(("danger", f"{item['symbol']} {item['name']} · {item['action']}", item["reason"]))
    if not findings:
        findings.append(("safe", "当前未发现明显风险违规", "仓位和已填写的风控条件均在规则范围内。继续保持，不因短期盈亏随意修改规则。"))
    st.subheader("复盘结论")
    for level, title, reason in findings:
        status_box(level, f"<strong>{title}</strong><br>{reason}")
    st.caption("以上结论使用最近一次行情价格、当前持仓和 Config 规则生成。")


def main() -> None:
    css()
    defaults = sidebar_defaults()
    rules = load_rules()
    positions = load_positions()
    page = st.sidebar.radio(
        "产品导航",
        ["Trading OS · 首页", "持仓管理", "规则设置", "风险复盘"],
        label_visibility="collapsed",
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### 核心流程")
    st.sidebar.caption("看风险 → 管持仓 → 调规则 → 做复盘")
    st.sidebar.markdown("---")
    st.sidebar.caption("本地数据 · 不连接券商 · 不自动交易")
    if page.startswith("Trading OS"):
        trading_os_page(defaults, positions)
    elif page == "持仓管理":
        checker_page(defaults)
    elif page == "规则设置":
        config_page(rules)
    else:
        review_page(defaults, positions)


if __name__ == "__main__":
    main()
