# 更新日志

本项目的所有重要变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-09-25

### 新增：桌面化（macOS 已验证，Windows 留钩子）

- **独立桌面应用**：`python -m desktop.main` 或直接打开 `dist/SpellForge.app`；
  pywebview 展示现有页面，不引入 Electron/Tauri；窗口关闭后本机服务优雅退出、
  端口释放、无残留进程（`--smoke` 参数可自动化自检）
- **用户数据隔离**：桌面模式数据统一写入系统用户目录
  （macOS `~/Library/Application Support/SpellForge`，Windows `%APPDATA%\SpellForge`），
  程序移动、升级不丢失；源码开发模式行为不变，继续使用仓库 `data/`
- **统一路径模块** `styles/paths.py`：内置只读资源与用户可写数据严格分离；
  种子 JSON 采用「包内默认 + 首启复制 + 用户副本读写」策略，
  规范文档采用「用户重生成优先、包内兜底」
- **一次性数据迁移**：`python -m styles.migrate`（预演 / `--apply` / `--apply --force`
  先备份再导入），默认不覆盖用户目录已有数据，源文件只读不修改
- **本机接口防护**：后端只监听 `127.0.0.1` 随机端口；Host 校验防 DNS rebinding；
  写请求要求同源 Origin + 每次启动的随机访问令牌，外部网页无法触发
- **macOS 打包**：`bash scripts/build_mac.sh` 产出 onedir + windowed 的
  `dist/SpellForge.app`；放入 `desktop/assets/icon.png` 自动生成应用图标；
  包内不含 `.env`、SQLite 与私人数据
- **Windows 打包钩子**：`scripts/build_windows.bat` 与平台分支 spec 已就绪，
  **未验证**，待 Windows 环境构建后按 README 清单验收

### 修复

- 修复 `store.export_json` 缺失，导致抓取 / LLM 补全 / 场景编辑后 `styles.json`
  同步必崩（500）的问题
- 修复迁移命令重复汇报同一文件名的问题

### 测试

- 新增 `tests/`（31 个用例）：路径解析、首启种子、二次启动不覆盖、
  迁移安全、导出格式、接口防护、服务生命周期
- macOS 干净环境（独立 HOME）实测：首启建库、重启保留修改、移动 `.app`
  后数据保留、包内容安全审查通过

## [1.0.0] - 2026-09-24

首个公开版本。

### 新增

- **场景库**：抓取 openrouter.ai 图像基准 Styles 全部 21 个风格、75 个场景的官方评测提示词，
  存 SQLite 并同步 `data/styles.json`；支持搜索、画幅比例编辑、触发重新抓取
- **LLM 补全**：为每条场景推断画幅比例（aspect_ratio）、生成 4 条中文创意文案模板，
  共 300 条；支持并发、断点续跑、`--force` 重跑
- **主体库**：管理可复用主体（人物 / 产品 / 景物 / 品牌），随项目内置示例
- **《通用自然语言提示词规范》**：从官方语料提炼的九维度提示词写法规范与质量检查清单
  （`docs/通用自然语言提示词规范.md`），语料更新后一条命令重新生成
- **Prompt 生成器**：风格 + 场景 + 创意模板 + 主体 → 按规范生成中英双语提示词，
  生成历史自动保存
- **LLM 设置**：左上角 ⚙ 设置，支持多套 OpenAI 规范（chat）配置并切换当前使用，
  兼容任意 OpenAI 规范 provider；未配置时回退 `.env` / 环境变量
  （`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`）

### 数据隔离

- 共享数据（风格 / 场景 / 创意模板 / 主体）以 JSON 种子随仓库分发，克隆即用
- 私人数据（LLM 配置、生成历史）存 `data/personal.db`，已加入 `.gitignore`
