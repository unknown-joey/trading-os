#!/usr/bin/env python3
"""长期资金管理仪表盘第一版。"""

# 这个脚本只使用 Python 标准库，方便你直接运行和修改。
# 第一版的目标不是预测价格，而是把“能不能做、做多少、错了亏多少”算清楚。
# 所有价格、合约乘数、极端价格都来自 CSV 样例文件，你可以手工改。
# 所有账户资金、仓位上限、风险比例都来自 JSON 配置文件，你可以手工改。
# 名义仓位 = 当前价格 * 合约乘数 * 手数，用来粗略衡量账户暴露。
# 极端亏损 = abs(当前价格 - 极端价格) * 合约乘数 * 手数，用来检查能否去杠杆。
# 趋势仓风险 = abs(开仓价 - 止损价) * 合约乘数 * 手数，用来检查单笔亏损是否小于 1%。
# 保本推进 = 当前盈利达到 2R 后，把止损抬到开仓价。
# 这不是投资建议，只是把你的规则翻译成可检查的流程。

from __future__ import annotations  # 允许类型标注在 Python 新旧版本里更稳一点。

import csv  # 用来读取 instruments.csv 和 positions.csv。
import json  # 用来读取 assumptions.json。
from dataclasses import dataclass  # 用来定义更清晰的数据结构。
from pathlib import Path  # 用来处理文件路径，避免手写字符串路径。
from typing import Iterable  # 用来标注一组数据，方便以后维护。


BASE_DIR = Path(__file__).resolve().parents[1]  # 项目根目录，也就是 long_term_risk_dashboard。
CONFIG_PATH = BASE_DIR / "config" / "assumptions.json"  # 基础假设配置文件路径。
INSTRUMENTS_PATH = BASE_DIR / "data" / "instruments.csv"  # 候选品种数据文件路径。
POSITIONS_PATH = BASE_DIR / "data" / "positions.csv"  # 当前持仓数据文件路径。


@dataclass
class Assumptions:
    """账户和风控假设。"""

    account_equity: float  # 账户权益。
    normal_max_exposure_ratio: float  # 平时最大总名义仓位比例。
    holiday_max_exposure_ratio: float  # 节假日最大总名义仓位比例。
    trend_risk_per_trade_ratio: float  # 每笔趋势仓最大亏损比例。
    breakeven_trigger_r_multiple: float  # 推保本所需的 R 倍数。
    max_extreme_loss_per_instrument_ratio: float  # 单品种一手极端亏损占账户比例上限。
    is_holiday_mode: bool  # 是否启用节假日仓位限制。

    @property
    def max_exposure_ratio(self) -> float:
        """根据当前模式返回总仓位上限。"""
        if self.is_holiday_mode:  # 如果是节假日模式，就用更低的仓位上限。
            return self.holiday_max_exposure_ratio  # 返回节假日仓位上限。
        return self.normal_max_exposure_ratio  # 否则返回平时仓位上限。

    @property
    def max_exposure_value(self) -> float:
        """返回账户允许的最大名义仓位。"""
        return self.account_equity * self.max_exposure_ratio  # 账户资金乘以上限比例。

    @property
    def max_trade_risk_value(self) -> float:
        """返回单笔趋势仓允许亏损金额。"""
        return self.account_equity * self.trend_risk_per_trade_ratio  # 账户资金乘以单笔风险比例。

    @property
    def max_extreme_loss_per_instrument_value(self) -> float:
        """返回单品种一手极端亏损允许金额。"""
        return self.account_equity * self.max_extreme_loss_per_instrument_ratio  # 账户资金乘以单品种极端亏损比例。


@dataclass
class Instrument:
    """候选品种。"""

    symbol: str  # 品种代码。
    name: str  # 品种名称。
    risk_group: str  # 风险组，用来做相关性粗筛。
    current_price: float  # 当前价格。
    extreme_price: float  # 极端压力价格。
    contract_multiplier: float  # 合约乘数。
    min_lots: int  # 最小交易手数。
    market_state: str  # 市场状态：low_grid、trend、risk、unclear。
    grid_step_ratio: float  # 网格间距比例。
    grid_lots: int  # 每格手数。
    max_grid_layers: int  # 最大网格层数。
    trend_entry_price: float  # 趋势计划开仓价。
    trend_stop_price: float  # 趋势计划止损价。

    @property
    def notional_per_lot(self) -> float:
        """返回一手名义价值。"""
        return self.current_price * self.contract_multiplier  # 当前价格乘以合约乘数。

    @property
    def extreme_loss_per_lot(self) -> float:
        """返回一手极端亏损。"""
        return abs(self.current_price - self.extreme_price) * self.contract_multiplier  # 极端价格差乘以合约乘数。

    @property
    def trend_risk_per_lot(self) -> float:
        """返回一手趋势仓止损风险。"""
        return abs(self.trend_entry_price - self.trend_stop_price) * self.contract_multiplier  # 开仓价和止损价的差乘以合约乘数。


