#!/usr/bin/env python3
"""
监管风险规则引擎

基于业务条件（进口/出口、目的地、贸易方式、产品特征等）进行条件式风险判断。
每条风险包含触发条件、确认条件、缺失信息和等级。

核心原则：
1. "含无线功能" 仅触发 "需要核实 SRRC" (verify 级别)，绝不自行得出 "违法" 结论
2. "含电池" 仅触发电池核查流程，不未经确认就断言全部证书要求
3. 风险等级必须基于贸易方向、目的地、贸易方式等条件判断
4. 缺少业务背景时标记为 verify 级别，绝不升级为 critical
5. 每条风险明确区分 "已确认条件" vs "缺失信息"
6. 所有输出区分 "已确认" vs "推断" vs "待确认" vs "需官方核实"
"""

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))


# ──────────────────────────────────────────────
# 枚举
# ──────────────────────────────────────────────


class RiskLevel(str, Enum):
    """风险等级（与 models.py 保持一致）"""

    CRITICAL = "critical"  # 明确依据，可能导致拒绝/查扣
    HIGH = "high"  # 高概率，需核验证书
    VERIFY = "verify"  # 触发特征，需核实
    MEDIUM = "medium"  # 单证缺失，可能引起补报
    NOTICE = "notice"  # 优化建议
    NOT_APPLICABLE = "not_applicable"  # 确认不适用


LEVEL_ORDER = {
    RiskLevel.CRITICAL: 0,
    RiskLevel.HIGH: 1,
    RiskLevel.VERIFY: 2,
    RiskLevel.MEDIUM: 3,
    RiskLevel.NOTICE: 4,
    RiskLevel.NOT_APPLICABLE: 5,
}

# ──────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────


@dataclass
class RiskResult:
    """风险判定结果"""

    risk_id: str
    category: str  # "SRRC", "CCC", "BATTERY", "WOOD_PACKAGING", "IPR", "EXPORT_CONTROL", "GENERAL"
    level: RiskLevel
    title: str
    description: str
    triggered_by: list[str]  # 触发条件的字段/值
    conditions_confirmed: list[str]  # 已确认的条件
    conditions_missing: list[str]  # 缺失的判定信息
    conclusion: str
    recommended_action: str
    source: str = ""
    verification_date: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = {}
        for k, v in asdict(self).items():
            if isinstance(v, Enum):
                result[k] = v.value
            elif isinstance(v, Decimal):
                result[k] = str(v)
            else:
                result[k] = v
        return result


def _get_bool(data: dict, key: str, default: bool = False) -> bool:
    """安全地从 dict 中获取布尔值"""
    val = data.get(key, default)
    if isinstance(val, str):
        return val.lower() in ("true", "yes", "1", "是", "有", "含")
    return bool(val)


def _get_str(data: dict, key: str, default: str = "") -> str:
    """安全地从 dict 中获取字符串值"""
    val = data.get(key, default)
    if val is None:
        return default
    return str(val).strip()


def _get_dict(data: dict, key: str, default: Optional[dict] = None) -> dict:
    """安全地从 dict 中获取子 dict"""
    val = data.get(key, default)
    if isinstance(val, dict):
        return val
    return default or {}


def _dest_is_china_mainland(destination: str) -> bool:
    """判断目的地是否为中国大陆"""
    if not destination:
        return False
    destination = destination.strip().lower()
    china_keywords = ["中国", "china", "mainland", "cn", "chn", "中国大陆", "境内"]
    return any(kw in destination for kw in china_keywords)


def _trade_direction_is(data: Optional[dict], direction: str) -> bool:
    """判断贸易方向"""
    if data is None:
        return False
    td = _get_str(data, "trade_direction")
    if not td:
        return False
    return direction in td.lower() or direction in td


# ──────────────────────────────────────────────
# 辅助：产品特征提取
# ──────────────────────────────────────────────


def _has_wireless(product_data: dict) -> bool:
    """检查产品是否有无线功能"""
    wireless = _get_dict(product_data, "wireless")
    if wireless and _get_bool(wireless, "has_wireless"):
        return True
    # 同时也检查产品顶层字段
    return bool(_get_bool(product_data, "has_wireless"))


def _has_battery(product_data: dict) -> bool:
    """检查产品是否含电池"""
    battery = _get_dict(product_data, "battery")
    if battery:
        if _get_bool(battery, "is_built_in") or _get_bool(battery, "is_independent"):
            return True
        if battery.get("battery_type"):
            return True
    return bool(_get_bool(product_data, "has_battery"))


def _get_battery_info(product_data: dict) -> dict:
    """获取电池信息"""
    return _get_dict(product_data, "battery")


def _get_wireless_info(product_data: dict) -> dict:
    """获取无线信息"""
    return _get_dict(product_data, "wireless")


def _is_in_ccc_scope(product_data: dict) -> bool:
    """初步判断是否可能属于 CCC 范围（非正式判定）"""
    name_cn = _get_str(product_data, "name_cn")
    hs_code = _get_str(product_data, "hs_code")
    usage = _get_str(product_data, "usage")
    function = _get_str(product_data, "function")

    # 常见 CCC 目录关键词（仅供参考，非正式判断依据）
    ccc_keywords = [
        "电源",
        "适配器",
        "充电器",
        "电线",
        "电缆",
        "开关",
        "插头",
        "插座",
        "灯具",
        "家电",
        "空调",
        "冰箱",
        "洗衣机",
        "电视",
        "显示器",
        "电脑",
        "笔记本",
        "平板",
        "手机",
        "电话",
        "路由器",
        "交换机",
        "玩具",
        "童车",
        "安全座椅",
        "防护服",
        "头盔",
        "消防",
        "安防",
        "摄像头",
        "门锁",
        "马达",
        "电机",
        "泵",
        "阀门",
        "医疗器械",
        "体温计",
        "血压计",
    ]

    text_to_check = f"{name_cn} {usage} {function} {hs_code}"
    return any(kw in text_to_check for kw in ccc_keywords)


