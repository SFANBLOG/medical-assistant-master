"""知识库文档「追写」增强脚本。

对 backend/data/uploads/<知识库>/公有|私有/*.md 下的全部文档进行内容追写：
在每个文档末尾追加以下章节（内容以原文事实为基准 + 按科室分类的通用循证建议，
不臆造具体诊疗方案）：

1. ## 常见问题解答（FAQ）—— 从原文各章节抽取生成的问答对
   （什么是XX？XX的病因/症状/治疗/护理/预防/就医……）
2. ## 检查与诊断 —— 按知识库分类的常用检查项目
3. ## 预防与日常保健 —— 通用循证预防建议
4. ## 就医指引 —— 就诊科室、何时就医

幂等：已包含 "## 常见问题解答" 的文档自动跳过，可重复运行。
运行：python enrich_docs.py
"""
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "data", "uploads")

PUBLIC_DIR = "公有"
PRIVATE_DIR = "私有"

# ---- 按知识库分类的通用内容 ----
KB_DEPT = {
    "呼吸系统疾病": "呼吸内科",
    "心血管疾病": "心血管内科",
    "消化系统疾病": "消化内科",
    "神经系统疾病": "神经内科",
    "内分泌代谢疾病": "内分泌科",
    "泌尿肾脏疾病": "肾内科、泌尿外科",
    "风湿免疫疾病": "风湿免疫科",
    "感染性疾病": "感染科",
    "急诊急症": "急诊科",
    "外科骨科疾病": "骨科、普外科等相应专科",
    "皮肤科疾病": "皮肤科",
    "妇儿疾病": "儿科、妇产科",
}

KB_TESTS = {
    "呼吸系统疾病": "血常规、C反应蛋白等炎症指标、胸部影像学检查（X线/CT）、肺功能检查、血气分析、痰培养及药敏等。",
    "心血管疾病": "血压测量、心电图、心脏超声、动态血压/动态心电图监测、血脂血糖、心肌损伤标志物等。",
    "消化系统疾病": "血常规、肝功能、腹部超声、胃镜/肠镜、幽门螺杆菌检测、大便潜血等。",
    "神经系统疾病": "神经系统查体、头颅CT/MRI、脑电图、肌电图、脑脊液检查等。",
    "内分泌代谢疾病": "血糖、糖化血红蛋白、甲状腺功能、血脂、尿酸、骨密度、相关激素水平及功能试验等。",
    "泌尿肾脏疾病": "尿常规、尿蛋白定量、肾功能、泌尿系超声、尿培养、肾穿刺活检等。",
    "风湿免疫疾病": "血沉、C反应蛋白、类风湿因子、自身抗体谱、关节影像学检查等。",
    "感染性疾病": "血常规、炎症标志物（CRP/PCT）、病原学检查（培养、抗原/抗体检测、核酸）等。",
    "急诊急症": "生命体征评估、心电图、血常规与生化、床旁超声、必要时的影像学检查等。",
    "外科骨科疾病": "X线、CT、MRI等影像学检查、血常规及凝血功能等，必要时专科查体评估。",
    "皮肤科疾病": "皮肤专科视诊、真菌镜检、过敏原检测、皮肤病理活检等。",
    "妇儿疾病": "儿科/妇产科专科查体、血常规等基础检查，必要时按专科指南进一步检查。",
}

KB_PREVENTION = {
    "呼吸系统疾病": "戒烟、避免吸入粉尘与有害气体，流感季节接种疫苗，注意保暖、避免受凉，勤洗手、保持室内通风，规律运动增强体质。",
    "心血管疾病": "低盐低脂饮食、控制体重、戒烟限酒、规律有氧运动、保持情绪平稳，定期监测血压血脂血糖，遵医嘱服药。",
    "消化系统疾病": "规律三餐、细嚼慢咽、避免过饱与刺激性食物，戒烟限酒，注意饮食卫生，保持作息规律，避免长期精神紧张。",
    "神经系统疾病": "规律作息、避免过度劳累与熬夜，控制高血压、糖尿病、高血脂等基础病，保持心情舒畅，适量运动。",
    "内分泌代谢疾病": "均衡饮食、控制总热量、规律运动、保持健康体重，定期体检监测血糖、血脂、尿酸等指标。",
    "泌尿肾脏疾病": "多饮水、不憋尿、注意个人卫生，避免滥用药物（尤其止痛药、抗生素），定期体检查尿常规与肾功能。",
    "风湿免疫疾病": "规律作息、均衡营养、适度锻炼、避免感染与过度劳累，遵医嘱规范用药，定期复查随访。",
    "感染性疾病": "勤洗手、保持环境通风、接种疫苗、注意饮食与饮水卫生，流行季节减少人群聚集，出现症状及时就医。",
    "急诊急症": "学习常见急症的家庭急救常识（如心肺复苏、止血包扎、烫伤处理），高危人群定期体检，出现急症征兆立即就医。",
    "外科骨科疾病": "合理运动、运动前充分热身、注意劳动与运动防护，控制体重、加强肌肉力量训练，预防跌倒。",
    "皮肤科疾病": "保持皮肤清洁保湿、避免过度搔抓与日晒，选择温和护肤品，注意个人物品不共用，出现皮疹及时就诊。",
    "妇儿疾病": "科学喂养、按时接种疫苗、注意手卫生与居家通风，孕期定期产检，儿童发热等症状持续不缓解及时就医。",
}

