"""
统一商品数据模型与业务背景模型

使用 dataclass + TypedDict 提供类型安全的数据结构。
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional


class Confidence(str, Enum):
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class VerificationStatus(str, Enum):
    CONFIRMED = "已确认"
    INFERRED = "推断"
    PENDING = "待确认"
    NEEDS_OFFICIAL = "待官方核实"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    VERIFY = "verify"
    MEDIUM = "medium"
    NOTICE = "notice"
    NOT_APPLICABLE = "not_applicable"


class TradeDirection(str, Enum):
    IMPORT = "进口"
    EXPORT = "出口"


class TradeMode(str, Enum):
    GENERAL = "一般贸易"
    SAMPLE = "样品"
    GIFT = "赠品"
    REPAIR = "维修"
    RETURN = "退运"
    TEMPORARY = "暂时进出口"
    PROCESSING = "加工贸易"
    CROSS_BORDER = "跨境电商"
    OTHER = "其他监管方式"


class SchemaStatus(str, Enum):
    OFFICIAL_CONFIRMED = "official_confirmed"
    INTERNAL_HISTORICAL = "internal_historical"
    EXAMPLE_ONLY = "example_only"
    NOT_FOUND = "not_found"


@dataclass
class BatteryParams:
    """电池参数"""

    battery_type: str = ""
    capacity_mah: Optional[Decimal] = None
    energy_wh: Optional[Decimal] = None
    is_built_in: bool = False
    is_independent: bool = False
    cell_count: Optional[int] = None
    battery_material: str = ""


@dataclass
class WirelessParams:
    """无线参数"""

    has_wireless: bool = False
    wireless_types: list[str] = field(default_factory=list)
    module_model: str = ""
    module_has_srrc: bool = False
    frequency_bands: list[str] = field(default_factory=list)


@dataclass
class CustomsProduct:
    """统一商品数据模型"""

    # 基本信息
    name_cn: str = ""
    name_en: str = ""
    brand: str = ""
    model: str = ""
    sku: str = ""

    # HS编码
    hs_code: str = ""
    hs_confidence: str = ""
    hs_classification_basis: str = ""

    # 产品属性
    usage: str = ""
    function: str = ""
    working_principle: str = ""
    material: str = ""
    composition: str = ""
    tech_params: str = ""
    is_complete_unit: bool = True
    is_part: bool = False
    is_accessory: bool = False

    # 无线和电池
    wireless: WirelessParams = field(default_factory=WirelessParams)
    battery: BatteryParams = field(default_factory=BatteryParams)

    # 数量和金额 (Decimal)
    quantity: Optional[Decimal] = None
    declare_unit: str = ""
    legal_first_unit: str = ""
    legal_second_unit: str = ""
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    currency: str = ""

    # 产地和贸易
    origin_country: str = ""
    trade_country: str = ""
    departure_country: str = ""
    destination_country: str = ""

    # 重量和包装
    gross_weight: Optional[Decimal] = None
    net_weight: Optional[Decimal] = None
    piece_count: Optional[int] = None
    package_type: str = ""
    case_no: str = ""
    pallet_no: str = ""

    # 元数据
    source_info: str = ""
    verification_status: VerificationStatus = VerificationStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        result = {}
        for k, v in asdict(self).items():
            if isinstance(v, Enum):
                result[k] = v.value
            elif isinstance(v, Decimal):
                result[k] = str(v)
            elif isinstance(v, list) and v and isinstance(v[0], Enum):
                result[k] = [i.value for i in v]
            else:
                result[k] = v
        return result


@dataclass
class TradeBackground:
    """业务背景模型"""

    trade_direction: TradeDirection = TradeDirection.IMPORT
    trade_mode: TradeMode = TradeMode.GENERAL
    domestic_consignor: str = ""
    foreign_consignor: str = ""
    consumer_user: str = ""
    declare_unit: str = ""

    # 税收和运输
    tax_nature: str = ""
    transport_mode: str = ""
    trade_terms: str = ""
    currency: str = ""
    contract_no: str = ""

    # 运费/保费/杂费 (Decimal)
    freight: Optional[Decimal] = None
    insurance: Optional[Decimal] = None
    miscellaneous: Optional[Decimal] = None

    # 地点
    departure_country: str = ""
    trade_country: str = ""
    origin_country: str = ""
    destination_country: str = ""
    domestic_destination: str = ""
    domestic_origin: str = ""
    entry_port: str = ""
    declare_customs: str = ""

    # 随附单证
    attached_documents: list[str] = field(default_factory=list)
    license_info: list[str] = field(default_factory=list)

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