def _has_wood_packaging(product_data: dict) -> bool:
    """检查是否有木质包装"""
    return _get_bool(product_data, "has_wood_packaging")


def _is_generic_name(name_cn: str) -> bool:
    """判断是否为宽泛的商品名称"""
    generic_keywords = [
        "电子产品",
        "设备",
        "配件",
        "零件",
        "物品",
        "商品",
        "产品",
        "用具",
        "器具",
        "工具",
        "材料",
        "元件",
        "组件",
        "electronic",
        "device",
        "equipment",
        "part",
        "accessory",
        "component",
        "material",
    ]
    if not name_cn:
        return True  # 空名称视为宽泛
    return any(
        name_cn.strip() == kw or name_cn.strip().endswith(kw) for kw in generic_keywords
    )


# ──────────────────────────────────────────────
# 规则定义
# ──────────────────────────────────────────────

RULES: list[dict] = []


# ========================
# 1. SRRC 规则
# ========================


def rule_srrc_general(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """
    SRRC-GENERAL：产品含无线 + 进口中国大陆 → verify 级别
    无线功能本身绝不直接判定为 critical/high，必须基于业务条件。
    """
    if not _has_wireless(product_data):
        return None

    triggered_by = ["product.wireless.has_wireless=True"]
    wireless = _get_wireless_info(product_data)
    confirmed = ["产品确认含无线通信功能"]
    missing = []

    if wireless.get("wireless_types"):
        confirmed.append(f"无线类型: {', '.join(wireless['wireless_types'])}")
    else:
        missing.append("无线通信类型/技术（Wi-Fi/蓝牙/4G/5G/NFC等）")

    if wireless.get("frequency_bands"):
        confirmed.append(f"工作频段: {', '.join(wireless['frequency_bands'])}")
    else:
        missing.append("工作频段信息")

    trade_direction = _get_str(trade_data or {}, "trade_direction")
    destination = _get_str(trade_data or {}, "destination_country")

    if (
        trade_direction
        and _trade_direction_is(trade_data, "进口")
        and _dest_is_china_mainland(destination)
    ):
        triggered_by.append(f"trade_direction={trade_direction}")
        triggered_by.append(f"destination_country={destination}")
        confirmed.append(f"贸易方向: {trade_direction}")
        confirmed.append(f"目的地: {destination}")
        confirmed.append("需核实中国大陆 SRRC 型号核准要求")

        # 已知无线模块型号但无SRRC证书号
        module_model = _get_str(wireless, "module_model")
        module_has_srrc = wireless.get("module_has_srrc", None)

        if module_model:
            confirmed.append(f"无线模块型号: {module_model}")
            if module_has_srrc is False or str(module_has_srrc).lower() == "false":
                # 已知模块型号但确认无SRRC → high
                missing.append("SRRC 型号核准证书编号")
                return RiskResult(
                    risk_id="SRRC-GENERAL",
                    category="SRRC",
                    level=RiskLevel.HIGH,
                    title="无线模块已知无 SRRC 核准",
                    description="产品含无线通信功能，无线模块型号已知但显示未取得 SRRC 型号核准证，需获取证书编号",
                    triggered_by=triggered_by,
                    conditions_confirmed=confirmed,
                    conditions_missing=missing,
                    conclusion=f"模块 {module_model} 标记为无 SRRC 核准，需确认并补办",
                    recommended_action="1) 联系模块供应商获取 SRRC 证书 2) 如未办理则提交型号核准申请 3) 保留核准证书备查",
                    source="rule_engine",
                    verification_date=datetime.now().strftime("%Y-%m-%d"),
                )
            elif module_has_srrc is True:
                confirmed.append("无线模块标记为已取得 SRRC 核准")
                return RiskResult(
                    risk_id="SRRC-GENERAL",
                    category="SRRC",
                    level=RiskLevel.VERIFY,
                    title="无线模块已标记 SRRC，需核验证书有效性",
                    description="产品含无线通信功能，无线模块已标记 SRRC 核准，建议核验证书编号和有效期",
                    triggered_by=triggered_by,
                    conditions_confirmed=confirmed,
                    conditions_missing=["SRRC 证书编号", "证书有效期"],
                    conclusion=f"模块 {module_model} 标记为有 SRRC，需核验证书真实性和有效期",
                    recommended_action="1) 获取 SRRC 证书编号 2) 在工信部官网查询证书有效性 3) 确认证书覆盖进口产品型号",
                    source="rule_engine",
                    verification_date=datetime.now().strftime("%Y-%m-%d"),
                )
            else:
                missing.append("SRRC 型号核准状态（有/无证书编号）")
        else:
            missing.append("无线模块型号")
            missing.append("SRRC 型号核准状态")

        level = RiskLevel.VERIFY
        conclusion = "产品含无线功能且进口至中国大陆，必须核实 SRRC 型号核准要求"
        recommended = (
            "1) 确认无线模块型号和频段\n"
            "2) 查询工信部 SRRC 目录确认是否在核准范围内\n"
            "3) 如需办理，提交型号核准申请\n"
            "4) 保留 SRRC 核准证书备查"
        )

    elif trade_direction and _trade_direction_is(trade_data, "出口"):
        triggered_by.append(f"trade_direction={trade_direction}")
        confirmed.append(f"贸易方向: {trade_direction}")
        if destination:
            triggered_by.append(f"destination_country={destination}")
            confirmed.append(f"目的地: {destination}")

        if _dest_is_china_mainland(destination):
            confirmed.append("目的地为中国大陆")
            level = RiskLevel.VERIFY
            conclusion = "出口至中国大陆且含无线功能，需按中国大陆要求办理 SRRC"
            recommended = "确认无线模块频段，按中国大陆 SRRC 要求办理型号核准"
        else:
            level = RiskLevel.NOTICE
            conclusion = "出口含无线产品至非中国大陆地区，需确认目的国无线认证要求"
            recommended = (
                "1) 查询目的国无线认证要求（如 FCC/CE/IC 等）\n"
                "2) 确认无线模块是否具备目的国认证\n"
                "3) 如无则协助办理当地认证"
            )

    else:
        # 无贸易方向
        missing.append("贸易方向（进口/出口）")
        missing.append("目的地国家/地区")
        level = RiskLevel.VERIFY
        conclusion = "产品含无线功能，但缺少贸易方向和目的地信息，需补充业务背景"
        recommended = "补充贸易方向和目的地，根据具体场景判断 SRRC 或目的国无线认证要求"

    return RiskResult(
        risk_id="SRRC-GENERAL",
        category="SRRC",
        level=level,
        title="无线功能认证需求核实",
        description="产品含无线通信功能，需根据业务场景核实无线认证要求",
        triggered_by=triggered_by,
        conditions_confirmed=confirmed,
        conditions_missing=missing,
        conclusion=conclusion,
        recommended_action=recommended,
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


RULES.append(
    {
        "rule_id": "SRRC-GENERAL",
        "category": "SRRC",
        "condition": rule_srrc_general,
        "description": "含无线功能 → 根据贸易方向/目的地判断 SRRC 认证需求",
    }
)


# ========================
# 2. CCC 规则
# ========================


def rule_ccc_import(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """
    CCC-IMPORT：产品可能在 CCC 目录范围内 + 进口中国大陆 → verify
    检查是否存在豁免条件（样品、维修、暂时进出口等）
    """
    if not _is_in_ccc_scope(product_data):
        return None

    name_cn = _get_str(product_data, "name_cn")
    hs_code = _get_str(product_data, "hs_code")
    trade_direction = _get_str(trade_data or {}, "trade_direction")
    destination = _get_str(trade_data or {}, "destination_country")
    trade_mode = _get_str(trade_data or {}, "trade_mode")

    triggered_by = ["product.name_cn包含CCC关键词"]
    confirmed = [f"产品名称: {name_cn}"]
    missing = []

    if hs_code:
        triggered_by.append(f"product.hs_code={hs_code}")
        confirmed.append(f"HS编码: {hs_code}")
    else:
        missing.append("HS编码（用于精确判断 CCC 目录覆盖范围）")

    if not _trade_direction_is(trade_data, "进口") or not _dest_is_china_mainland(
        destination
    ):
        confirmed.append("非进口中国大陆场景，CCC 要求通常不适用（需确认目的国法规）")
        return RiskResult(
            risk_id="CCC-IMPORT",
            category="CCC",
            level=RiskLevel.NOTICE,
            title="非中国大陆进口，CCC 认证要求不适用",
            description="产品特征可能涉及 CCC 目录，但非进口中国大陆，CCC 认证要求通常不适用",
            triggered_by=triggered_by,
            conditions_confirmed=confirmed,
            conditions_missing=[],
            conclusion="非中国大陆进口，需确认目的国强制认证要求（如 CE/FCC 等）",
            recommended_action="确认目的国的强制认证要求",
            source="rule_engine",
            verification_date=datetime.now().strftime("%Y-%m-%d"),
        )

    triggered_by.append(f"trade_direction={trade_direction}")
    triggered_by.append(f"destination_country={destination}")
    confirmed.append(f"贸易方向: {trade_direction}")
    confirmed.append(f"目的地: {destination}")
    confirmed.append("进口中国大陆，需核实 CCC 认证要求")

    # 检查豁免条件
    exemption_modes = [
        "样品",
        "维修",
        "暂时进出口",
        "退运",
        "返修",
        "sample",
        "repair",
        "temporary",
        "return",
        "rework",
    ]
    is_exempt = False
    if trade_mode:
        triggered_by.append(f"trade_mode={trade_mode}")
        confirmed.append(f"贸易方式: {trade_mode}")
        for em in exemption_modes:
            if em in trade_mode.lower() or em in trade_mode:
                is_exempt = True
                confirmed.append(f"贸易方式属于可豁免场景: {trade_mode}")
                break

    if is_exempt:
        missing.append("CCC 免办证明或《免办强制性产品认证证明》")
        level = RiskLevel.MEDIUM
        conclusion = f"产品可能涉及 CCC 目录，但贸易方式（{trade_mode}）可申请 CCC 免办"
        recommended = (
            f"1) 确认 {trade_mode} 场景的具体免办条件\n"
            "2) 准备免办申请材料（合同、发票、运单、用途说明）\n"
            "3) 申请 CCC 免办证明或《免办强制性产品认证证明》"
        )
    else:
        missing.append("是否属于 CCC 强制认证目录")
        missing.append("CCC 证书编号（如适用）")
        level = RiskLevel.VERIFY
        conclusion = "产品可能属于 CCC 强制认证目录范围，需核实认证要求"
        recommended = (
            "1) 查询《强制性产品认证目录描述与界定表》确认是否在目录内\n"
            "2) 如属目录内，获取 CCC 证书编号\n"
            "3) 如不确属目录内，咨询认证机构确认\n"
            "4) 特殊情况可申请 CCC 免办"
        )

    return RiskResult(
        risk_id="CCC-IMPORT",
        category="CCC",
        level=level,
        title="CCC 认证需求核实",
        description="产品特征可能涉及 CCC 认证目录范围，需核实",
        triggered_by=triggered_by,
        conditions_confirmed=confirmed,
        conditions_missing=missing,
        conclusion=conclusion,
        recommended_action=recommended,
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


RULES.append(
    {
        "rule_id": "CCC-IMPORT",
        "category": "CCC",
        "condition": rule_ccc_import,
        "description": "产品可能在CCC目录 + 进口中国大陆 → 核实CCC要求",
    }
)


# ========================
# 3. 电池规则
# ========================


def rule_battery_builtin(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """
    BATTERY-BUILTIN：设备内置电池 → verify
    绝不自动断言所有证书必须，需用户提供电池参数。
    """
    if not _has_battery(product_data):
        return None

    battery = _get_battery_info(product_data)
    is_built_in = _get_bool(battery, "is_built_in") or _get_bool(
        product_data, "battery_is_built_in"
    )
    is_independent = _get_bool(battery, "is_independent") or _get_bool(
        product_data, "battery_is_independent"
    )

    triggered_by = ["product含电池"]
    confirmed = ["产品确认含电池"]
    missing = []

    if is_built_in:
        triggered_by.append("product.battery.is_built_in=True")
        confirmed.append("电池类型：内置（不可拆卸）")

        battery_type = _get_str(battery, "battery_type")
        if battery_type:
            confirmed.append(f"电池类型: {battery_type}")
        else:
            missing.append("电池类型（锂电池/镍氢/铅酸等）")

        capacity_mah = battery.get("capacity_mah")
        energy_wh = battery.get("energy_wh")
        if capacity_mah:
            confirmed.append(f"电池容量: {capacity_mah}mAh")
        if energy_wh:
            confirmed.append(f"电池能量: {energy_wh}Wh")
        if not capacity_mah and not energy_wh:
            missing.append("电池容量(mAh)或能量(Wh)")

        if battery.get("battery_material"):
            confirmed.append(f"电池材料: {battery['battery_material']}")
        else:
            missing.append("电池材料（锂离子/锂金属/镍氢等）")

        missing.append("UN38.3 检测报告（锂电池适用）")
        missing.append("危险包装证书/危包证（如适用）")

        conclusion = "设备内置锂电池，需确认电池容量及运输文件"
        level = RiskLevel.VERIFY
        recommended = (
            "1) 确认电池容量和能量参数\n"
            "2) 准备 UN38.3 检测报告（锂电池必须）\n"
            "3) 确认是否需办理危包证\n"
            "4) 外包装贴锂电池运输标签"
        )

    elif is_independent:
        triggered_by.append("product.battery.is_independent=True")
        confirmed.append("电池类型：独立（单独进口/出口）")
        level = RiskLevel.HIGH

        battery_type = _get_str(battery, "battery_type")
        if battery_type:
            confirmed.append(f"电池类型: {battery_type}")
        else:
            missing.append("电池类型（锂电池/镍氢/铅酸等）")

        capacity_mah = battery.get("capacity_mah")
        energy_wh = battery.get("energy_wh")
        if capacity_mah:
            confirmed.append(f"电池容量: {capacity_mah}mAh")
        if energy_wh:
            confirmed.append(f"电池能量: {energy_wh}Wh")
        if not capacity_mah and not energy_wh:
            missing.append("电池容量(mAh)或能量(Wh)")

        missing.append("UN38.3 检测报告")
        missing.append("MSDS（安全数据表）")
        missing.append("危险包装证书/危包证")
        missing.append("CCC 认证要求确认")

        trade_direction = _get_str(trade_data or {}, "trade_direction")
        destination = _get_str(trade_data or {}, "destination_country")
        if trade_direction:
            triggered_by.append(f"trade_direction={trade_direction}")
            confirmed.append(f"贸易方向: {trade_direction}")
        if destination:
            triggered_by.append(f"destination_country={destination}")
            confirmed.append(f"目的地: {destination}")

        conclusion = "独立进口/出口锂电池，需全套运输文件和认证"
        recommended = (
            "1) 获取 UN38.3 检测报告（必须）\n"
            "2) 准备 MSDS 和安全数据表\n"
            "3) 申请危险包装证书\n"
            "4) 确认是否需 CCC 认证（进口中国大陆）\n"
            "5) 外包装贴锂电池运输标签 Class 9"
        )

    else:
        # 检测到电池但无法区分内置/独立
        missing.append("电池安装方式（内置/独立）")
        battery_type = _get_str(battery, "battery_type")
        if battery_type:
            confirmed.append(f"电池类型: {battery_type}")
        else:
            missing.append("电池类型")

        level = RiskLevel.VERIFY
        conclusion = "检测到产品含电池，需补充电池参数以判定文件要求"
        recommended = (
            "1) 确认电池安装方式（内置/独立）\n"
            "2) 确认电池类型和容量\n"
            "3) 按需准备 UN38.3/MSDS 等文件"
        )

    return RiskResult(
        risk_id="BATTERY-BUILTIN",
        category="BATTERY",
        level=level,
        title="电池认证需求核实",
        description="产品含电池，需根据电池参数确认认证及运输文件要求",
        triggered_by=triggered_by,
        conditions_confirmed=confirmed,
        conditions_missing=missing,
        conclusion=conclusion,
        recommended_action=recommended,
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


def rule_battery_no_battery(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """BATTERY-NO-BATTERY：无电池 → not_applicable，跳过"""
    if _has_battery(product_data):
        return None

    return RiskResult(
        risk_id="BATTERY-NO-BATTERY",
        category="BATTERY",
        level=RiskLevel.NOT_APPLICABLE,
        title="不涉及电池认证",
        description="产品不含电池，不涉及电池相关认证和运输要求",
        triggered_by=[],
        conditions_confirmed=["产品确认不含电池"],
        conditions_missing=[],
        conclusion="无需电池认证和运输文件",
        recommended_action="无需处理",
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


RULES.append(
    {
        "rule_id": "BATTERY-BUILTIN",
        "category": "BATTERY",
        "condition": rule_battery_builtin,
        "description": "含电池 → 根据电池参数判定文件要求",
    }
)

RULES.append(
    {
        "rule_id": "BATTERY-NO-BATTERY",
        "category": "BATTERY",
        "condition": rule_battery_no_battery,
        "description": "无电池 → 标记为不适用",
    }
)


# ========================
# 4. 木质包装规则
# ========================


def rule_wood_packaging(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """WOOD-PACKAGING：有木质包装 → verify"""
    if not _has_wood_packaging(product_data):
        return None

    triggered_by = ["product.has_wood_packaging=True"]
    confirmed = ["产品使用木质包装"]
    missing = []

    destination = _get_str(trade_data or {}, "destination_country")
    origin = _get_str(trade_data or {}, "origin_country")

    if destination:
        triggered_by.append(f"destination_country={destination}")
        confirmed.append(f"目的地: {destination}")

    if origin:
        triggered_by.append(f"origin_country={origin}")
        confirmed.append(f"起运国/原产国: {origin}")

    missing.append("IPPC 标识（国际植物保护公约热处理/熏蒸标识）")
    missing.append("熏蒸/热处理证书（如目的地要求）")

    if _dest_is_china_mainland(destination):
        confirmed.append("进口中国大陆需符合 IPPC-15 标准")
        conclusion = "木质包装进口中国大陆，需确保符合 IPPC-15 标准和海关检疫要求"
    else:
        conclusion = "木质包装出口，需确认目的国木质包装检疫要求"

    return RiskResult(
        risk_id="WOOD-PACKAGING",
        category="WOOD_PACKAGING",
        level=RiskLevel.VERIFY,
        title="木质包装检疫要求核实",
        description="产品使用木质包装，需提供 IPPC 标识或熏蒸证书",
        triggered_by=triggered_by,
        conditions_confirmed=confirmed,
        conditions_missing=missing,
        conclusion=conclusion,
        recommended_action=(
            "1) 检查木质包装是否有 IPPC 标识（HT热处理/MB熏蒸）\n"
            "2) 获取熏蒸/热处理证书\n"
            "3) 确保木质包装无树皮、虫眼\n"
            "4) 如人造板/胶合板则可豁免"
        ),
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


def rule_wood_no_packaging(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """WOOD-NO-PACKAGING：无木质包装 → not_applicable"""
    if _has_wood_packaging(product_data):
        return None

    return RiskResult(
        risk_id="WOOD-NO-PACKAGING",
        category="WOOD_PACKAGING",
        level=RiskLevel.NOT_APPLICABLE,
        title="不涉及木质包装检疫",
        description="产品未使用木质包装，不涉及木质包装检疫要求",
        triggered_by=[],
        conditions_confirmed=["产品未使用木质包装"],
        conditions_missing=[],
        conclusion="无需木质包装检疫文件",
        recommended_action="无需处理",
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


RULES.append(
    {
        "rule_id": "WOOD-PACKAGING",
        "category": "WOOD_PACKAGING",
        "condition": rule_wood_packaging,
        "description": "有木质包装 → 核实检疫要求",
    }
)

RULES.append(
    {
        "rule_id": "WOOD-NO-PACKAGING",
        "category": "WOOD_PACKAGING",
        "condition": rule_wood_no_packaging,
        "description": "无木质包装 → 标记为不适用",
    }
)


# ========================
# 5. IPR（品牌/知识产权）规则
# ========================


def rule_ipr_brand(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """IPR-BRAND：有品牌 + 中国进出口 → verify"""
    brand = _get_str(product_data, "brand")
    if not brand:
        return None

    trade_direction = _get_str(trade_data or {}, "trade_direction")
    destination = _get_str(trade_data or {}, "destination_country")

    triggered_by = [f"product.brand={brand}"]
    confirmed = [f"品牌: {brand}"]
    missing = []

    if not trade_direction:
        missing.append("贸易方向（用于判断知识产权备案查询必要性）")
        return RiskResult(
            risk_id="IPR-BRAND",
            category="IPR",
            level=RiskLevel.VERIFY,
            title="品牌知识产权备案需核实",
            description=f"产品涉及品牌 '{brand}'，但缺少贸易方向信息，需补充业务背景",
            triggered_by=triggered_by,
            conditions_confirmed=confirmed,
            conditions_missing=missing,
            conclusion=f"品牌 {brand} 已识别，需确认贸易场景判断是否需要知识产权备案查询",
            recommended_action="补充进口/出口方向和目的地信息",
            source="rule_engine",
            verification_date=datetime.now().strftime("%Y-%m-%d"),
        )

    triggered_by.append(f"trade_direction={trade_direction}")
    confirmed.append(f"贸易方向: {trade_direction}")
    confirmed.append(f"目的地: {destination if destination else '待确认'}")

    if _dest_is_china_mainland(destination) or _dest_is_china_mainland(trade_direction):
        confirmed.append("涉及中国大陆进出口，需查询海关知识产权备案")
        missing.append("品牌是否在海关知识产权备案系统中备案")
        conclusion = (
            f"品牌 '{brand}' 涉及中国大陆进出口，需确认是否在海关知识产权备案系统中备案"
        )
        level = RiskLevel.VERIFY
        recommended = (
            f"1) 登录海关知识产权备案系统查询 '{brand}' 是否备案\n"
            "2) 如已备案，确认权利人是否授权该批次货物\n"
            "3) 保留授权证明文件\n"
            "4) 如未备案，可建议权利人办理备案"
        )
    else:
        confirmed.append("非中国大陆进出口，需确认目的国知识产权要求")
        conclusion = (
            f"品牌 '{brand}' 涉及非中国大陆进出口，需确认目的国知识产权保护要求"
        )
        level = RiskLevel.NOTICE
        recommended = (
            f"1) 查询目的国海关对 '{brand}' 的知识产权保护措施\n"
            "2) 确认是否需提供品牌授权书\n"
            "3) 保留正品来源证明"
        )

    return RiskResult(
        risk_id="IPR-BRAND",
        category="IPR",
        level=level,
        title="品牌知识产权备案核实",
        description=f"产品涉及品牌 '{brand}'，需确认海关知识产权备案情况",
        triggered_by=triggered_by,
        conditions_confirmed=confirmed,
        conditions_missing=missing,
        conclusion=conclusion,
        recommended_action=recommended,
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


RULES.append(
    {
        "rule_id": "IPR-BRAND",
        "category": "IPR",
        "condition": rule_ipr_brand,
        "description": "有品牌 + 中国进出口 → 核实知识产权备案",
    }
)


# ========================
# 6. 通用规则
# ========================


def rule_generic_wide_name(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """GENERIC-WIDE-NAME：商品名称过于宽泛 → medium"""
    name_cn = _get_str(product_data, "name_cn")
    if not _is_generic_name(name_cn):
        return None

    return RiskResult(
        risk_id="GENERIC-WIDE-NAME",
        category="GENERAL",
        level=RiskLevel.MEDIUM,
        title="商品名称过于宽泛",
        description=f"商品名称 '{name_cn}' 过于宽泛，不利海关归类审单，可能引起人工审单或退单",
        triggered_by=[f"product.name_cn={name_cn}"],
        conditions_confirmed=[f"当前名称: {name_cn}"],
        conditions_missing=["具体商品名称（应反映材质、用途、功能）"],
        conclusion="商品名称过于宽泛，建议细化以提高通关效率",
        recommended_action=(
            "1) 在名称中增加材质（如 塑料/金属/铝合金）\n"
            "2) 增加用途/功能描述\n"
            "3) 示例：将'电子产品'改为'车载蓝牙耳机用塑料外壳'\n"
            "4) 参考同类商品规范申报名称"
        ),
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


def rule_generic_missing_model(
    product_data: dict, trade_data: Optional[dict]
) -> Optional[RiskResult]:
    """GENERIC-MISSING-MODEL：无型号 → medium"""
    model = _get_str(product_data, "model")
    if model:
        return None

    return RiskResult(
        risk_id="GENERIC-MISSING-MODEL",
        category="GENERAL",
        level=RiskLevel.MEDIUM,
        title="产品型号缺失",
        description="商品未填写型号，影响海关审单及后续查验比对",
        triggered_by=["product.model为空"],
        conditions_confirmed=["产品型号字段为空"],
        conditions_missing=["产品型号（应与实物标签一致）"],
        conclusion="缺少型号信息，需补充以便海关审单和查验",
        recommended_action=(
            "1) 查看产品实物标签确认型号\n"
            "2) 如有多型号需分别申报\n"
            "3) 型号需与商业发票、装箱单一致\n"
            "4) 如确无型号（如原材料），注明'无型号'"
        ),
        source="rule_engine",
        verification_date=datetime.now().strftime("%Y-%m-%d"),
    )


RULES.append(
    {
        "rule_id": "GENERIC-WIDE-NAME",
        "category": "GENERAL",
        "condition": rule_generic_wide_name,
        "description": "商品名称为宽泛词汇 → 建议优化",
    }
)

RULES.append(
    {
        "rule_id": "GENERIC-MISSING-MODEL",
        "category": "GENERAL",
        "condition": rule_generic_missing_model,
        "description": "无型号 → 需补充",
    }
)


# ──────────────────────────────────────────────
# 主评估函数
# ──────────────────────────────────────────────


def evaluate_risks(product_data: dict, trade_data: Optional[dict] = None) -> list[dict]:
    """
    评估所有风险规则，返回风险结果列表。

    Args:
        product_data: 商品数据 dict（遵循 CustomsProduct.to_dict 格式）
        trade_data: 业务背景数据 dict（可选），包含贸易方向、目的地等

    Returns:
        风险结果 dict 列表
    """
    if trade_data is None:
        trade_data = {}

    results: list[dict] = []

    for rule in RULES:
        try:
            result = rule["condition"](product_data, trade_data)
            if result is not None:
                results.append(result.to_dict())
        except Exception as e:
            results.append(
                {
                    "risk_id": f"{rule['rule_id']}-ERROR",
                    "category": rule["category"],
                    "level": RiskLevel.NOTICE.value,
                    "title": f"风险规则执行异常: {rule['rule_id']}",
                    "description": f"执行规则 {rule['rule_id']} 时发生错误: {e}",
                    "triggered_by": [],
                    "conditions_confirmed": [],
                    "conditions_missing": [],
                    "conclusion": "规则执行异常，建议人工复核",
                    "recommended_action": "检查输入数据格式是否完整",
                    "source": "rule_engine",
                    "verification_date": datetime.now().strftime("%Y-%m-%d"),
                }
            )

    return results


def _level_sort_key(r: dict) -> int:
    """按风险等级排序的 key 函数"""
    level_str = r.get("level", RiskLevel.NOTICE.value)
    try:
        level = RiskLevel(level_str)
    except ValueError:
        level = RiskLevel.NOTICE
    return LEVEL_ORDER.get(level, 99)


def print_risk_report(risks: list[dict]) -> None:
    """
    打印风险报告，按类别分组、按等级排序。
    """
    if not risks:
        print("=" * 70)
        print("  监管风险评估报告")
        print("=" * 70)
        print("  未发现任何风险项。")
        return

    # 按类别分组
    categories: dict[str, list[dict]] = {}
    for r in risks:
        cat = r.get("category", "其他")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    print("=" * 70)
    print("  监管风险评估报告")
    print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 按类别字母排序
    for cat in sorted(categories.keys()):
        cat_risks = sorted(categories[cat], key=_level_sort_key)
        print(f"\n{'─' * 70}")
        print(f"  [{cat}]")
        print(f"{'─' * 70}")

        for r in cat_risks:
            level_str = r.get("level", "unknown")
            level_label = level_str.upper()

            # 等级着色（用不同符号标记）
            if level_str == RiskLevel.CRITICAL.value:
                marker = "🔴"  # 用文字替代 emoji 时保留视觉区分
                marker = "[CRITICAL]"
            elif level_str == RiskLevel.HIGH.value:
                marker = "[HIGH]"
            elif level_str == RiskLevel.VERIFY.value:
                marker = "[VERIFY]"
            elif level_str == RiskLevel.MEDIUM.value:
                marker = "[MEDIUM]"
            elif level_str == RiskLevel.NOTICE.value:
                marker = "[NOTICE]"
            elif level_str == RiskLevel.NOT_APPLICABLE.value:
                marker = "[N/A]"
            else:
                marker = f"[{level_label}]"

            print(f"\n  {marker} {r.get('risk_id', 'UNKNOWN')}")
            print(f"  ├─ 标题: {r.get('title', '')}")
            print(f"  ├─ 描述: {r.get('description', '')}")

            confirmed = r.get("conditions_confirmed", [])
            if confirmed:
                print("  ├─ 已确认条件:")
                for c in confirmed:
                    print(f"  │   • {c}")

            missing = r.get("conditions_missing", [])
            if missing:
                print("  ├─ 缺失信息:")
                for m in missing:
                    print(f"  │   • {m}")

            print(f"  ├─ 结论: {r.get('conclusion', '')}")
            print(f"  └─ 建议: {r.get('recommended_action', '')}")

    # 汇总统计
    print(f"\n{'=' * 70}")
    print("  风险汇总")
    print(f"{'=' * 70}")
    counts = {
        RiskLevel.CRITICAL.value: 0,
        RiskLevel.HIGH.value: 0,
        RiskLevel.VERIFY.value: 0,
        RiskLevel.MEDIUM.value: 0,
        RiskLevel.NOTICE.value: 0,
        RiskLevel.NOT_APPLICABLE.value: 0,
    }
    for r in risks:
        lv = r.get("level", RiskLevel.NOTICE.value)
        if lv in counts:
            counts[lv] += 1

    for level, count in counts.items():
        if count > 0:
            print(f"  {level.upper()}: {count} 项")

    critical_count = counts.get(RiskLevel.CRITICAL.value, 0)
    high_count = counts.get(RiskLevel.HIGH.value, 0)
    verify_count = counts.get(RiskLevel.VERIFY.value, 0)
    if critical_count + high_count + verify_count > 0:
        print(f"\n  存在 {critical_count + high_count + verify_count} 项需关注风险。")
    else:
        print("\n  未发现需关注的风险。")


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="监管风险规则引擎")
    parser.add_argument("input_file", nargs="?", help="输入商品数据文件 (JSON)")
    parser.add_argument("--output", "-o", help="输出风险报告路径")
    args = parser.parse_args()

    if args.input_file:
        # 从文件加载
        input_path = args.input_file
        if not os.path.exists(input_path):
            print(f"错误：找不到输入文件 {input_path}", file=sys.stderr)
            sys.exit(1)

        with open(input_path, "r", encoding="utf-8") as f:
            try:
                input_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"错误：JSON 解析失败 - {e}", file=sys.stderr)
                sys.exit(1)

        product_data = input_data.get("product", input_data)
        trade_data = input_data.get("trade", None)

        risks = evaluate_risks(product_data, trade_data)
        print_risk_report(risks)

        # 检查是否有需要关注的风险
        has_actionable = any(
            r.get("level")
            in (RiskLevel.CRITICAL.value, RiskLevel.HIGH.value, RiskLevel.VERIFY.value)
            for r in risks
        )

        if args.output:
            output_path = args.output
            output_data = {
                "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "product": product_data,
                "trade": trade_data,
                "risks": risks,
                "summary": {
                    "total": len(risks),
                    "critical": sum(
                        1 for r in risks if r.get("level") == RiskLevel.CRITICAL.value
                    ),
                    "high": sum(
                        1 for r in risks if r.get("level") == RiskLevel.HIGH.value
                    ),
                    "verify": sum(
                        1 for r in risks if r.get("level") == RiskLevel.VERIFY.value
                    ),
                    "medium": sum(
                        1 for r in risks if r.get("level") == RiskLevel.MEDIUM.value
                    ),
                    "notice": sum(
                        1 for r in risks if r.get("level") == RiskLevel.NOTICE.value
                    ),
                    "not_applicable": sum(
                        1
                        for r in risks
                        if r.get("level") == RiskLevel.NOT_APPLICABLE.value
                    ),
                },
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"\n风险报告已保存至: {output_path}")

        if has_actionable:
            sys.exit(1)
        sys.exit(0)

    else:
        # 无参数：运行示例数据
        print("未指定输入文件，使用示例数据运行...\n")
        _run_sample()
        sys.exit(0)


# ──────────────────────────────────────────────
# 示例数据
# ──────────────────────────────────────────────


def _run_sample() -> None:
    """运行三个示例场景"""
    print("=" * 70)
    print("  场景 1: 中国大陆进口含无线 + 电池产品")
    print("=" * 70)
    product_1 = {
        "name_cn": "智能蓝牙音箱",
        "name_en": "Smart Bluetooth Speaker",
        "brand": "SoundMax",
        "model": "SM-BT100",
        "hs_code": "8518220000",
        "usage": "家用音频播放",
        "function": "蓝牙无线连接播放音乐",
        "has_wireless": True,
        "wireless": {
            "has_wireless": True,
            "wireless_types": ["蓝牙", "Wi-Fi"],
            "module_model": "BK3266",
            "module_has_srrc": None,
            "frequency_bands": ["2.4GHz"],
        },
        "has_battery": True,
        "battery": {
            "is_built_in": True,
            "battery_type": "锂离子电池",
            "capacity_mah": 2500,
            "energy_wh": 9.25,
            "battery_material": "锂离子",
        },
    }
    trade_1 = {
        "trade_direction": "进口",
        "trade_mode": "一般贸易",
        "destination_country": "中国",
        "origin_country": "越南",
    }
    risks_1 = evaluate_risks(product_1, trade_1)
    print_risk_report(risks_1)

    # 验证关键原则：无线不应被标记为 critical
    for r in risks_1:
        if r.get("level") == RiskLevel.CRITICAL.value:
            print(
                f"\n⚠️  警告：场景1 中 {r['risk_id']} 被标记为 CRITICAL，"
                f"但含无线功能不应自动判定为 critical！"
            )

    print(f"\n\n{'=' * 70}")
    print("  场景 2: 出口香港含无线产品")
    print("=" * 70)
    product_2 = {
        "name_cn": "无线耳机",
        "name_en": "Wireless Earbuds",
        "brand": "EarFun",
        "model": "EF-TWS200",
        "hs_code": "8518300000",
        "usage": "个人音频",
        "function": "真无线蓝牙耳机",
        "has_wireless": True,
        "wireless": {
            "has_wireless": True,
            "wireless_types": ["蓝牙"],
            "module_model": "AB1562",
            "module_has_srrc": True,
            "frequency_bands": ["2.4GHz"],
        },
        "has_battery": False,
    }
    trade_2 = {
        "trade_direction": "出口",
        "trade_mode": "一般贸易",
        "destination_country": "香港",
        "origin_country": "中国",
    }
    risks_2 = evaluate_risks(product_2, trade_2)
    print_risk_report(risks_2)

    # 验证：出口香港不应触发中国大陆 SRRC 为 critical
    for r in risks_2:
        if r.get("risk_id") == "SRRC-GENERAL":
            level = r.get("level")
            if level == RiskLevel.NOTICE.value or level == RiskLevel.VERIFY.value:
                print(
                    f"\n✓ 正确：出口香港 SRRC 风险等级为 {level.upper()}，未误判为 CRITICAL"
                )
            else:
                print(
                    f"\n⚠️  注意：出口香港 SRRC 风险等级为 {level.upper()}，期望为 NOTICE 或 VERIFY"
                )

    print(f"\n\n{'=' * 70}")
    print("  场景 3: 无无线/电池/木包装产品（最小风险）")
    print("=" * 70)
    product_3 = {
        "name_cn": "铝合金手机支架",
        "name_en": "Aluminum Phone Stand",
        "brand": "StandPro",
        "model": "SP-200A",
        "hs_code": "7326909000",
        "usage": "手机配件",
        "function": "支撑手机",
        "material": "铝合金",
        "has_wireless": False,
        "has_battery": False,
    }
    trade_3 = {
        "trade_direction": "出口",
        "trade_mode": "一般贸易",
        "destination_country": "美国",
        "origin_country": "中国",
    }
    risks_3 = evaluate_risks(product_3, trade_3)
    print_risk_report(risks_3)

    print(f"\n\n{'=' * 70}")
    print("  示例运行完成。")
    print(
        "  使用方式: python regulatory_risk_engine.py <input.json> [--output report.json]"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