@dataclass
class Position:
    """当前持仓。"""

    symbol: str  # 品种代码。
    position_id: str  # 持仓编号。
    strategy: str  # 策略类型：trend 或 grid。
    lots: int  # 持仓手数。
    entry_price: float  # 开仓价格。
    stop_price: float | None  # 止损价格，网格仓可以为空。
    current_price: float  # 当前价格。
    status: str  # 仓位状态：risk、breakeven、grid、closed。


def load_assumptions(path: Path) -> Assumptions:
    """读取账户基础假设。"""
    raw = json.loads(path.read_text(encoding="utf-8"))  # 读取 JSON 并转成字典。
    return Assumptions(  # 把字典转成 Assumptions 对象。
        account_equity=float(raw["account_equity"]),  # 账户权益。
        normal_max_exposure_ratio=float(raw["normal_max_exposure_ratio"]),  # 平时仓位上限。
        holiday_max_exposure_ratio=float(raw["holiday_max_exposure_ratio"]),  # 节假日仓位上限。
        trend_risk_per_trade_ratio=float(raw["trend_risk_per_trade_ratio"]),  # 单笔趋势风险。
        breakeven_trigger_r_multiple=float(raw["breakeven_trigger_r_multiple"]),  # 推保本 R 倍数。
        max_extreme_loss_per_instrument_ratio=float(raw["max_extreme_loss_per_instrument_ratio"]),  # 单品种极端亏损上限。
        is_holiday_mode=bool(raw["is_holiday_mode"]),  # 是否节假日模式。
    )


def load_instruments(path: Path) -> list[Instrument]:
    """读取候选品种表。"""
    with path.open("r", encoding="utf-8", newline="") as file:  # 打开 CSV 文件。
        rows = list(csv.DictReader(file))  # 读取成字典列表。
    return [  # 把每一行转成 Instrument 对象。
        Instrument(  # 创建一个候选品种。
            symbol=row["symbol"],  # 品种代码。
            name=row["name"],  # 品种名称。
            risk_group=row["risk_group"],  # 风险组。
            current_price=float(row["current_price"]),  # 当前价格。
            extreme_price=float(row["extreme_price"]),  # 极端价格。
            contract_multiplier=float(row["contract_multiplier"]),  # 合约乘数。
            min_lots=int(row["min_lots"]),  # 最小手数。
            market_state=row["market_state"],  # 市场状态。
            grid_step_ratio=float(row["grid_step_ratio"]),  # 网格间距比例。
            grid_lots=int(row["grid_lots"]),  # 每格手数。
            max_grid_layers=int(row["max_grid_layers"]),  # 最大网格层数。
            trend_entry_price=float(row["trend_entry_price"]),  # 趋势开仓价。
            trend_stop_price=float(row["trend_stop_price"]),  # 趋势止损价。
        )
        for row in rows  # 遍历 CSV 的每一行。
    ]


def load_positions(path: Path) -> list[Position]:
    """读取当前持仓表。"""
    with path.open("r", encoding="utf-8", newline="") as file:  # 打开 CSV 文件。
        rows = list(csv.DictReader(file))  # 读取成字典列表。
    return [  # 把每一行转成 Position 对象。
        Position(  # 创建一个持仓对象。
            symbol=row["symbol"],  # 品种代码。
            position_id=row["position_id"],  # 持仓编号。
            strategy=row["strategy"],  # 策略类型。
            lots=int(row["lots"]),  # 持仓手数。
            entry_price=float(row["entry_price"]),  # 开仓价。
            stop_price=float(row["stop_price"]) if row["stop_price"] else None,  # 止损价，空值转成 None。
            current_price=float(row["current_price"]),  # 当前价。
            status=row["status"],  # 仓位状态。
        )
        for row in rows  # 遍历 CSV 的每一行。
    ]


def money(value: float) -> str:
    """把数字格式化成金额。"""
    return f"{value:,.0f}"  # 千分位，不显示小数。


def percent(value: float) -> str:
    """把比例格式化成百分比。"""
    return f"{value * 100:.1f}%"  # 比例乘以 100，并保留一位小数。


