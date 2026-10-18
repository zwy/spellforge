# SpellForge · Agent 工作说明

图像提示词生产线：语料（openrouter 图像基准）→ 规范 → 模板 → 生成。
Web 端 FastAPI + 无构建原生前端；另有 pywebview 桌面模式。

## 快速运行

```bash
python -m web.app          # http://127.0.0.1:8765
python -m pytest tests/ -q # 测试
```

- 改 `web/static/**` 刷新页面即生效；改 Python 后端需重启。
- 版本号唯一来源：`spellforge/__version__.py`。

## 前端设计语言（必须对齐）

**任何前端改动（HTML/CSS/JS/交互/文案）动手前，先读并遵守 `docs/前端设计规范.md`。**

要点速查（细节以规范文档为准）：

- 设计 token 只有一组：米白 `#f6f4ef` 底 + 青绿 `--accent #20808d`，语义色 ok/warn/bad/run/violet；禁止暗色主题与 token 外取色。
- 组件类名复用 `style.css`：`.btn(.primary/.small/.ghost/.danger)`、`.chip(.ok/.run/.warn/.bad/.violet)`、`.card`、`.panel`、`.field`、`.prompt`、`.tablecard`、`.modal-mask/.modal`、`.toast-root/.toast`、`.empty`、`.progress`、`.statusbar`。
- 交互工具全部用 `web/static/app.js` 顶部实现：`toast()`、`confirmDialog()`、`busy(btn, text)`、`fmtTime()`——**禁止**原生 `confirm/alert`，危险操作必须走确认弹窗（Esc 取消 / Enter 确认）。
- 异步按钮必须 busy（disabled + aria-busy + 「处理中…」，长任务带进度如「补全中 12/75」）；失败 toast 带原因；全局反馈只用 toast，不用 alert。
- 时间展示统一 `fmtTime()`（UTC → 本地时区），数字用 `font-variant-numeric: tabular-nums`。
- `web/static/style.css` 顶部 token 段与 `91porn-download/web/static/style.css` 保持逐字一致；发现不一致时以规范文档为准修正本仓库，不要在页面里发明第二套颜色。

## 前端结构

```
web/static/index.html   页面骨架 + 三视图（#browse 场景库 / #subj 主体库 / #gen 生成器）+ LLM 设置弹窗
web/static/style.css    全部样式（token 在顶部；与参考项目共享）
web/static/app.js       状态、视图切换、API 渲染、toast/confirm/busy/fmtTime
```

跨仓库参考（只读，不改动）：`/Users/zwy/Sites/91porn-download`（主参考）、`/Users/zwy/Sites/riban-ranking`（次参考）。

## 后端约定

- API 前缀 `/api/*`；错误返回 FastAPI `detail`，前端 toast 直接展示 `detail`。
- 首次运行从 `data/*.json` 种子建库；LLM 配置与历史在 `data/personal.db`（勿提交/勿打印）。
- 桌面模式写请求通过一次性 `sf_token`（`app.js` 开头的 fetch 包装自动注入）；改前端请求逻辑时不得绕过。
