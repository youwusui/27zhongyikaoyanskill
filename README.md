# 27中医307考研学霸笔记知识点简介

> 把 2027 中医 307 考研《27学霸笔记》从扫描 PDF 变成一个可检索、可出题、可批改、可溯源的 Agent Skill 知识库。

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-111827?style=for-the-badge)](./skills/kaoyan-xueba-27-notes/SKILL.md)
[![OCR Indexed](https://img.shields.io/badge/OCR-768%2F768%20pages-16a34a?style=for-the-badge)](./skills/kaoyan-xueba-27-notes/references/ocr-status.md)
[![Exam Papers](https://img.shields.io/badge/Exam%20Papers-1991--2026-7c3aed?style=for-the-badge)](./skills/kaoyan-xueba-27-notes/references/exam-papers-status.md)
[![SQLite FTS](https://img.shields.io/badge/Search-SQLite%20FTS-2563eb?style=for-the-badge)](./skills/kaoyan-xueba-27-notes/references/xueba-notes.sqlite)
[![All Agents](https://img.shields.io/badge/Agents-Compatible-f97316?style=for-the-badge)](./skills/kaoyan-xueba-27-notes/agents/openai.yaml)

这是一个面向 **中医 307 考研复习** 的本地资料库 Skill。它不是一堆散乱 OCR 文本，而是一套已经打包好的、Agent 可调用的知识点检索与训练系统：扫描页经过 OCR，知识点进入 SQLite 全文检索，目录与页码被映射，章节索引可辅助定位，脚本可直接输出证据链。

现在它也接入了 **1991-2026 年中医综合历年真题资料**：做章节训练时，Agent 会先检索同知识点真题，优先拿真题考你，再补自编题；批改时能把真题来源、年份、标准答案/解析和 2027 学霸笔记知识点解析串起来。老题不是沉睡在 PDF 里的灰尘，是可以被召唤出来揍你的那种复习资产。

如果普通笔记是“我好像在哪看过”，这个 Skill 的目标是：“在《中医基础理论》第几页，原文怎么说，能不能立刻给我出题并等我作答后批改。”

## 亮点

- **全量 OCR 入库**：6 本扫描 PDF，768 页记录，767 页有效 OCR 文本，唯一空页已确认是《中医基础理论》PDF 第 2 页空白页。
- **一键速查知识点**：通过 SQLite FTS、OCR JSONL、TXT 导出、目录索引和 section index 快速定位概念、章节、页码与原文证据。
- **考研级出题训练**：支持按学科、章节、概念范围出 A 型题 / X 型题；默认不直接给答案，等学习者作答后再批改。
- **真题优先组卷**：指定知识点出题时，先检索同知识点历年真题，优先选真题，再补自编题；真题会标注年份，例如 `【真题：2021年】`。
- **近五年真题保护**：出题前会询问是否排除近 5 年真题，理由是把最新试卷留给最后整卷练习，方便检验复习提升。
- **完整解析与溯源**：批改时要求给出完整解析，并标明书名、PDF 页码、相关 OCR 原文或忠实转述。
- **双轨答案策略**：2007 年及以后有标准答案/解析的真题优先按题库标准答案批改；1991-2006 年无现成答案的真题，将依据 2027 学霸笔记证据生成答案并标注置信度。
- **跨科知识联动**：覆盖中基、中诊、中药、方剂、中内、针灸、人文，可用于跨科对比、概念串联和高频考点复盘。
- **所有 Agent 通用**：采用 Codex-style Skill 结构，核心知识、脚本和引用资产都在仓库内，任何能读取本地 Skill 的 Agent 都可以使用。
- **可维护可扩展**：保留 OCR、索引重建、压缩输出、后台 OCR 等脚本，后续补资料、重跑 OCR、刷新索引都不需要从零开始。

## 覆盖资料

| 科目 | 页数 | 状态 |
| --- | ---: | --- |
| 方剂学 | 160 | OCR 完成 |
| 针灸与人文 | 135 | OCR 完成 |
| 中药学 | 89 | OCR 完成 |
| 中医基础理论 | 112 | OCR 完成，PDF 第 2 页为空白页 |
| 中医内科学 | 162 | OCR 完成 |
| 中医诊断学 | 110 | OCR 完成 |

历年真题覆盖：

| 资料 | 范围 | 状态 |
| --- | --- | --- |
| 历年中医综合真题 | 1991-2026 | 已导入 SQLite FTS、JSONL 页记录和 TXT 文本 |
| 1991-2006 合并真题 | 16 年，题目级切分 2436 条 | 源文件无标准答案；后续依据 2027 学霸笔记生成答案、证据和置信度 |
| 2007 年及以后真题/解析 | 2007-2026 | 有答案/解析的题优先按题库标准答案与原解析批改，再补学霸笔记综合解析 |

## 能做什么

### 速查知识点

想查“舌诊”“医疗事故”“麻黄”“阴阳互根互用”等关键词时，Agent 会优先走 SQLite 全文检索，再结合章节索引与目录定位，输出页码和证据片段。

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\answer_lookup.py --query "舌诊" --limit 6
```

如果 Windows 终端把中文显示打花，可以用 Unicode escape：

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\answer_lookup.py --query-escape "\u820c\u8bca" --limit 6
```

### 出题并批改

你可以这样问 Agent：

```text
使用 $kaoyan-xueba-27-notes，根据《中医基础理论》精气学说及其以前内容，出 20 道考研难度选择题。先不要给答案，等我作答后批改。
```

Skill 规则已经写明：出题时不直接给答案；你提交答案后，Agent 再逐题批改，给完整解析，并附书籍位置和原文依据。

现在的出题流程更像一个真题教练：

- 先问你要不要排除近 5 年真题，保护最新试卷作为后期整卷检测材料。
- 再检索历年真题库，优先抽取同知识点真题，并在题目上标注年份。
- 如果真题数量不够，再按学霸笔记自编考研难度题。
- 批改真题时，有题库答案解析就优先用题库解析；同时补一份来自 2027 学霸笔记的综合知识点解析。
- 1991-2006 年真题没有现成答案，后续会依据学霸笔记证据生成答案；证据不足的题会标注不确定，不硬猜。

### 原文溯源

适合用来回答这类问题：

- “这句话在书里哪一页？”
- “某概念是在目录哪个章节下？”
- “这个知识点能不能按考研选项形式考我？”
- “我错的题，能不能指出书上原文怎么写？”

## 仓库结构

```text
skills/kaoyan-xueba-27-notes/
├── SKILL.md                     # Skill 触发规则、检索流程、出题批改规则
├── agents/openai.yaml           # 展示名、默认 prompt、隐式触发策略
├── references/
│   ├── xueba-notes.sqlite       # SQLite + FTS 主检索库
│   ├── ocr-pages.jsonl          # 页级 OCR 记录
│   ├── ocr-text/                # 每本书的 TXT 导出
│   ├── toc-index.csv            # 总目录索引
│   ├── section-index.csv        # OCR 派生章节/标题索引
│   ├── page-map.json            # 总页码与拆分 PDF 页码映射
│   ├── ocr-status.md            # OCR 覆盖与维护记录
│   ├── exam-papers-status.md    # 真题导入、OCR 和旧题切分状态
│   └── exam-papers/             # 1991-2026 真题检索库、页记录、TXT 和旧题 JSONL
└── scripts/
    ├── answer_lookup.py         # 推荐入口：页命中 + 章节命中 + TOC 路由
    ├── search_db.py             # 数据库检索
    ├── search_toc.py            # 目录检索
    ├── ocr_progress.py          # OCR 进度检查
    ├── compact_ocr_outputs.py   # OCR 输出压缩/去重
    ├── build_section_index.py   # section 索引重建
    ├── build_exam_papers.py     # 历年真题导入与 OCR fallback
    ├── search_exam_papers.py    # 历年真题检索
    └── extract_legacy_questions.py # 1991-2006 旧题题目级切分
```

## 安装到 Codex Skill

把本仓库中的 skill 目录复制或链接到你的 Codex skills 目录即可。示例：

```powershell
Copy-Item -Recurse .\skills\kaoyan-xueba-27-notes "$env:USERPROFILE\.codex\skills\kaoyan-xueba-27-notes"
```

然后在对话里显式调用：

```text
使用 $kaoyan-xueba-27-notes 查一下“阴阳互根互用”，给出出处和原文依据。
```

## 推荐使用方式

- **快速查漏**：输入一个概念，让 Agent 返回出处、页码、核心表述和易错点。
- **章节刷题**：指定某章或某概念范围，让 Agent 出题，不给答案，等你作答后批改。
- **真题混编**：指定某知识点，让 Agent 先抽同知识点真题并标年份，再补自编题。
- **近年保留**：训练阶段排除近 5 年真题，冲刺阶段再释放出来做整卷检测。
- **错题回炉**：把错题答案发给 Agent，让它反查书中原文并解释为什么错。
- **考点压缩**：让 Agent 根据页面证据把一节内容压缩成“高频问法 + 易混点 + 记忆钩子”。
- **跨科对比**：例如把中基的“精气神”与中诊/中内相关证候联系起来，做辨析训练。

## 注意

- 本仓库是本地学习资料 Skill，不等同于官方教材或考试答案。
- OCR 文本可能存在少量识别误差；严肃引用时应结合 PDF 原页核对。
- 原始扫描 PDF 和 OCR 缓存未纳入仓库；仓库保留的是 Skill、索引、OCR 文本与检索数据库。
- 出题批改逻辑以 `SKILL.md` 为准：默认先出题，等作答后再给答案、解析和出处。
- 1991-2006 年真题当前只有题干切分，没有官方标准答案；答案生成必须依据 2027 学霸笔记证据逐题完成。
- 以后更新 `SKILL.md` 的能力、流程或资料覆盖时，必须同步更新本 `README.md`，让仓库介绍和实际 skill 行为保持一致。

## 赞助支持

如果你觉得这个 Skill 有用的话，不妨支持一下。你的支持会让我更有动力继续补答案、修 OCR、扩展真题解析和优化复习工作流。

<p align="center">
  <img src="./assets/wechat-pay.png" alt="微信支付赞助二维码" width="360" />
</p>

## 致谢

特别感谢 [JuneYaooo/lineage-skill](https://github.com/JuneYaooo/lineage-skill) 这个 TCM 相关开源项目带来的启发：它证明了中医资料不必只停留在“能搜到文本”的层面，而可以被组织成 Agent 能理解、能检索、能引用、能训练的知识系统。本项目延续这种思路，把 307 中医考研笔记做成更偏复习实战的 Skill：有 OCR，有索引，有证据链，也有出题批改的闭环。

## 一句话

这是把“厚厚一摞扫描版中医考研笔记”压进 Agent 脑子旁边的一套检索引擎：能查、能问、能考、能批改，还能把每个判断拉回书上的具体页码。复习不再靠玄学翻页，开始靠证据链推进。
