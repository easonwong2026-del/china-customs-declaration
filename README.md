# china-customs-declaration

中国报关与商品归类助手 — WorkBuddy Skill

协助处理中国海关进出口申报的专业 Skill，支持商品 HS 编码归类建议、规范申报要素整理、商业发票/装箱单检查与生成、监管合规风险识别。

## 功能

- 商品 HS 编码归类建议（按 2026 年税则）
- 规范申报要素整理（含粘贴版和明细版）
- 商业发票与装箱单检查/生成
- 合同、发票、箱单、申报资料一致性检查
- 监管条件与检验检疫风险提示
- 中文/英文品名规范化
- 批量商品 Excel 标准化输出
- 商品归类预裁定资料准备
- 单据缺失项检查与风险分级

## 重点支持商品

投影仪、音响、回音壁、低音炮、锂电池、显示器、电视、电源适配器、遥控器、无线通信模块等电子产品。

## 安装

将 `skill.zip` 解压到 WorkBuddy 的 skills 目录：

```bash
unzip skill.zip -d ~/.workbuddy/skills/
```

## 使用方法

在 WorkBuddy 对话中直接提出报关相关需求：

- "帮我查这个投影仪的 HS 编码"
- "整理这批商品的申报要素"
- "检查发票和装箱单是否一致"
- "这批电子产品有什么监管风险"

## 项目结构

```
china-customs-declaration/
├── SKILL.md                         # 主控制文件
├── references/                      # 参考知识库
│   ├── hs-classification-workflow.md
│   ├── declaration-elements.md
│   ├── customs-documents.md
│   ├── electronics.md
│   ├── machinery.md
│   ├── materials-and-components.md
│   ├── special-regulatory-risks.md
│   ├── official-sources.md
│   ├── dynamic-verification.md
│   └── case-handling.md
├── scripts/                         # Python 工具脚本
│   ├── validate_customs_data.py
│   ├── generate_declaration_table.py
│   ├── compare_documents.py
│   └── update_source_manifest.py
├── assets/                          # Excel 模板
│   ├── customs-product-template.xlsx
│   ├── commercial-invoice-template.xlsx
│   ├── packing-list-template.xlsx
│   └── declaration-elements-template.xlsx
└── tests/                           # 自动化测试
    └── test_customs_scripts.py
```

## 免责声明

本 Skill 输出为资料整理和专业辅助建议。HS 编码属于归类建议，不代表海关最终认定。最终申报责任由申报主体承担。

## 许可证

MIT
