# 咒语工坊 · SpellForge

![License](https://img.shields.io/badge/license-MIT-green) ![Python](https://img.shields.io/badge/python-3.10%2B-blue)

一条「**语料 → 规范 → 模板 → 生成**」的图像提示词生产线。

从 [openrouter.ai 图像基准](https://openrouter.ai/benchmarks/media/images) 抓取 21 个风格、75 个场景的**官方评测提示词**作为语料；用 LLM 为每条场景推断画幅比例、生成创意文案模板；从语料中提炼《通用自然语言提示词规范》；最终在 Web 工坊里按「**风格 + 模板 + 主体**」锻造新的中英双语提示词。

| 场景库 | 生成器 |
|---|---|
| ![场景库](docs/screenshots/browse.png) | ![生成器](docs/screenshots/generator.png) |

| 主体库 | LLM 设置 |
|---|---|
| ![主体库](docs/screenshots/subjects.png) | ![设置](docs/screenshots/settings.png) |

## 功能

- **场景库**：浏览 21 个风格 / 75 个场景的官方提示词与创意模板，搜索过滤、编辑画幅比例与文案、一键重新抓取最新数据
- **主体库**：管理可复用主体（人物 / 产品 / 景物 / 品牌），生成时直接选用，也可随时「自定义」手动输入
- **Prompt 生成器**：LLM 严格按《规范》生成提示词——主体外形具象化写入、动作道具适配主体身份、身份一致与负面约束收尾；输出中英双语 + 画幅建议，历史可回看
- **《通用自然语言提示词规范》**：五条总则、提示词骨架、九大维度写法、六族风格适配、画幅指引、中文模板句式与 10 条质量检查清单（[在线阅读](docs/通用自然语言提示词规范.md)）
- **LLM 设置**：多套 OpenAI 规范（chat）配置，一键切换使用；兼容任意 OpenAI 规范 provider（OpenRouter / DeepSeek 官方 / 各类中转等）

## 快速开始

```bash
git clone https://github.com/zwy/spellforge.git
cd spellforge
pip install -r requirements.txt

# 配置 LLM（也可启动后在页面左上角 ⚙ 设置里配置）
cp .env.example .env        # 填入你的 API Key

python -m web.app           # 打开 http://127.0.0.1:8765
```

> 首次运行会自动从 `data/*.json` 种子数据建库，无需任何额外步骤。
> 生成提示词需要配置任意 OpenAI 规范 API（默认演示用 OpenRouter）。

### 命令行

```bash
python -m styles.scrape     # 重新抓取最新官方数据
python -m styles.enrich     # LLM 补全比例与创意模板（自动跳过已补全）
python -m styles.spec       # 重新生成《通用自然语言提示词规范》
```

## 数据说明

| 文件 | 是否入库 | 内容 |
|---|---|---|
| `data/styles.json` | ✅ 公开 | 21 风格 / 75 场景官方提示词 + 画幅 + 创意模板 |
| `data/creative_templates.json` | ✅ 公开 | 创意模板数据集（300 条，用户选择用） |
| `data/spec_vocab.json` | ✅ 公开 | 规范词汇库（LLM 提取缓存） |
| `data/subjects.json` | ✅ 公开 | 内置示例主体 |
| `data/app.db` | ❌ 派生 | 本地工作库，首次运行从种子 JSON 自动建库 |
| `data/personal.db` | ❌ 私密 | LLM 配置（含 API Key）与生成历史 |

## 项目结构

```
styles/       Python 包：schema / 抓取 / 解析 / 存储 / LLM 补全 / 规范生成 / 生成器
web/          FastAPI + 单页管理端（场景库 / 主体库 / 生成器 / 设置）
data/         JSON 种子数据（公开）+ 本地 db（gitignore）
docs/         规范文档与截图
```

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 致谢与说明

- 语料来自 [OpenRouter](https://openrouter.ai) 公开的图像基准页面，版权归 OpenRouter 所有，本项目仅作学习研究用途
- 生成提示词的质量取决于你配置的 LLM；默认模型 `deepseek/deepseek-v4.1-flash`
- 规范是纯语言层面的，不绑定任何特定图像模型
