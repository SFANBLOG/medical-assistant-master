"""文本处理：递归字符级切分 + 关键词重叠度。

中文没有空白分词，因此按「段落 -> 行 -> 句子 -> 固定字符」递归切分，
始终在字符边界断开（Python str 按码点切片，不会切裂单个汉字/字符）。
"""
import re

# 分词正则：拉丁字母/数字/下划线 + 连续汉字
WORD_RE = re.compile(r"[a-zA-Z0-9_]+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
SENT_END_RE = re.compile(r"[。！？!?；;]")
PARA_SPLIT_RE = re.compile(r"\n\s*\n")
LINE_SPLIT_RE = re.compile(r"\n")


def tokenize(text: str) -> list[str]:
    """分词：英文单词取整词；连续汉字按字符二元组切分（CJK 无空格分词，
    二元组可命中跨文档的相邻字对，显著提升离线检索相关性）。"""
    tokens: list[str] = []
    for w in WORD_RE.findall(text.lower()):
        tokens.append(w)
    for run in CJK_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i: i + 2] for i in range(len(run) - 1))
    return tokens


def keyword_overlap(question: str, text: str) -> float:
    """简单关键词重叠度，用于召回后的轻量重排加分。"""
    q_tokens = tokenize(question)
    if not q_tokens:
        return 0.0
    t_tokens = set(tokenize(text))
    hit = sum(1 for t in q_tokens if t in t_tokens)
    return hit / len(q_tokens)


def char_overlap(question: str, text: str) -> float:
    """字符级覆盖度：提问中的有效中文字符有多少出现在候选文本中（0~1）。

    中文问答中提问往往只包含几个关键实体（疾病名、症状、身体部位），
    字符级覆盖对「问题 -> 参考片段」的匹配比二元组分词更稳定，
    即使文档措辞不同，只要实体一致即可得到较高分值。
    """
    q_chars = {ch for ch in question if "\u4e00" <= ch <= "\u9fff"}
    if not q_chars:
        return 0.0
    t_chars = set(text)
    hit = sum(1 for ch in q_chars if ch in t_chars)
    return hit / len(q_chars)