def find_instrument(symbol: str, instruments: Iterable[Instrument]) -> Instrument | None:
    """按品种代码查找候选品种。"""
    for instrument in instruments:  # 遍历所有候选品种。
        if instrument.symbol == symbol:  # 如果代码匹配。
            return instrument  # 返回这个品种。
    return None  # 找不到就返回空。


def position_notional(position: Position, instrument: Instrument) -> float:
    """计算当前持仓名义价值。"""
    return position.current_price * instrument.contract_multiplier * position.lots  # 当前价乘以合约乘数再乘以手数。


def position_open_risk(position: Position, instrument: Instrument) -> float:
    """计算未保本趋势仓的当前止损风险。"""
    if position.strategy != "trend":  # 如果不是趋势仓。
        return 0.0  # 网格仓不在这里计算止损风险。
    if position.status == "breakeven":  # 如果已经推保本。
        return 0.0  # 保本仓不占用计划风险额度。
    if position.stop_price is None:  # 如果趋势仓没有止损。
        return float("inf")  # 这属于严重风险，直接返回无限大。
    return abs(position.entry_price - position.stop_price) * instrument.contract_multiplier * position.lots  # 计算止损金额。


def position_r_multiple(position: Position, instrument: Instrument) -> float | None:
    """计算趋势仓当前盈利是几 R。"""
    if position.strategy != "trend":  # 如果不是趋势仓。
        return None  # 网格仓不计算 R。
    if position.stop_price is None:  # 如果没有止损价。
        return None  # 没法计算 R。
    one_r = abs(position.entry_price - position.stop_price) * instrument.contract_multiplier  # 一手的一倍风险。
    if one_r == 0:  # 如果止损等于开仓价。
        return None  # 避免除以零。
    profit_per_lot = (position.current_price - position.entry_price) * instrument.contract_multiplier  # 当前每手浮动盈利。
    return profit_per_lot / one_r  # 返回当前盈利的 R 倍数。


def print_section(title: str) -> None:
    """打印分区标题。"""
    print()  # 先空一行。
    print("=" * 72)  # 打印分隔线。
    print(title)  # 打印标题。
    print("=" * 72)  # 再打印分隔线。


def account_dashboard(assumptions: Assumptions, instruments: list[Instrument], positions: list[Position]) -> None:
    """账户总控仪表盘。"""
    print_section("1. 入场前检查：账户还能不能承担新风险")  # 打印模块标题。
    total_notional = 0.0  # 初始化总名义仓位。
    total_open_risk = 0.0  # 初始化未保本风险。
    for position in positions:  # 遍历每一笔持仓。
        instrument = find_instrument(position.symbol, instruments)  # 找到对应品种。
        if instrument is None:  # 如果找不到品种。
            continue  # 跳过这笔持仓。
        total_notional += position_notional(position, instrument)  # 累加名义仓位。
        total_open_risk += position_open_risk(position, instrument)  # 累加未保本风险。
    exposure_ratio = total_notional / assumptions.account_equity  # 计算当前总仓位比例。
    open_risk_ratio = total_open_risk / assumptions.account_equity  # 计算未保本风险比例。
    print(f"账户权益：{money(assumptions.account_equity)}")  # 打印账户权益。
    print(f"当前模式：{'节假日/风险模式' if assumptions.is_holiday_mode else '平时模式'}")  # 打印当前模式。
    print(f"当前总名义仓位：{money(total_notional)}（{percent(exposure_ratio)}）")  # 打印总仓位。
    print(f"允许总名义仓位：{money(assumptions.max_exposure_value)}（{percent(assumptions.max_exposure_ratio)}）")  # 打印允许仓位。
    print(f"当前未保本风险：{money(total_open_risk)}（{percent(open_risk_ratio)}）")  # 打印未保本风险。
    if total_notional > assumptions.max_exposure_value:  # 如果总仓位超限。
        print("动作：总仓位超限，先降仓，不开新仓。")  # 给出动作。
    else:  # 如果总仓位没有超限。
        print("动作：总仓位未超限，可以继续进入后续检查。")  # 给出动作。


def instrument_survival_dashboard(assumptions: Assumptions, instruments: list[Instrument]) -> list[Instrument]:
    """品种生存仪表盘。"""
    print_section("2. 入场前检查：品种能不能碰")  # 打印模块标题。
    allowed: list[Instrument] = []  # 准备保存通过筛选的品种。
    for instrument in instruments:  # 遍历候选品种。
        min_extreme_loss = instrument.extreme_loss_per_lot * instrument.min_lots  # 计算最小交易单位的极端亏损。
        can_survive = min_extreme_loss <= assumptions.max_extreme_loss_per_instrument_value  # 判断是否通过。
        status = "通过" if can_survive else "剔除"  # 转成人能看的状态。
        print(  # 打印品种检查结果。
            f"{instrument.symbol} {instrument.name} | 风险组：{instrument.risk_group} | "
            f"一手名义：{money(instrument.notional_per_lot)} | "
            f"一手极端亏损：{money(instrument.extreme_loss_per_lot)} | "
            f"结论：{status}"
        )
        if can_survive:  # 如果通过生存检查。
            allowed.append(instrument)  # 放入候选池。
    return allowed  # 返回通过的品种。


