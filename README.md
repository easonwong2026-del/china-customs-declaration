# China Customs Declaration Expert · 中国报关与商品归类专家

WorkBuddy 专家包（Agent 型，内置 `china-customs-declaration` Skill），辅助中国进出口报关全流程：HS 编码归类、规范申报要素整理、单据一致性检查与监管风险识别。

> 本专家输出属于资料整理与专业辅助建议。HS 编码为归类建议，不代表海关最终认定。

## 类型

- **Agent 型专家**（单角色），内置 Skill：`china-customs-declaration`
- 分类：`11-SecurityCompliance`（合规审查 / 监管风险）

## 核心能力

1. **HS 编码归类**：基于归类六步法给出带置信度（高 / 中 / 低）的建议编码，附归类逻辑、主要依据与候选编码排除理由。
2. **规范申报要素整理**：按当前有效申报要素字段与顺序，分别输出"粘贴版"（分号分隔）与"明细版"（含信息来源与状态）。
3. **报关单据检查与生成**：对发票 / 装箱单 / 申报要素做跨单据一致性比对、计算校验，并套用标准模板生成资料。
4. **监管风险识别**：对 CCC、SRRC、进口许可证、贸易救济、出口管制等动态监管项分级（严重 / 中等 / 提醒）标注风险与修改建议。

## 重点支持商品

投影仪、音响、回音壁 / 条形音箱、低音炮、锂电池、显示器、电视、电源适配器、遥控器、无线通信模块等电子类；以及材料 / 零部件、机械类商品。

## 2026-07-30 更新摘要

- 新增**案例五**：三星回音壁多型号批次 + 无线后置扬声器套件（8518.22 vs 8518.29 辨析）
- 回音壁归类补充：无线后置套件双候选、多功能不归 8519 / 8517 / 8521、同型号分票按货号聚合
- 新增扬声器（8518.22 / 8518.29）申报要素**粘贴版示例**
- 新增「回音壁 / 家用音响专项风险」排查链：SRRC → CCC → IPPC → 品牌授权 → 电池
- 修正 references 数量描述（13 → 10 篇）
- 专家包结构升级为标准 WorkBuddy 专家包（plugin.json + agents + skills/ + avatars）

## 项目结构

```
china-customs-declaration/
├── .codebuddy-plugin/plugin.json          # 专家包元数据
├── agents/
│   └── china-customs-declaration-expert.md # 专家角色定义
├── avatars/expert.png                      # 头像
├── skills/china-customs-declaration/       # 核心 Skill
│   ├── SKILL.md
│   ├── references/                         # 10 篇参考知识库
│   ├── scripts/                            # 4 个 Python 工具
│   ├── templates/                          # 4 份 Excel 模板
│   └── tests/                              # 自动化测试
├── pyproject.toml                          # ruff 配置
├── .github/workflows/ci.yml                # CI（test / lint / build）
└── README.md
```

## 安装

**方式一（作为专家包，推荐）**：将仓库目录放到 WorkBuddy 专家目录并注册：

```bash
cp -R china-customs-declaration ~/.workbuddy/plugins/marketplaces/my-experts/plugins/
python3 <expert-manager>/scripts/register_expert.py \
  ~/.workbuddy/plugins/marketplaces/my-experts/plugins/china-customs-declaration
```

**方式二（仅作为 Skill 使用）**：将 `skills/china-customs-declaration/` 解压到 `~/.workbuddy/skills/`。

## 使用方法

在 WorkBuddy 对话中直接提出报关需求：

- "帮我查这个投影仪的 HS 编码"
- "整理这批商品的申报要素"
- "检查发票和装箱单是否一致"
- "这批电子产品有什么监管风险"

## 免责声明

本专家所有输出均为资料整理与专业辅助建议。HS 编码属于归类建议，不代表海关最终认定；税率、监管条件与政策要求必须以申报时的官方有效规定为准。争议较大的商品应咨询专业报关行或主管海关；重大或长期重复进出口商品建议申请商品归类预裁定。最终申报责任由申报主体承担。

## 许可证

MIT