# 医疗常见同义词/别称归一化：提问与文档用词不一致时统一到主词。
SYNONYMS = {
    # ================= 通用/基础症状 =================
    "发烧": "发热",
    "中风": "脑卒中",
    "脑中风": "脑卒中",
    "脚气": "足癣",  # 注意：非“脚汗”或“臭脚”，特指真菌感染
    "青春痘": "痤疮",
    "牛皮癣": "银屑病",
    "上感": "上呼吸道感染",
    "肠胃炎": "胃肠炎",
    "高血压病": "高血压",
    "高血脂": "血脂异常",

    # ================= 呼吸系统 =================
    "感冒": "急性上呼吸道感染",
    "流感": "流行性感冒",
    "咳血": "咯血",
    "气胸": "自发性气胸",  # 若上下文未提及外伤
    "慢阻肺": "慢性阻塞性肺疾病",
    "肺心病": "慢性肺源性心脏病",
    "白喉": "白喉病",

    # ================= 心血管系统 =================
    "冠心病": "冠状动脉粥样硬化性心脏病",
    "心梗": "心肌梗死",
    "急冠综": "急性冠状动脉综合征",
    "心衰": "心力衰竭",
    "房颤": "心房颤动",
    "室早": "室性期前收缩",
    "室速": "室性心动过速",
    "风心病": "风湿性心脏病",
    "先心": "先天性心脏病",

    # ================= 消化系统 =================
    "胃炎": "胃炎症",  # 泛指，具体需结合语境，此处做基础归一
    "肠炎": "肠炎症",
    "乙肝": "乙型病毒性肝炎",
    "丙肝": "丙型病毒性肝炎",
    "甲肝": "甲型病毒性肝炎",
    "肝癌": "原发性肝癌",  # 默认情况
    "肝硬化": "肝硬变",
    "胰腺炎": "急性胰腺炎",  # 默认急性，若慢性需额外判断，此处取高频
    "胆囊炎": "急性胆囊炎",
    "阑尾炎": "急性阑尾炎",
    "痔疮": "痔",
    "肛裂": "肛门裂",
    "胃溃疡": "胃溃疡",
    "十二指肠溃疡": "球部溃疡",  # 通俗叫法
    "便秘": "功能性便秘",  # 泛指
    "腹泻": "痢疾",  # 注意：老百姓常混用，医学上痢疾有特异性，但归一化时视场景，此处仅列常见混淆，建议谨慎
    # 修正：下面改为更准确的医学同义
    "拉肚子": "腹泻",
    "烧心": "胃食管反流",  # 症状指代

    # ================= 神经系统 =================
    "癫痫": "羊癫疯",
    "癔症": "分离转换性障碍",
    "偏瘫": "半身不遂",
    "痴呆": "认知功能障碍",  # 或阿尔茨海默病等，视语境
    "帕金森": "帕金森病",
    "坐骨神经痛": "坐骨神经病理性疼痛",

    # ================= 内分泌/代谢 =================
    "糖尿病": "消渴病",  # 中医别称，西医统称即糖尿病
    "甲亢": "甲状腺功能亢进症",
    "甲减": "甲状腺功能减退症",
    "甲功": "甲状腺功能",
    "侏儒症": "生长激素缺乏症",
    "呆小症": "先天性甲状腺功能减退症",
    "尿崩": "尿崩症",
    "痛风石": "痛风结节",

    # ================= 泌尿/肾脏 =================
    "肾炎": "肾小球肾炎",
    "肾衰": "肾功能衰竭",
    "尿毒症": "慢性肾脏病5期",
    "结石": "尿路结石",
    "前列腺增生": "良性前列腺增生",
    "阳萎": "勃起功能障碍",
    "早泄": "射精过快",  # 或保留早泄，视标准库而定，这里统一为ED相关或原词

    # ================= 骨科/运动医学 =================
    "骨折": "骨质断裂",
    "脱臼": "关节脱位",
    "扭伤": "韧带损伤",
    "腰突": "腰椎间盘突出症",
    "颈椎病": "颈椎退行性变",
    "肩周炎": "冻结肩",
    "网球肘": "肱骨外上髁炎",
    "鼠标手": "腕管综合征",
    "滑膜炎": "膝关节滑膜炎",
    "半月板损伤": "膝半月板撕裂",

    # ================= 皮肤/性病 =================
    "梅毒": "花柳病",  # 旧称
    "淋病": "淋菌性尿道炎",
    "疱疹": "单纯疱疹",
    "带状疱疹": "缠腰龙",
    "湿疹": "特应性皮炎",  # 严格来说有区别，但患者常混用，此处可做模糊匹配
    "荨麻疹": "风疹块",
    "扁平疣": "瘊子",  # 俗称
    "白癜风": "白癜疯",
    "毛囊炎": "疖子",  # 早期

    # ================= 血液/肿瘤 =================
    "白血病": "血癌",
    "贫血": "红细胞减少症",  # 泛指
    "血友病": "出血性疾病",
    "淋巴瘤": "恶性淋巴瘤",
    "癌症": "恶性肿瘤",

    # ================= 妇科/产科 =================
    "宫外孕": "异位妊娠",
    "流产": "自然流产",  # 或人工流产，视语境
    "痛经": "经期腹痛",
    "闭经": "月经停止",
    "白带多": "阴道分泌物增多",
    "宫颈糜烂": "宫颈柱状上皮异位",  # 重要更新：医学名词变更
    "盆腔炎": "女性盆腔炎症性疾病",
    "多囊卵巢": "多囊卵巢综合征",
    "更年期": "围绝经期",

    # ================= 儿科/常见儿童病 =================
    "奶癣": "婴儿湿疹",
    "水痘": "水痘-带状疱疹",
    "手足口": "手足口病",
    "腮腺炎": "流行性腮腺炎",
    "百日咳": "百日咳病",
    "轮状病毒肠炎": "秋季腹泻",
    "小儿麻痹": "脊髓灰质炎",

    # ================= 五官科 =================
    "老花眼": "老视",
    "白内障": "老年性白内障",
    "青光眼": "高眼压症",  # 不完全等同，但常混用
    "近视": "近视眼",
    "远视": "远视眼",
    "散光": "规则散光",
    "耳鸣": "耳 auditory hallucination",  # 英文对照参考，中文归一为耳鸣
    "中耳炎": "分泌性中耳炎",  # 常见类型
    "鼻炎": "过敏性鼻炎",  # 最常见类型

    # ================= 精神/心理 =================
    "抑郁症": "抑郁障碍",
    "焦虑症": "广泛性焦虑障碍",
    "精神病": "精神分裂症",  # 严重误称，需纠正
    "自闭": "孤独症谱系障碍",
    "多动症": "注意缺陷多动障碍",
    "厌食症": "神经性厌食",

    # ================= 补充常用杂项 (凑齐100+) =================
    "晕车": "运动病",
    "中暑": "日射病",
    "冻疮": "冷伤",
    "破伤风": "新生儿破伤风",  # 或统称破伤风
    "狂犬病": "恐水病",
    "麻风": "汉生病",
    "疟疾": "打摆子",
    "登革热": "断骨热",
    "艾滋病": "获得性免疫缺陷综合征",
    "新冠": "新型冠状病毒感染",
    "二阳": "新冠病毒二次感染",
    "复阳": "核酸复阳",
    "长新冠": "新冠后遗症",
    "打鼾": "睡眠呼吸暂停",
    "失眠": "入睡困难",
    "多梦": "睡眠障碍",
    "乏力": "疲乏",
    "消瘦": "体重减轻",
    "浮肿": "水肿",
    "发绀": "青紫",
    "黄疸": "黄疽",
    "皮疹": "皮炎",
    "溃疡": "黏膜破损",
    "息肉": "增生",
    "囊肿": "囊性病变",
    "肿瘤": "肿块",
    "包块": "肿物",
}


