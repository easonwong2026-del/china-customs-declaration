# China Customs Declaration Expert · 中国报关与商品归类专家

WorkBuddy 专家包（Agent 型，内置 `china-customs-declaration` Skill），辅助中国进出口报关全流程：HS 编码归类、规范申报要素整理、单据一致性检查与监管风险识别。

> 本专家输出属于资料整理与专业辅助建议。HS 编码为归类建议，不代表海关最终认定。

## 项目定位

本项目是一个专业的报关辅助工具包，旨在帮助报关从业者整理资料、识别风险、提高申报效率。

### 支持的范围
- HS 编码归类建议（基于归类六步法）
- 规范申报要素整理（Schema 驱动，按 HS 编码匹配）
- 商业发票/装箱单/申报要素表格生成
- 多份单据一致性比较（按商品匹配，非行号）
- 监管风险条件式判断
- 商品数据完整性校验

### 不支持的范围
- ❌ 自动确定 HS 编码（编码必须人工复核）
- ❌ 替代专业报关行或海关预裁定
- ❌ 实时海关数据查询（需通过单一窗口）
- ❌ PDF 扫描件 OCR 识别（接口预留但未实现）

## 项目结构

```
china-customs-declaration/
├── .codebuddy-plugin/plugin.json          # 专家包元数据
├── agents/
│   └── china-customs-declaration-expert.md # 专家角色定义
├── avatars/expert.png                      # 头像
├── skills/china-customs-declaration/       # 核心 Skill
│   ├── SKILL.md                            # 控制流程
│   ├── data/
│   │   ├── declaration-elements/           # 申报要素 Schema
│   │   │   ├── schema.json (注册文件)
│   │   │   ├── 8528.json (投影仪示例)
│   │   │   ├── 8518.json (扬声器示例)
│   │   │   ├── 8507.json (电池示例)
│   │   │   ├── 8504.json (电源示例)
│   │   │   └── README.md
│   │   └── source-manifest.json            # 来源清单
│   ├── references/                         # 参考知识库
│   ├── scripts/
│   │   ├── common/                         # 公共模块
│   │   │   ├── models.py                   # 数据模型
│   │   │   ├── decimal_utils.py            # Decimal 工具
│   │   │   └── field_normalizer.py         # 字段别名标准化
│   │   ├── validate_customs_data.py        # 数据校验
│   │   ├── generate_declaration_table.py   # 表格生成
│   │   ├── compare_documents.py            # 单据比较
│   │   ├── declaration_elements.py         # 申报要素整理
│   │   ├── regulatory_risk_engine.py       # 风险引擎
│   │   └── update_source_manifest.py       # 来源管理
│   ├── templates/                          # Excel 模板
│   └── tests/                              # 旧版测试
├── tests/
│   └── test_all.py                         # 综合测试（71 项）
├── CHANGELOG.md
├── pyproject.toml
├── .github/workflows/ci.yml
└── README.md
```

## 声明要素 Schema 状态说明

| 状态 | 含义 | 使用规则 |
|------|------|---------|
| official_confirmed | 官方已核实 Schema | 可在输出中标记"已确认" |
| internal_historical | 内部历史 Schema | 仅供对比参考，不得作为当前申报依据 |
| example_only | 示例 Schema | 必须标记为"示例参考，需官方核实" |
| not_found | 未找到对应 Schema | 输出"当前未加载该 HS 编码的有效申报要素定义" |

## 风险等级说明

| 等级 | 含义 | 示例 |
|------|------|------|
| critical | 有明确依据，可能导致退单/扣货 | 禁止进口商品 |
| high | 高概率适用，需核实证书 | 独立锂电池进口缺UN38.3 |
| verify | 发现触发特征，需进一步核实 | 含无线功能但未确认SRRC |
| medium | 资料缺失，可能导致补料 | 品名过于宽泛 |
| notice | 优化建议 | 型号可进一步明确 |
| not_applicable | 已有依据确认不适用 | 无木质包装不触发IPPC |

## 动态数据核实原则

所有输出必须区分静态知识和动态数据：

**静态知识**（可直接使用）：归类方法、检查规则、Schema 结构、模板格式
**动态数据**（必须标注查询时间和来源）：HS 编码、税率、监管条件、CCC 目录、SRRC 证书

