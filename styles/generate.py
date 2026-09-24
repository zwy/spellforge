"""提示词生成器：风格 + 场景 + 创意模板 + 用户主体 → 新提示词。

规范文档（docs/通用自然语言提示词规范.md）作为系统约束注入。
"""
from __future__ import annotations

from pathlib import Path

from . import personal, store
from .llm import chat_json, get_llm_config

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "docs" / "通用自然语言提示词规范.md"
ASPECT_RATIOS = ["1:1", "2:3", "3:2", "4:5", "5:4", "3:4", "4:3", "9:16", "16:9"]

_spec_cache: str | None = None


def load_spec() -> str:
    global _spec_cache
    if _spec_cache is None:
        if not SPEC_PATH.exists():
            raise RuntimeError("规范文档不存在，先运行 python -m styles.spec")
        _spec_cache = SPEC_PATH.read_text(encoding="utf-8")
    return _spec_cache


SYSTEM_TMPL = """你是图像提示词生成专家。生成提示词时必须严格遵守下方《通用自然语言提示词规范》——它是从 75 条官方基准提示词提炼的结构与用语规范。只返回合法 JSON。

==== 通用自然语言提示词规范 ====
{spec}
==== 规范结束 ====
"""

USER_TMPL = """任务：把用户提供的主体代入指定风格场景，生成新的图像提示词。

风格：{style_name}（分组：{group}）
风格选用说明：{why_chosen}
场景：{scenario_label}
该场景官方参考提示词：{official_prompt}
选用创意模板（{template_label}）：
{template_value}

用户主体描述：
{subject}
画幅要求：{aspect_ratio}

关键规则（必须全部遵守）：
1. 主体必须具象化——这是最重要的一条。图像模型只看得到提示词文本，不认识"徐丽"或"所选主体"这类指代。必须从用户主体描述中提取具体外形特征（性别与年龄段、发型发色、五官、肤色、体型、服饰、气质），直接写进提示词；绝对禁止只写名字或「所选主体」这类指代。
2. 特征取舍：外形特征取最能定义身份的 5-8 项，不逐条罗列；服饰与标志性物件完整保留。
3. 动作与道具适配主体：模板中的动作与道具（如"把木作举到窗边"是匠人场景的道具）若与主体身份明显不符，要替换为主体合理会做的事与物，但保留场景的构图、光线与质感框架。
4. 保留官方场景与模板的风格要素（光线、材质、构图语言）与约束（身份一致、负面约束）。

输出：
1. prompt_en：英文提示词，遵循规范第 3 节骨架与第 5 节该风格族的锚语与维度，50-90 词，以具象化的主体开场。
2. prompt_zh：中文提示词，遵循规范第 7 节句式（120-220 字）。开头必须嵌入主体的外形描述来替换「所选主体」四个字（例：「以一位乌黑齐肩波浪卷发、杏仁眼、肤色白皙透蜜桃色调、身穿白色丝质连衣裙的东亚女性为核心」）；收尾的身份一致句要列出该主体的关键特征清单。
3. aspect_ratio：按规范第 6 节为该题材选择（{ratio_hint}）。
4. notes：一句话说明风格如何迁移到用户主体（30 字内，中文）。

只返回 JSON：{{"prompt_en": "...", "prompt_zh": "...", "aspect_ratio": "w:h", "notes": "..."}}"""


def build_messages(style, sc, template_label: str, template_value: str,
                   subject: str, aspect_ratio: str | None) -> list[dict]:
    system = SYSTEM_TMPL.format(spec=load_spec())
    ratio_hint = f"用户指定 {aspect_ratio}" if aspect_ratio else "由你按规范第 6 节决定"
    user = USER_TMPL.format(
        style_name=style.name, group=style.group, why_chosen=style.why_chosen,
        scenario_label=sc.label, official_prompt=sc.prompt,
        template_label=template_label, template_value=template_value,
        subject=subject, aspect_ratio=aspect_ratio or "由你决定", ratio_hint=ratio_hint,
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def generate(style_id: str, scenario_id: str, template_label: str,
             subject: str, aspect_ratio: str | None = None,
             model: str | None = None, subject_id: int | None = None) -> dict:
    """生成一条提示词并落库，返回完整记录。

    subject_id 传主体库 id：主体描述为空时自动取该主体的描述；
    历史记录会保存 subject_id 与主体名称快照。
    """
    subject = (subject or "").strip()
    if aspect_ratio and aspect_ratio not in ASPECT_RATIOS:
        raise ValueError(f"画幅比例应为 {'、'.join(ASPECT_RATIOS)} 之一")

    conn = store.connect()
    try:
        subject_name: str | None = None
        if subject_id is not None:
            sub = store.get_subject(conn, subject_id)
            if sub is None:
                raise ValueError(f"主体不存在: {subject_id}")
            subject_name = sub["name"]
            if not subject:
                subject = sub["description"]
        if not subject:
            raise ValueError("主体描述不能为空")
        style = next((s for s in store.load_styles(conn) if s.id == style_id), None)
        if style is None:
            raise ValueError(f"风格不存在: {style_id}")
        sc = next((s for s in style.scenarios if s.id == scenario_id), None)
        if sc is None:
            raise ValueError(f"场景不存在: {scenario_id}")
        tpl = next((t for t in (sc.creative_copy or [])
                    if (t.label if not isinstance(t, dict) else t["label"]) == template_label), None)
        if tpl is None:
            raise ValueError(f"模板不存在: {template_label}")
        tpl_value = tpl.value if not isinstance(tpl, dict) else tpl["value"]
        template_label = tpl.label if not isinstance(tpl, dict) else tpl["label"]

        result = chat_json(
            build_messages(style, sc, template_label, tpl_value, subject, aspect_ratio),
            max_tokens=16000, model=model,
        )
        prompt_en = str(result.get("prompt_en", "")).strip()
        prompt_zh = str(result.get("prompt_zh", "")).strip()
        if not prompt_en or not prompt_zh:
            raise ValueError(f"LLM 返回不完整: {list(result.keys())}")
        rec = {
            "style_id": style_id, "scenario_id": scenario_id,
            "template_label": template_label, "subject": subject,
            "subject_id": subject_id, "subject_name": subject_name,
            "prompt_zh": prompt_zh, "prompt_en": prompt_en,
            "aspect_ratio": aspect_ratio or result.get("aspect_ratio"),
            "notes": str(result.get("notes", ""))[:200],
            "model": model or get_llm_config()["model"],
        }
        conn.close()
        pconn = personal.connect()
        try:
            rec["id"] = personal.save_generation(pconn, rec)
        finally:
            pconn.close()
        return rec
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