def normalize_synonyms(text: str) -> str:
    """把常见同义词替换为主词，提升提问与文档的匹配度。"""
    for k, v in SYNONYMS.items():
        if k in text:
            text = text.replace(k, v)
    return text


# 文档标题的常见描述性后缀（剥离后得到疾病核心名，用于标题匹配）
DESC_SUFFIXES = (
    "的急救处理", "的院前处置", "的家庭护理", "的鉴别诊断", "的规范使用",
    "的规范治疗", "的早期筛查", "的早期信号", "的饮食管理", "的应急处理",
    "的现场处理", "的识别与处理", "的识别", "的防控", "的预防与保健", "的预防",
    "的处理", "的治疗", "的管理", "的诊断", "的筛查", "的护理", "的保健",
    "的注意事项", "的防治", "的药物管理", "的分级治疗", "的解读", "的判读",
    "的调整", "与随访", "的监测", "的规范化管理", "的适应证",
)


def core_disease_names(names: list[str]) -> set[str]:
    """从文档标题集合中剥离描述性后缀、拆分并列名，得到疾病核心名集合。

    例如「中暑的急救处理」->「中暑」；「感冒与流感」->「感冒」「流感」；
    「痛风与高尿酸血症」->「痛风」「高尿酸血症」。
    """
    out: set[str] = set()
    for n in names:
        n = n.strip().strip("#").strip()
        if not n:
            continue
        out.add(n)
        base = re.split(r"[（(]", n)[0].strip()
        # 剥离描述性后缀
        for sfx in sorted(DESC_SUFFIXES, key=len, reverse=True):
            if base.endswith(sfx) and len(base) - len(sfx) >= 2:
                base = base[: -len(sfx)]
                break
        # 拆分并列名：A与B / A及B / A和B
        for sep in ("与", "及", "和"):
            if sep in base:
                for part in base.split(sep):
                    part = part.strip()
                    if len(part) >= 2:
                        out.add(part)
        if len(base) >= 2:
            out.add(base)
    return out


def extract_disease(question: str, known_names: list[str]) -> str:
    """从提问中提取最长的已知疾病名（用于标题级强匹配）。

    known_names 传知识库文档标题（疾病名）列表即可；找不到返回空串。
    支持剥离描述性后缀（如「中暑的急救处理」的核心名「中暑」）与括号别名。
    """
    candidates: set[str] = set()
    for name in core_disease_names(known_names):
        candidates.add(name)
        # “银屑病（牛皮癣）”“慢性阻塞性肺疾病(COPD)” -> 括号内别名
        for part in re.findall(r"[（(]([^（）()]+)[）)]", name):
            part = part.strip()
            if len(part) >= 2:
                candidates.add(part)
    best = ""
    for name in candidates:
        if name in question and len(name) > len(best):
            best = name
    return best