动态数据输出格式：
```
[字段名] [值]
  查询来源: [来源名称] (source-manifest.json 中 source_id)
  查询日期: YYYY-MM-DD
  状态: [已确认/推断/待确认/待官方核实]
  是否需要再次核实: [是/否]
```

## 安装

**方式一（作为专家包，推荐）**：
```bash
# 将仓库目录放到 WorkBuddy 专家目录
cp -R china-customs-declaration ~/.workbuddy/plugins/marketplaces/my-experts/plugins/
# 注册专家包
python3 <expert-manager>/scripts/register_expert.py \
  ~/.workbuddy/plugins/marketplaces/my-experts/plugins/china-customs-declaration
```

**方式二（仅作为 Skill 使用）**：
```bash
cp -R skills/china-customs-declaration/ ~/.workbuddy/skills/china-customs-declaration/
```

## 使用方法

### 基本命令

```bash
# 商品数据校验
python scripts/validate_customs_data.py data.json

# 生成报关资料表格
python scripts/generate_declaration_table.py data.json output_dir xlsx

# 单据一致性比较
python scripts/compare_documents.py invoice.csv packing_list.csv

# 申报要素整理
python scripts/declaration_elements.py products.json --output elements.json

# 监管风险分析
python scripts/regulatory_risk_engine.py products.json --output risks.json

# 来源清单管理
python scripts/update_source_manifest.py --status
```

### 输入文件格式

- **JSON**: 商品数据数组，每个元素为字段字典
- **CSV**: 第一行为表头，支持常见中英文别名
- **XLSX**: 自动识别 Sheet 和表头，支持多行表头

所有支持的中英文字段别名见 `scripts/common/field_normalizer.py` 中的 FIELD_ALIASES。

### 输出文件

| 输出 | 格式 | 说明 |
|------|------|------|
| 商品资料汇总 | XLSX/CSV/JSON | 含确认状态列 |
| 商业发票 | XLSX/CSV/JSON | 标准发票格式 |
| 装箱单 | XLSX/CSV/JSON | 含重量汇总 |
| 申报要素明细 | XLSX/CSV/JSON | 含 Schema 状态 |
| 风险报告 | JSON | 6 级风险等级 |
| 比较报告 | JSON | 商品级匹配结果 |

## 示例工作流

### 示例一：投影仪归类资料整理

暂无实际案例数据。Schema 示例仅供参考。

### 示例二：回音壁多型号批次

暂无实际案例数据。Schema 示例仅供参考。

> 案例数据和示例中的编码、监管结论为示例数据，不代表当前正式结论。

## 测试

```bash
# 运行完整测试套件
python -m unittest discover -s tests -p "test_*.py" -v

# 运行回归测试
python skills/china-customs-declaration/tests/test_customs_scripts.py
```

CI 中执行：
```bash
ruff check skills/china-customs-declaration/scripts tests
ruff format --check skills/china-customs-declaration/scripts tests
```

## 专家包打包

```bash
zip -r china-customs-declaration-expert.zip . \
  -x ".git/*" ".github/*" ".gitignore" "README.md" \
  -x "__pycache__/*" "*.pyc" ".DS_Store" \
  -x "tests/*" "skills/china-customs-declaration/tests/*"
```

## 当前限制

1. 申报要素 Schema 为示例数据（example_only），非官方法定数据
2. 无法实时查询海关总署/单一窗口数据，动态内容需用户自行核实
3. 无 PDF 文本提取和 OCR 能力
4. 无法自动完成官方报关申报
5. HS 编码建议需专业报关行复核
6. 不支持加工贸易手册管理

## 后续路线图

- [ ] 接入实时海关数据查询接口
- [ ] PDF 和扫描件自动识别
- [ ] 更多 HS 品目的申报要素 Schema
- [ ] 报关单智能填制辅助
- [ ] 加工贸易核销辅助

## 免责声明

本专家所有输出均为资料整理与专业辅助建议。HS 编码属于归类建议，不代表海关最终认定；税率、监管条件与政策要求必须以申报时的官方有效规定为准。争议较大的商品应咨询专业报关行或主管海关；重大或长期重复进出口商品建议申请商品归类预裁定。最终申报责任由申报主体承担。

## 许可证

MIT
