# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-07-30

### Added
- **申报要素 Schema 系统**：新增 `data/declaration-elements/` 目录，包含 schema.json 注册文件和按 HS 编码前缀组织的示例 Schema（8528/8518/8507/8504）
- **申报要素整理脚本**（`declaration_elements.py`）：支持 HS 编码逐级匹配（10位→8位→6位→4位→兜底），Schema 状态区分（official_confirmed / internal_historical / example_only / not_found），输出粘贴版和明细版
- **条件式风险引擎**（`regulatory_risk_engine.py`）：基于业务条件（贸易方向、目的地、贸易方式、产品特征）进行风险判断，6 级风险等级，区分含无线的仅核实 vs 违规
- **统一商品数据模型**（`scripts/common/models.py`）：dataclass 定义 CustomsProduct、TradeBackground 等类型
- **Decimal 工具模块**（`scripts/common/decimal_utils.py`）：所有金额/数量/重量统一使用 Decimal 计算
- **字段别名标准化模块**（`scripts/common/field_normalizer.py`）：支持常见中英文字段别名自动映射
- **来源清单**（`data/source-manifest.json`）：12 个数据来源的结构化记录，含查询日期和动态标识
- **综合测试套件**（`tests/test_all.py`）：71 个测试覆盖 Decimal、字段标准化、申报要素、单据比较、风险引擎、来源清单、回归和包验证
- **CHANGELOG.md**

### Changed
- **单据比较脚本**（`compare_documents.py`）：重构为按商品键匹配（SKU → 品牌+型号+HS → 型号+HS → 品名+型号 → 模糊），支持多行聚合和乱序比较，使用 Decimal 计算
- **数据校验脚本**（`validate_customs_data.py`）：所有数值计算改为 Decimal，移除 float
- **资料生成脚本**（`generate_declaration_table.py`）：集成申报要素 Schema 系统和风险引擎，新增 XLSX 多 Sheet 读取，所有计算使用 Decimal
- **SKILL.md**：精简为控制流程文档，减少与 agent 文件的重复
- **CI 流程**（`.github/workflows/ci.yml`）：新增测试发现、source manifest 验证、包结构验证 jobs
- **插件版本**：从 1.0.0 升级至 1.1.0
- `README.md`：更新结构和文档

### Fixed
- 申报要素不再对所有 HS 使用同一固定模板字段
- 未知 HS 编码不会伪造法定申报要素
- 单据比较不再按行号机械比较
- "含无线"不再直接判定严重违规风险
- "含电池"不再自动断言全部认证文件均必需
- 金额计算不再使用 float，消除浮点误差

### Compatibility

- **向后兼容**：所有旧 CLI 参数保持不变
- **新增参数**：`declaration_elements.py` 新增 `--output` 和 `--format`；`compare_documents.py` 新增 `--output`；`generate_declaration_table.py` 新增 `--format`
- **输出变化**：风险等级从三级（严重/中等/提醒）扩展为六级（critical/high/verify/medium/notice/not_applicable）；申报要素输出新增 Schema 状态信息