def correlation_dashboard(instruments: list[Instrument], positions: list[Position]) -> None:
    """相关性粗筛仪表盘。"""
    print_section("3. 入场前检查：是不是重复押同一个风险")  # 打印模块标题。
    held_symbols = {position.symbol for position in positions if position.status != "closed"}  # 取出当前仍持有的品种代码。
    group_to_symbols: dict[str, list[str]] = {}  # 准备按风险组聚合品种。
    for instrument in instruments:  # 遍历候选品种。
        if instrument.symbol in held_symbols:  # 只检查当前持仓。
            group_to_symbols.setdefault(instrument.risk_group, []).append(instrument.symbol)  # 按风险组放入列表。
    if not group_to_symbols:  # 如果没有持仓。
        print("当前没有持仓，不存在重复押注。")  # 打印提示。
        return  # 结束模块。
    for risk_group, symbols in group_to_symbols.items():  # 遍历每个风险组。
        if len(symbols) > 1:  # 如果同组超过一个。
            print(f"{risk_group}：{', '.join(symbols)} | 动作：强相关重复，只保留一个主品种。")  # 提示降重。
        else:  # 如果同组只有一个。
            print(f"{risk_group}：{', '.join(symbols)} | 动作：暂未发现同组重复持仓。")  # 提示通过。


def grid_stress_dashboard(assumptions: Assumptions, instruments: list[Instrument]) -> None:
    """网格压力测试仪表盘。"""
    print_section("4. 入场检查：低位网格会不会拖死账户")  # 打印模块标题。
    grid_candidates = [instrument for instrument in instruments if instrument.market_state == "low_grid"]  # 只挑低位网格候选。
    if not grid_candidates:  # 如果没有候选。
        print("当前没有 low_grid 状态品种。")  # 打印提示。
        return  # 结束模块。
    for instrument in grid_candidates:  # 遍历每个网格候选。
        max_lots = instrument.grid_lots * instrument.max_grid_layers  # 计算最大补仓后的总手数。
        max_notional = instrument.current_price * instrument.contract_multiplier * max_lots  # 粗略计算最大名义仓位。
        stress_loss_30 = instrument.current_price * 0.30 * instrument.contract_multiplier * max_lots  # 粗略计算下跌 30% 的亏损。
        stress_loss_50 = instrument.current_price * 0.50 * instrument.contract_multiplier * max_lots  # 粗略计算下跌 50% 的亏损。
        pass_exposure = max_notional <= assumptions.max_exposure_value  # 检查最大名义仓位是否超限。
        pass_stress = stress_loss_50 <= assumptions.account_equity * assumptions.max_exposure_ratio  # 检查 50% 压力亏损是否过大。
        decision = "允许轻仓网格" if pass_exposure and pass_stress else "缩小网格或放弃"  # 给出决策。
        print(  # 打印压力测试结果。
            f"{instrument.symbol} {instrument.name} | 最大层数：{instrument.max_grid_layers} | "
            f"最大手数：{max_lots} | 最大名义：{money(max_notional)} | "
            f"跌30%估算亏损：{money(stress_loss_30)} | 跌50%估算亏损：{money(stress_loss_50)} | "
            f"动作：{decision}"
        )


