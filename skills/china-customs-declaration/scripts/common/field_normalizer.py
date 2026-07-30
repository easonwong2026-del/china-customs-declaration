"""
字段别名标准化工具

统一不同来源文档中的字段名、文本格式。
"""

from typing import Any, Optional

# 字段别名映射
FIELD_ALIASES: dict[str, list[str]] = {
    "中文品名": [
        "中文品名",
        "品名",
        "商品名称",
        "产品名称",
        "申报品名",
        "product_name",
    ],
    "英文品名": ["英文品名", "英文名称", "product_name_en", "english_name"],
    "品牌": ["品牌", "brand", "品牌名称", "商标", "牌子"],
    "型号": ["型号", "model", "model_no", "产品型号", "规格型号", "料号"],
    "货号": ["货号", "sku", "item_no", "article_no", "物料编码", "产品编号"],
    "HS编码": ["HS编码", "HS CODE", "hs_code", "HS", "海关编码", "商品编码"],
    "数量": ["数量", "qty", "quantity", "订货数量", "发货数量"],
    "单位": ["单位", "unit", "计量单位", "包装单位", "unit_of_measure"],
    "单价": ["单价", "unit_price", "unit price", "价格"],
    "总价": ["总价", "amount", "total_price", "total amount", "金额", "total_price"],
    "币种": ["币种", "currency", "货币", "币别"],
    "原产国": ["原产国", "country_of_origin", "产地", "原产地"],
    "毛重": ["毛重", "gross_weight", "gross weight", "G.W.", "总毛重"],
    "净重": ["净重", "net_weight", "net weight", "N.W.", "总净重"],
    "箱号": ["箱号", "case_no", "箱号/托盘号", "包装编号", "包装序号"],
    "件数": ["件数", "pieces", "箱数", "ctns", "cartons", "package_qty"],
    "体积": ["体积", "volume", "cbm", "立方米", "cubic_meter"],
    "包装尺寸": ["包装尺寸", "package_size", "尺寸", "包装规格"],
    "包装种类": ["包装种类", "package_type", "包装方式", "包装"],
    "贸易国": ["贸易国", "trade_country", "贸易国家/地区"],
    "启运国": ["启运国", "departure_country", "发运国", "起运国"],
    "最终目的国": ["最终目的国", "destination_country", "目的国", "destination"],
    "用途": ["用途", "usage", "应用领域", "应用场景"],
    "功能": ["功能", "function", "主要功能"],
    "工作原理": ["工作原理", "working_principle", "原理", "work principle"],
    "材质": ["材质", "material", "材料", "主要材质"],
    "是否整机": ["是否整机", "is_complete_unit", "是否成品"],
    "是否含无线": ["是否含无线", "has_wireless", "是否含无线功能", "无线功能"],
    "是否含电池": ["是否含电池", "has_battery", "是否含电池", "电池"],
    "技术参数": ["技术参数", "tech_params", "规格参数", "参数"],
}


def resolve_field(available_keys: list[str], target_field: str) -> Optional[str]:
    """
    根据可用键名解析出目标字段的实际键名

    Args:
        available_keys: 文档中可用的所有键名
        target_field: 统一目标字段名

    Returns:
        文档中的实际键名，未找到返回 None
    """
    aliases = FIELD_ALIASES.get(target_field, [target_field])
    for alias in aliases:
        if alias in available_keys:
            return alias
        # 大小写不敏感匹配
        for key in available_keys:
            if key.lower().replace(" ", "_") == alias.lower().replace(" ", "_"):
                return key
    return None


def normalize_text(text: Any) -> str:
    """
    文本标准化：
    - 去除首尾空格
    - 全角转半角
    - 合并连续空格
    - 英文大写标准化
    """
    if text is None:
        return ""
    s = str(text).strip()
    # 全角转半角
    result = []
    for ch in s:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(chr(0x0020))
        else:
            result.append(ch)
    s = "".join(result)
    # 合并连续空格
    while "  " in s:
        s = s.replace("  ", " ")
    return s


def normalize_model(model: Any) -> str:
    """
    型号标准化：
    - 基本文本标准化
    - 连字符和空格归一化
    """
    s = normalize_text(model)
    if not s:
        return ""
    s = s.replace("-", "-").replace("—", "-").replace("–", "-")
    s = s.upper()
    return s


def normalize_hs_code(code: Any) -> str:
    """
    HS编码标准化：
    - 去点号、空格
    - 只保留数字
    """
    s = normalize_text(code)
    if not s:
        return ""
    return s.replace(".", "").replace(" ", "")


def normalize_quantity(value: Any) -> str:
    """数量标准化"""
    s = normalize_text(value)
    return s
