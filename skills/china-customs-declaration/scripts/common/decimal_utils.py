"""
Decimal 工具函数

所有金额、数量、重量相关计算统一使用 Decimal，避免浮点误差。
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Optional

# 默认金额精度
DECIMAL_PRECISION = Decimal("0.01")
# 金额容差
AMOUNT_TOLERANCE = Decimal("0.01")
# 数量精度
QUANTITY_PRECISION = Decimal("0.001")
# 重量精度
WEIGHT_PRECISION = Decimal("0.001")


def to_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """将各种格式转为 Decimal，失败时返回 default 或 None"""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default
        # 去除千分位
        cleaned = cleaned.replace(",", "").replace("，", "")
        # 去除币种符号
        for sym in ["$", "€", "£", "¥", "HK$", "US$", "€"]:
            cleaned = cleaned.replace(sym, "")
        cleaned = cleaned.strip()
        if not cleaned:
            return default
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return default
    return default


def to_decimal_safe(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """安全的 Decimal 转换，失败时返回 default"""
    result = to_decimal(value, default)
    if result is None:
        return default
    return result


def round_amount(value: Decimal, precision: Decimal = DECIMAL_PRECISION) -> Decimal:
    """四舍五入到指定精度（默认 0.01）"""
    return value.quantize(precision, rounding=ROUND_HALF_UP)


def calc_total_price(
    unit_price: Any, quantity: Any, precision: Decimal = DECIMAL_PRECISION
) -> Optional[Decimal]:
    """计算 单价 × 数量 = 总价"""
    up = to_decimal(unit_price)
    qty = to_decimal(quantity)
    if up is None or qty is None:
        return None
    return round_amount(up * qty, precision)


def check_amount_match(
    expected: Any,
    actual: Any,
    tolerance: Decimal = AMOUNT_TOLERANCE,
) -> tuple[bool, Optional[Decimal], Optional[Decimal]]:
    """
    检查金额是否匹配（在容差范围内）

    Returns:
        (是否匹配, 期望值, 实际值)
    """
    exp = to_decimal(expected)
    act = to_decimal(actual)
    if exp is None or act is None:
        return False, exp, act
    return abs(exp - act) <= tolerance, exp, act


def sum_decimal(values: list[Any]) -> Decimal:
    """对一组值求和"""
    total = Decimal("0")
    for v in values:
        d = to_decimal(v)
        if d is not None:
            total += d
    return total


def format_amount(value: Any, currency: str = "") -> str:
    """格式化金额输出"""
    d = to_decimal(value)
    if d is None:
        return "待确认"
    formatted = f"{d:,.2f}"
    if currency:
        return f"{currency} {formatted}"
    return formatted


def format_weight(value: Any) -> str:
    """格式化重量输出"""
    d = to_decimal(value)
    if d is None:
        return "待确认"
    return f"{d:,.3f} kg"


def format_quantity(value: Any) -> str:
    """格式化数量输出"""
    d = to_decimal(value)
    if d is None:
        return "待确认"
    # 整数显示无小数
    if d == d.to_integral_value():
        return str(int(d))
    return f"{d:g}"