def trend_position_size_dashboard(assumptions: Assumptions, instruments: list[Instrument]) -> None:
    """趋势仓位计算仪表盘。"""
    print_section("5. 入场/加仓检查：趋势仓错了最多亏多少")  # 打印模块标题。
    trend_candidates = [instrument for instrument in instruments if instrument.market_state == "trend"]  # 只挑趋势候选。
    if not trend_candidates:  # 如果没有趋势候选。
        print("当前没有 trend 状态品种。")  # 打印提示。
        return  # 结束模块。
    for instrument in trend_candidates:  # 遍历趋势候选。
        risk_per_lot = instrument.trend_risk_per_lot  # 计算一手止损风险。
        raw_lots = assumptions.max_trade_risk_value / risk_per_lot if risk_per_lot > 0 else 0  # 根据 1% 风险反推手数。
        allowed_lots = int(raw_lots)  # 期货手数通常取整数，先向下取整。
        actual_risk = allowed_lots * risk_per_lot  # 计算实际风险。
        actual_notional = allowed_lots * instrument.notional_per_lot  # 计算实际名义仓位。
        can_open = allowed_lots >= instrument.min_lots and actual_notional <= assumptions.max_exposure_value  # 判断是否可开。
        decision = f"最多开 {allowed_lots} 手" if can_open else "不做或缩小止损距离"  # 给出动作。
        print(  # 打印趋势仓计算结果。
            f"{instrument.symbol} {instrument.name} | 开仓：{instrument.trend_entry_price:g} | "
            f"止损：{instrument.trend_stop_price:g} | 一手风险：{money(risk_per_lot)} | "
            f"单笔风险上限：{money(assumptions.max_trade_risk_value)} | "
            f"计算手数：{allowed_lots} | 实际风险：{money(actual_risk)} | "
            f"动作：{decision}"
        )


def breakeven_dashboard(assumptions: Assumptions, instruments: list[Instrument], positions: list[Position]) -> None:
    """保本推进仪表盘。"""
    print_section("6. 止盈检查：哪些仓位应该推保本")  # 打印模块标题。
    found_trend = False  # 用来判断是否有趋势仓。
    for position in positions:  # 遍历每一笔持仓。
        instrument = find_instrument(position.symbol, instruments)  # 找到对应品种。
        if instrument is None:  # 如果找不到品种。
            continue  # 跳过这笔持仓。
        r_multiple = position_r_multiple(position, instrument)  # 计算当前 R 倍数。
        if r_multiple is None:  # 如果不是趋势仓或无法计算。
            continue  # 跳过。
        found_trend = True  # 标记已经找到趋势仓。
        should_breakeven = r_multiple >= assumptions.breakeven_trigger_r_multiple and position.status != "breakeven"  # 判断是否需要推保本。
        if should_breakeven:  # 如果达到推保本条件。
            action = "达到2R，止损抬到开仓价，状态改为保本仓"  # 给出动作。
        elif position.status == "breakeven":  # 如果已经保本。
            action = "已经是保本仓，继续持有或按后续规则跟踪"  # 给出动作。
        else:  # 如果还没达到 2R。
            action = "未到2R，继续按原止损管理"  # 给出动作。
        print(  # 打印保本推进检查结果。
            f"{position.position_id} {position.symbol} | 当前R：{r_multiple:.2f} | "
            f"状态：{position.status} | 动作：{action}"
        )
    if not found_trend:  # 如果没有趋势仓。
        print("当前没有可计算 R 倍数的趋势仓。")  # 打印提示。


def risk_event_dashboard(assumptions: Assumptions) -> None:
    """风险事件仪表盘。"""
    print_section("7. 总风控检查：节假日或风险事件要不要降仓")  # 打印模块标题。
    if assumptions.is_holiday_mode:  # 如果配置里启用了节假日模式。
        print(f"当前是节假日/风险模式，总仓位上限自动降为 {percent(assumptions.holiday_max_exposure_ratio)}。")  # 打印限制。
        print("动作：暂停激进开仓，优先降仓或只保留确定要长期持有的轻仓。")  # 给出动作。
    else:  # 如果不是节假日模式。
        print(f"当前是平时模式，总仓位上限为 {percent(assumptions.normal_max_exposure_ratio)}。")  # 打印限制。
        print("动作：仍然需要在重大事件前手动切换 is_holiday_mode。")  # 给出动作。


def main() -> None:
    """程序入口。"""
    assumptions = load_assumptions(CONFIG_PATH)  # 读取基础假设。
    instruments = load_instruments(INSTRUMENTS_PATH)  # 读取候选品种。
    positions = load_positions(POSITIONS_PATH)  # 读取当前持仓。
    account_dashboard(assumptions, instruments, positions)  # 启动账户总控仪表盘。
    allowed_instruments = instrument_survival_dashboard(assumptions, instruments)  # 启动品种生存仪表盘。
    correlation_dashboard(instruments, positions)  # 用完整品种表检查已有持仓是否重复押注。
    grid_stress_dashboard(assumptions, allowed_instruments)  # 启动网格压力测试仪表盘。
    trend_position_size_dashboard(assumptions, allowed_instruments)  # 启动趋势仓位计算仪表盘。
    breakeven_dashboard(assumptions, instruments, positions)  # 用完整品种表检查已有趋势仓是否该推保本。
    risk_event_dashboard(assumptions)  # 启动风险事件仪表盘。


if __name__ == "__main__":  # 只有直接运行这个文件时才执行。
    main()  # 运行主程序。
