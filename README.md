# 图文知行 · Visual Book Skills

把书中的文字、图表和案例整理成有来源依据、可反复调用的 Agent Skills。

[English](./README.en.md) · [技能入口](./SKILL.md) · [图文阅读流程](./methodology/08-visual-reading.md) · [MIT License](./LICENSE)

## 这个项目做什么

读懂方法，往往需要同时看正文、图例和作者对案例的解释。图文知行把这些材料关联起来，再整理为输入、步骤、适用条件、反例和输出要求，供 AI 在后续任务中按需调用。

它是一个面向 Agent 的阅读与技能构建工作流。模型负责理解和核查内容，Python 工具负责图页准备、资源打包、静态校验与版本管理。

适合图表密集的技术书、操作手册、课程讲义，也支持文字材料和已经取得的字幕、转写稿。Brooks 价格行为书是图文阅读流程的设计场景之一。

## 核心能力

| 能力 | 实际作用 |
|---|---|
| 图页准备 | 渲染选定 PDF 页，保留完整页面，并按需裁切局部 |
| 图文对应 | 关联图号、PDF 页序、书本页码及解释该图的正文 |
| 证据核查 | 分别记录图中事实、作者解释、模型推断与未解决的问题 |
| 方法构建 | 提取触发场景、必要输入、执行步骤、边界和完成标准 |
| 可携带产物 | 将核查记录与 PNG/JPEG/WebP 图片随生成的 skill 一起保存 |
| 更新与恢复 | 图片沿用文件哈希、手改检测、快照和回滚机制 |

局部图始终与完整图配合使用。对于时序图表，流程要求区分事后复盘与当时判断，后者需要隐藏未来走势及透露答案的标注。

## 安装

需要支持本地 Agent Skills、文件读写和 Python 命令的宿主。图文任务还需要宿主能够实际打开图片。

将本仓库的最新源码放入宿主支持的技能目录，目录名使用 `visual-book-skills`，保留完整文件结构：

```text
visual-book-skills/
├── SKILL.md
├── methodology/
├── extractors/
├── templates/
├── scripts/
└── schemas/
```

例如，在你选定的技能目录中运行：

```bash
git clone https://github.com/savagealexander/visual-book-skills.git visual-book-skills
cd visual-book-skills
python -m pip install pyyaml
python scripts/cangjie.py doctor
```

图文任务另需：

```bash
python -m pip install Pillow pypdf
```

还需安装 Poppler，让 `pdfinfo` 和 `pdftoppm` 出现在 PATH 中。页内文字优先用 `pdftotext`，缺失时使用 `pypdf`。两者都不可用时，图页仍可渲染，但清单会明确标记文字提取不可用。

历史命令 `scripts/cangjie.py`、`.cangjie/` 数据目录及相关 schema 字段继续保留，以兼容继承的工具链。项目和技能入口的新名称是 `visual-book-skills`。

安装后按宿主的方式重新加载技能。旧的上游安装和历史发行包不会自动获得本项目的增强；同时保留两个同用途入口可能造成调用混淆。

## 怎么使用

安装并加载技能后，向 Agent 提出具体要求，例如：

> 使用 visual-book-skills 阅读这本书。先处理第一章，结合原图、图注和相关正文，提炼可应用的方法。每条方法保留出处、适用条件、反例和待核查问题。

图文流程会：

1. 确认来源、阅读范围和使用目的。
2. 建立关键图页及相关正文的对应关系。
3. 实际打开完整图和必要的局部图，完成图文核查。
4. 把有充分依据的方法构造成能力卡。
5. 用实际任务及反例验证，再编译为可安装的 skill。

一个生成后的 skill 可以接收类似任务：“用书中的方法检查这个案例，列出支持证据、反对证据和缺失信息。”具体分析能力取决于原书内容、生成质量、底层模型与验收结果。

### 单独准备 PDF 图页

以下命令只准备材料，不会自动完成整书阅读或生成方法：

```bash
python scripts/cangjie.py render-pages --pdf "/path/book.pdf" --pages 18-20 --source-id src-book --out "/path/new-page-directory"
```

`--pages` 使用从 1 开始的 PDF 文件页序。它可能不同于印在纸面上的书本页码，后者需要人工核实。

先查看完整页，再按实际位置裁切：

```bash
python scripts/cangjie.py render-pages --pdf "/path/book.pdf" --pages 18 --source-id src-book --max-edge 4800 --crop "0.08,0.12,0.94,0.70" --out "/path/new-detail-directory"
```

裁切坐标相对页面左上角，格式为 `x0,y0,x1,y1`，取值 0..1；示例坐标需要按实际页面调整。输出目录必须是新目录，完整页面始终保留。

输出含完整 PNG、可选局部 PNG、提取文字和来源清单。所有页面初始状态均为 `unreviewed`，实际看图与正文核查完成后才能登记已核查证据。

## 会生成什么

阅读工作区会保留整书概览、候选方法、核查依据、术语、覆盖审计和待核查清单。通过核查的方法以 Capability Bundle 保存，再编译成：

- **single**：一个技能入口，按任务加载内部能力卡，适合围绕一本书使用。
- **pack**：一个来源路由入口加少量独立技能，适合接入多个工作流。

依赖图例的能力可以携带完整图、局部图、来源定位和图文核查记录。只打包明确声明的资源，避免默认复制整本书。

[能力卡构造](./methodology/04-stage2-ria-plus.md) · [图文证据记录模板](./templates/FIGURE_EVIDENCE.md.template) · [编译与交付](./methodology/07-stage5-deliver.md)

## 当前边界与验证范围

- 页面渲染、文本提取和资源校验都是确定性工具操作；视觉理解仍由模型或阅读者完成。
- 脚本不提供自动 OCR、自动图号识别或完整的图文语义核查。
- `reviewed` 是完成核查后的记录状态，编译成功本身不证明理解正确。
- 关键图形模糊、图文矛盾或条件缺失时，记录为待核查，不能补造方法。
- 图片支持静态 PNG/JPEG/WebP，单张最多 25 MiB、40MP；其他二进制资源尚不支持。
- 当前增量 `update --add` 仅处理文本；图片变更需在 Bundle 中更新、重新核查并编译。

图文增强提交时，本地 40 项测试通过，1 项因 Windows 符号链接权限跳过。验证覆盖渲染、裁切、图像完整性、各类输出、图片补丁与回滚，并实际查看了一张 Brooks 原书图例。这些结果不等于全书理解、新图分析准确率或交易效果已获验证。

开发检查：

```bash
python -m pip install pyyaml Pillow pypdf jsonschema
python -m unittest discover -s tests -v
```

渲染集成测试需要 Poppler；缺少相关依赖时会跳过对应测试。

## 项目来源与许可

本项目由 [savagealexander](https://github.com/savagealexander) 维护，基于 [kangarooking/cangjie-skill](https://github.com/kangarooking/cangjie-skill) 开发。

原项目提供方法提取、验证、能力卡和编译工具链；本分支增加图文联合阅读流程、PDF 图页准备、图片资源支持及相关测试，并使用独立名称和说明。继承的历史资料、示例与网站代码不表示其内容已按本分支流程重新验证。

代码及适用的项目文档沿用 [MIT License](./LICENSE)，保留原许可声明。书籍、课程及图片的权利属于各自权利人；工具许可证不会改变来源材料的使用和分发权限。
