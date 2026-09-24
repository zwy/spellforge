# 通用自然语言提示词规范

> 版本 1.0 · 提炼自 [openrouter.ai 图像基准](https://openrouter.ai/benchmarks/media/images) 的 75 条官方评测提示词，并与本库 300 条创意模板交叉校验。所有英文示例均为语料原文，标注出处。

## 1. 定位与用途

这份规范回答一个问题：**用自然语言描述一张图，怎样写才能让图像模型稳定、准确地出图。**

它有两个用途：

1. **给人**：写图像提示词时的结构参照与检查清单；
2. **给 LLM**：作为系统约束注入，让模型按统一结构生成或改写提示词（配合第 7 节的中文创意模板句式与 `creative_templates.json` 使用）。

{{stats_summary}}

## 2. 总则：五条原则

1. **具体压倒抽象。** 用可拍摄、可绘制的具体名词、动作与数字，不用「美丽」「高级」「有意境」这类无法执行的形容词。语料里没有一处出现 vague 形容词堆砌——每个修饰都有画面指向。
2. **一个画面，一个瞬间。** 一条提示词只描述一个连贯的瞬间；动作要抓「正在进行」的临界点（mid-conversation、at the moment of a layup、mid-yawn）。多主体必须写清数量与相互关系。
3. **维度完整，但不堆砌。** 按第 3 节骨架逐维度检查；每个维度用一两个精准表达即可，不要同义重复。官方语料每条 50–90 个英文词（约 120–220 汉字），从不超载。
4. **可验证优先。** 优先写「一眼能检查对错」的硬细节：文字是否清晰、脚是否离地、边缘是否垂直、数量是否正确。这是基准级提示词与随手感写的分水岭。
5. **明确说不。** 不要什么要直接列出（no text / no logos / no gradients / 不裁切关键部位），并主动保留真实感的不完美（见 4.9）。

## 3. 提示词骨架

所有官方提示词都遵循同一条链路：

```
[媒介/风格声明] → [主体与瞬间] → [环境与时间] → [构图与镜头] → [光线] → [材质与质感] → [色彩] → [精确性细节] → [负面约束]
```

完整示例（影棚人像）：

{{example:portraits/studio-headshot}}

逐段拆解：

| 骨架段 | 对应原文 |
|---|---|
| 媒介声明 | Studio headshot of a woman |
| 主体与瞬间 | in a charcoal blazer |
| 环境与时间 | against a mid-grey seamless backdrop |
| 光线 | lit by a large softbox slightly above and to the left with a soft fill from the right, catchlights in both eyes |
| 构图与镜头 | An 85mm look with shallow depth of field |
| 质感与不完美保留 | skin texture and flyaway hairs kept rather than smoothed |

篇幅与句式基线：

- **2–3 句陈述句**；第一句完成「媒介 + 主体 + 动作 + 环境」，第二句给技术细节（光线/镜头/材质），约束性短语放最后。
- 逗号分隔的短语从句为主，几乎不用感叹号、不用省略号、不堆形容词。
- 中文版（创意模板）对应 120–220 字，句式见第 7 节。

## 4. 九大维度写法规范

### 4.1 媒介与风格声明

**要点**：第一个短语锁定媒介类型；不同风格族有固定「锚语」（完整表见第 5 节）。声明要具体到子类型——不是 photograph，而是 candid photograph / studio headshot / macro photograph / wildlife photograph。

{{vocab:媒介与风格声明}}

### 4.2 主体与瞬间

**要点**：
- 主体唯一且明确；动作抓「临界瞬间」：`laughing mid-conversation`、`pulling her helmet off after a hard landing`、`the ball leaving the fingertips`。
- 身份靠具体锚点（发型、服装、道具、体态）而非形容词。
- 单独可验证的姿态细节（`one forepaw raised`、`one ear turned toward the camera`）同时承担身份与精确性两个职责。

{{vocab:主体与瞬间}}

### 4.3 环境与时间

**要点**：具体地点 + 一两件道具 + 时间/天气；环境必须服务主体而不是抢戏。语料反复使用「时间点即光位」的写法：`late afternoon sun`、`at dawn`、`an hour before sunset`、`in early morning mist`。

{{vocab:环境与时间}}

### 4.4 构图与镜头

**要点**：景别、视角、镜头、画面完整性四件套至少写其二。
- 景别：`close-up` / `head and shoulders` / `full body` / `wide angle` / `fills the frame`
- 视角：`three-quarter view` / `low angle` / `eye level` / `from above`
- 镜头：`85mm look`、`shallow depth of field`、`long lens compression`、`wide angle`
- 完整性：`complete from base to tip`、`centred with generous margin`、`every vertical edge straight`

{{vocab:构图与镜头}}

### 4.5 光线

**要点**：光源类型 + 方向 + 质量三要素；最多两个光源，主光必有方向。影棚布光可以精确到位置关系（`a large softbox slightly above and to the left with a soft fill from the right`）。自然光用时间/天气间接定义（`overcast daylight with no direct sun`）。

{{vocab:光线}}

### 4.6 材质与质感

**要点**：
- 用「对比」写材质：`the matte plastic and the brushed aluminium reading as different materials`。
- 用「读作」写感知：`the glass reads amber through its full depth`、`rough glass rather than plastic`。
- 用「分辨率」写细节：`grain, knots and fine cracks resolved sharply`、`the canvas weave showing through`。

{{vocab:材质与质感}}

### 4.7 色彩

**要点**：默认低饱和、自然；描述「色相 + 明度 + 面积」而非情绪词。有限调色板要给数量（`four colours per region`、`a sixteen-colour palette`、`two colours only`）。

{{vocab:色彩}}

### 4.8 精确性与可验证细节

**要点**：基准级提示词都含至少一条「硬检查」：
- 数量：`nine icons`、`four cooks`、`five habits`
- 状态：`feet visibly off the ground`、`propeller blades still`、`steam still coming off the crumb`
- 文字：`all text legible`、`the printed text sharp`（要出现的文字必须原样写出）
- 结构正确性：`the wing struts and control surfaces where they should be`、`mechanically plausible`

{{vocab:精确性与可验证细节}}

### 4.9 负面约束与不完美保留

负面约束直接、具体、可数，放在提示词末尾：

{{vocab:负面约束}}

「不完美保留」是这批语料最鲜明的指纹——真实感来自被明确保留下来的瑕疵，以及 **X rather than Y** 的对比式表达：

{{vocab:不完美与真实感}}

典型句式：

> skin texture and flyaway hairs kept rather than smoothed（保留皮肤纹理与碎发，而非磨平）
> expression tired rather than triumphant（神情疲惫而非得意）
> the frosted body reading as rough glass rather than plastic

## 5. 风格族适配

六族媒介各有固定的「锚语」与特有维度。**同一主体跨风格改写时，主体、动作、光向描述保持不变，只替换风格声明与质感语言**——`style-switching` 组的 7 条语料是现成对照（同一游泳者出水瞬间 × 7 种风格）。

| 风格族 | 锚语（开头） | 特有维度 | 专属约束 |
|---|---|---|---|
| 写实摄影 | Photograph of / Candid photograph of / Macro photograph of | 焦段、景深、天气时刻、皮肤与毛发细节 | no motion blur、no visible logos |
| 3D 渲染 | 3D render, physically based materials, soft studio lighting. | PBR 材质、全局光照、接触阴影 | no text anywhere、no decoration |
| 动漫 | Anime illustration, clean cel shading and crisp linework. | 赛璐璐分块阴影、硬边高光「以块面而非渐变呈现」 | 线稿干净、背景厚涂衬托 |
| 扁平矢量 | Flat vector illustration, bold two-colour poster style. | 负形、笔画等宽、几何简化 | no gradients、consistent stroke weight |
| 绘画 | Oil painting, thick impasto / Loose watercolor / Ink line drawing | 笔触、颜料行为（bloom、granulate）、边缘处理 | no hatching、edges left unresolved |
| 像素 | Pixel art (sprite / portrait / scene) | 网格尺寸、调色板数量、无抗锯齿 | hard pixels、no anti-aliasing |
| 设计图文（Logo/海报/UI） | Logo design: / Front cover of… / A mobile app screen mockup | 精确文字、字重层级、留白与对齐 | legible、no additional text、centred with generous margin |

跨风格对照示例（anime → 同主体 photo 版）：

{{example:style-switching/photo}}

## 6. 画幅比例指引

画幅不由画面内容凭空猜，由「题材 + 用途」决定。下表从本库 75 条场景的 LLM 推断比例统计而来：

{{ratio_table}}

约定：比例写 `宽:高`；未指明用途时，人像/竖版题材默认 `2:3`，横向题材默认 `3:2`，图标/图案/Logo 默认 `1:1`，手机 UI 默认 `9:16`。

## 7. 中文创意模板句式

本库 300 条创意模板（`creative_templates.json`）遵循同一句式骨架，用于「用户带主体 + 选模板 → LLM 生成新提示词」：

```
以「所选主体」为唯一核心，生成一张……。
构图：……（景别/视角/完整入镜/留白）。
光线：……（光源/方向/质量）。
质感与色彩：……。
保持主体身份与关键特征（外形、比例、配色、标志性细节）一致。
不出现文字、Logo、水印、边框或乱码。
```

句式要点：

1. **主体锚定开场**：首句必须点明「所选主体」是唯一焦点；
2. **构图给出可执行边界**：`完整入镜`、`不裁切顶部或关键轮廓`、`四周留出均匀余白`；
3. **光线写布光而非氛围**：`左侧大面积柔光箱为主光，右侧黑色挡板压住边缘`；
4. **身份一致性单列一句**：明确列出不能被改变的特征清单（发型、脸型、配色、道具、服饰）；
5. **负面约束收尾**：固定短语 `不出现文字、Logo、水印、边框或乱码`，设计类另加 `除规范字标外`。

生成新提示词时，把模板 value 中的风格要素迁移到用户主体上，再按第 3 节骨架查漏。

## 8. 质量检查清单

写完（或生成）一条提示词后逐条自检：

- [ ] 第一句是否锁定媒介/风格？锚语对不对（对照第 5 节）？
- [ ] 主体是否唯一？是否有一个明确的「正在发生」的瞬间？
- [ ] 主体身份锚点（发型/服装/道具/配色）是否具体？
- [ ] 环境是否有具体地点 + 时间/天气，且不抢主体？
- [ ] 构图是否给了景别与视角？主体是否完整、裁切是否说明？
- [ ] 光线是否写明方向与质量（至多两个光源）？
- [ ] 材质是否有对比或「读作」式表达？
- [ ] 需要出现的文字是否原样写出并要求 legible？
- [ ] 负面约束是否列全（文字/水印/Logo/多余物体）？
- [ ] 是否保留了一处刻意的不完美（纹理/碎发/歪斜）？

## 9. 语料说明

- 官方语料：75 条英文评测提示词，全部为陈述句、无标点堆砌、无权重语法（无 `(xx:1.2)`）、无模型参数——**规范是语言层面的，不绑定任何模型**。
- 词汇库：由 LLM 从语料中分批提取并去重（`data/spec_vocab.json`），重跑 `python -m styles.spec --refresh-vocab` 可再生成。
- 数据更新：抓取流程（`python -m styles.scrape`）与 LLM 补全（`python -m styles.enrich`）运行后，重跑 `python -m styles.spec` 即可让本文档的统计、示例与比例表同步最新语料。