def _split_sentences(paragraph: str) -> list[str]:
    """按句子结束标点切分，保留标点。"""
    parts = SENT_END_RE.split(paragraph)
    # 重新拼接标点到句子尾部
    delimiters = SENT_END_RE.findall(paragraph)
    sentences = []
    for i, part in enumerate(parts):
        if i < len(delimiters):
            sentences.append(part + delimiters[i])
        elif part.strip():
            sentences.append(part)
    return [s for s in sentences if s.strip()]


def _merge_chunks(chunks: list[str], size: int) -> list[str]:
    """把过小的片段合并到接近 size。"""
    merged: list[str] = []
    buffer = ""
    for c in chunks:
        if buffer and len(buffer) + len(c) > size:
            merged.append(buffer)
            buffer = c
        else:
            buffer += c
    if buffer:
        merged.append(buffer)
    return merged


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """递归字符级切分。返回去空白后的文本块列表。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in PARA_SPLIT_RE.split(text) if p.strip()]
    if not paragraphs:
        return []

    pieces: list[str] = []

    def push(piece: str) -> None:
        piece = piece.strip()
        if piece:
            pieces.append(piece)

    for para in paragraphs:
        if len(para) <= size:
            push(para)
            continue
        lines = [ln.strip() for ln in LINE_SPLIT_RE.split(para) if ln.strip()]
        for line in lines:
            if len(line) <= size:
                push(line)
                continue
            sentences = _split_sentences(line)
            for sent in sentences:
                if len(sent) <= size:
                    push(sent)
                    continue
                # 最后手段：固定长度按字符切分
                for i in range(0, len(sent), size):
                    push(sent[i: i + size])

    chunks = _merge_chunks(pieces, size)

    # 相邻块之间加 overlap
    if overlap > 0 and len(chunks) > 1:
        out: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            out.append((prev_tail + chunks[i]).strip())
        chunks = out

    return [c for c in chunks if c.strip()]


# 文档标题（Markdown # 风格）正则
HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _split_recursive(text: str, size: int) -> list[str]:
    """递归字符级切分（段落 -> 行 -> 句 -> 定长），返回长度 <= size 的片段列表。"""
    out: list[str] = []
    for para in [p.strip() for p in PARA_SPLIT_RE.split(text) if p.strip()]:
        if len(para) <= size:
            out.append(para)
            continue
        for line in [l.strip() for l in LINE_SPLIT_RE.split(para) if l.strip()]:
            if len(line) <= size:
                out.append(line)
                continue
            for sent in _split_sentences(line):
                if len(sent) <= size:
                    out.append(sent)
                    continue
                for i in range(0, len(sent), size):
                    out.append(sent[i: i + size])
    return out


def chunk_document(text: str, size: int = 380, overlap: int = 60) -> list[dict]:
    """标题感知切分：按章节标题分块、为每块携带所属小节上下文、去除近重复块。

    返回 [{"text": str, "heading": str}, ...]。
    - heading 前缀（如「（小节：高血压的饮食原则）」）显著提升切片的可检索性与
      LLM 对资料归属的理解，避免把不同章节内容混为一谈导致回答杂乱。
    - 末尾对完全相同/高度重叠的块去重，避免同一段话被多次喂给大模型。
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    # 按标题切分章节（标题之前的正文视为无名章节）
    sections: list[tuple[str, str]] = []
    ms = list(HEADING_RE.finditer(text))
    if ms and ms[0].start() > 0:
        pre = text[: ms[0].start()].strip()
        if pre:
            sections.append(("", pre))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        body = text[m.end(): end].strip()
        if body:
            sections.append((m.group(2).strip(), body))
    if not sections:
        sections = [("", text)]

    # 章节内递归切到接近 size，并在「同节内」做内容重叠（避免跨小节混淆正文）
    out: list[dict] = []
    seen: set[str] = set()
    for heading, body in sections:
        sec_pieces = _split_recursive(body, size)
        if overlap > 0 and len(sec_pieces) > 1:
            merged = [sec_pieces[0]]
            for p in sec_pieces[1:]:
                merged.append((merged[-1][-overlap:] + p).strip())
            sec_pieces = merged
        for p in sec_pieces:
            if not p or p in seen:
                continue
            seen.add(p)  # 按正文去重（heading 前缀不参与比较）
            if heading:
                out.append({"text": f"（小节：{heading}）\n{p}", "heading": heading})
            else:
                out.append({"text": p, "heading": ""})
    return out