SECTION_RULES = [
    (re.compile(r"病因|原因|诱因|发病"), "病因"),
    (re.compile(r"症状|表现|信号"), "症状"),
    (re.compile(r"治疗|处理|用药|药物|方案"), "治疗"),
    (re.compile(r"护理|注意|观察|管理|日常"), "护理"),
    (re.compile(r"预防|筛查"), "预防"),
    (re.compile(r"就医|就诊|急诊"), "就医"),
    (re.compile(r"诊断|检查|临床要点|判读|解读"), "诊断"),
]


def _parse_doc(text: str) -> tuple[str, str, dict]:
    """解析 md：返回 (标题, 简介段落, {章节名: 内容})。"""
    lines = text.splitlines()
    title = ""
    intro = ""
    sections: dict[str, list[str]] = {}
    current = None
    intro_parts: list[str] = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("# "):
            title = s[2:].strip()
            current = None
        elif s.startswith("## "):
            current = s[3:].strip()
            sections.setdefault(current, [])
        elif s and not s.startswith("#") and not s.startswith("（") and not s.startswith("(本文"):
            if current is None:
                intro_parts.append(s)
            else:
                sections[current].append(s)
    intro = " ".join(intro_parts).strip()
    return title, intro, {k: "\n".join(v).strip() for k, v in sections.items()}


def _map_section(header: str, sections: dict) -> str:
    for pat, key in SECTION_RULES:
        if pat.search(header):
            content = sections.get(header, "")
            if content:
                return content
    return ""


def _faq_block(title: str, intro: str, sections: dict, kb_name: str) -> str:
    """根据文档章节生成常见问题解答。"""
    name = title or "该疾病"
    qa: list[tuple[str, str]] = []

    if intro:
        qa.append((f"什么是{name}？", intro))
    cause = next((_map_section(h, sections) for h in sections if _map_section(h, sections) and "因" in h), "")
    if cause:
        qa.append((f"{name}的病因/诱因有哪些？", cause))
    symptom = next((_map_section(h, sections) for h in sections if _map_section(h, sections) and ("症状" in h or "表现" in h)), "")
    if symptom:
        qa.append((f"{name}有哪些典型症状或表现？", symptom))
    treat = next((_map_section(h, sections) for h in sections if _map_section(h, sections) and any(k in h for k in ("治疗", "处理", "用药", "方案"))), "")
    if treat:
        qa.append((f"{name}应该如何治疗/处理？", treat))
    care = next((_map_section(h, sections) for h in sections if _map_section(h, sections) and any(k in h for k in ("护理", "注意", "管理", "观察"))), "")
    if care:
        qa.append((f"{name}患者日常需要注意什么？", care))
    preven = next((_map_section(h, sections) for h in sections if _map_section(h, sections) and "预防" in h), "")
    if preven:
        qa.append((f"如何预防{name}？", preven))
    clinic = next((_map_section(h, sections) for h in sections if _map_section(h, sections) and any(k in h for k in ("诊断", "临床要点", "检查"))), "")
    if clinic:
        qa.append((f"{name}的诊断与评估要点有哪些？", clinic))

    if not qa:
        return ""

    lines = [f"### {name}常见问题解答（FAQ）"]
    for q, a in qa:
        a_clean = " ".join(a.split())
        lines.append(f"- **{q}**：{a_clean}")
    return "\n".join(lines)


def _generic_blocks(kb_name: str, name: str) -> str:
    dept = KB_DEPT.get(kb_name, "相应专科")
    tests = KB_TESTS.get(kb_name, "血常规等基础检查，必要时由专科医生进一步评估。")
    prevention = KB_PREVENTION.get(kb_name, "保持健康生活方式，规律作息、均衡饮食、适量运动，定期体检，出现不适及时就医。")
    blocks = [
        f"## 检查与诊断\n{name}的确诊需要结合临床表现与辅助检查。常用检查包括：{tests}具体检查项目应由接诊医生根据病情决定。",
        f"## 预防与日常保健\n{prevention}",
        f"## 就医指引\n如出现疑似{name}的相关症状，建议及时到{dept}就诊；症状较重或持续不缓解、进行性加重时，应立即就医，切勿拖延。就诊时请如实告知医生症状持续时间、既往病史与用药情况。",
    ]
    return "\n\n".join(blocks)


def enrich_file(path: str, kb_name: str) -> tuple[bool, str]:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "常见问题解答" in text:
        return False, ""
    title, intro, sections = _parse_doc(text)
    name = title or os.path.splitext(os.path.basename(path))[0]
    faq = _faq_block(name, intro, sections, kb_name)
    extra = _generic_blocks(kb_name, name)
    addition = "\n\n---\n\n" + faq + "\n\n" + extra if faq else "\n\n---\n\n" + extra
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.rstrip() + addition + "\n")
    return True, name


def main() -> None:
    total = enriched = 0
    if not os.path.isdir(SRC):
        print(f"目录不存在: {SRC}")
        return
    for kb_name in sorted(os.listdir(SRC)):
        kb_dir = os.path.join(SRC, kb_name)
        if not os.path.isdir(kb_dir):
            continue
        for sub in (PUBLIC_DIR, PRIVATE_DIR):
            sub_dir = os.path.join(kb_dir, sub)
            if not os.path.isdir(sub_dir):
                continue
            for fname in sorted(os.listdir(sub_dir)):
                if not fname.lower().endswith((".md", ".txt")):
                    continue
                path = os.path.join(sub_dir, fname)
                total += 1
                ok, name = enrich_file(path, kb_name)
                if ok:
                    enriched += 1
                    print(f"[+] {kb_name}/{sub}/{fname}")
    print(f"\n完成：共 {total} 个文档，追写 {enriched} 个，跳过 {total - enriched} 个。")


if __name__ == "__main__":
    main()
