"""
Agent 工具抽象层（Tool Abstraction）。


每个工具对外暴露：
  - name        : 工具名（LLM 调用时使用的标识）
  - description : 给 LLM 看的自然语言说明（决定它何时被选用）
  - parameters  : JSON Schema，描述入参
  - run(state, **kwargs) -> str : 执行工具，返回「观察(observation)」文本

工具通过 run() 的 state 参数读取调用方注入的上下文
（role / user_id / kb_id / 最近一次检索结果 last_hits 等），
从而在不破坏无状态接口的前提下访问用户态与共享记忆。
"""
import json
from typing import Callable, Optional

import requests

from backend import config
from backend.rag.retriever import retrieve, build_context
from backend.rag.llm import _clean_answer_text
from backend.utils.db import fetchall, fetchone, execute


class Tool:
    """单个工具的定义与执行包装。"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        func: Callable,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func

    def run(self, state: dict, **kwargs) -> str:
        """执行工具。state 为编排器维护的共享上下文。"""
        return self.func(state, **kwargs)

    def to_openai_schema(self) -> dict:
        """转为 OpenAI 函数调用所需的 tool 描述。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---------------------------------------------------------------------------
# 工具实现
# ---------------------------------------------------------------------------

def _search_knowledge(state: dict, query: str, top_k: int = 5) -> str:
    """检索医学知识库，返回最相关片段（带来源与相似度）。"""
    hits = retrieve(
        query,
        state.get("role", "public"),
        state.get("user_id", 0),
        kb_id=state.get("kb_id"),
        top_k=int(top_k) if top_k else 5,
    )
    state["last_hits"] = hits  # 供最终回答构建引用
    if not hits:
        return "未检索到与问题相关的知识库文档。"
    lines = []
    for i, h in enumerate(hits, 1):
        snippet = _clean_answer_text(h["text"])[:200]
        lines.append(
            f"[{i}] 来源《{h.get('filename', '')}》 相关度 {h['similarity']:.2f}：{snippet}"
        )
    return "\n".join(lines)


def _reverse_geocode(state: dict, lat: float, lon: float) -> str:
    """经纬度反查城市名（BigDataCloud 免费接口，无需 key）。"""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return "缺少或非法的经纬度参数（lat/lon），无法反查城市。"
    try:
        url = "https://api.bigdatacloud.net/data/reverse-geocode-client"
        r = requests.get(
            url,
            params={"latitude": lat, "longitude": lon, "localityLanguage": "zh"},
            timeout=8,
        )
        r.raise_for_status()
        d = r.json()
        city = d.get("city") or d.get("locality") or d.get("principalSubdivision") or "未知城市"
        return f"城市：{city}；省份：{d.get('principalSubdivision', '')}；国家：{d.get('countryName', '')}"
    except Exception as e:  # noqa: BLE001
        return f"反查城市失败：{e}"


def _get_weather(state: dict, lat: float, lon: float) -> str:
    """根据经纬度获取当前天气（Open-Meteo，无需 key），并尽量反查城市名。"""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return "缺少或非法的经纬度参数（lat/lon），无法获取天气。可先调用 reverse_geocode 或在前端定位后传入。"
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        r = requests.get(
            url,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
                "forecast_days": 1,
            },
            timeout=8,
        )
        r.raise_for_status()
        d = r.json()
        cur = d.get("current", {})
        daily = (d.get("daily") or {})
        city = _reverse_geocode(state, lat, lon)
        t_now = cur.get("temperature_2m")
        hum = cur.get("relative_humidity_2m")
        code = cur.get("weather_code")
        tmax = (daily.get("temperature_2m_max") or ["-"])[0]
        tmin = (daily.get("temperature_2m_min") or ["-"])[0]
        return (
            f"{city}；当前气温 {t_now}°C，湿度 {hum}%，天气代码 {code}；"
            f"今日最高 {tmax}°C / 最低 {tmin}°C。"
        )
    except Exception as e:  # noqa: BLE001
        return f"获取天气失败：{e}"


def _query_hospitalizations(state: dict, keyword: str) -> str:
    """按患者姓名 / 科室 / 诊断查询住院信息。"""
    like = f"%{keyword}%"
    rows = fetchall(
        """
        SELECT h.id, u.name AS patient_name, h.department, h.ward,
               h.admit_date, h.discharge_date, h.diagnosis
        FROM hospitalizations h
        LEFT JOIN users u ON h.patient_id = u.id
        WHERE u.name LIKE %s OR h.department LIKE %s OR h.diagnosis LIKE %s
        ORDER BY h.admit_date DESC
        LIMIT 10
        """,
        (like, like, like),
    )
    if not rows:
        return f"未查询到与「{keyword}」相关的住院信息。"
    lines = []
    for r in rows:
        dis = r.get("discharge_date") or "在院"
        lines.append(
            f"住院号{r['id']}：患者 {r.get('patient_name','?')}，科室 {r.get('department','')}"
            f"，病房 {r.get('ward','')}，诊断 {r.get('diagnosis','')}，"
            f"入院 {r.get('admit_date')}，出院 {dis}。"
        )
    return "\n".join(lines)


def _query_appointments(state: dict, keyword: str) -> str:
    """按患者姓名 / 科室查询预约信息。"""
    like = f"%{keyword}%"
    rows = fetchall(
        """
        SELECT a.id, u.name AS patient_name, a.department, a.appointment_time, a.status, a.reason
        FROM appointments a
        LEFT JOIN users u ON a.patient_id = u.id
        WHERE u.name LIKE %s OR a.department LIKE %s
        ORDER BY a.appointment_time DESC
        LIMIT 10
        """,
        (like, like),
    )
    if not rows:
        return f"未查询到与「{keyword}」相关的预约信息。"
    lines = []
    for r in rows:
        lines.append(
            f"预约号{r['id']}：患者 {r.get('patient_name','?')}，科室 {r.get('department','')}"
            f"，时间 {r.get('appointment_time')}，状态 {r.get('status','')}，事由 {r.get('reason','')}。"
        )
    return "\n".join(lines)


# 常见科室分诊参考（内置知识，无需外部表；用于导诊智能体）
_DEPARTMENTS = [
    ("急诊科", "突发、危重、外伤、意识障碍等紧急情况"),
    ("内科", "感冒发热、咳嗽、胃肠不适、慢性病管理"),
    ("心血管内科", "胸痛、心慌、高血压、胸闷"),
    ("神经内科", "头痛、头晕、肢体麻木、疑似中风"),
    ("呼吸内科", "咳嗽、哮喘、呼吸困难、咳痰"),
    ("消化内科", "腹痛、腹泻、反酸、食欲不振"),
    ("骨科", "骨折、关节痛、腰背痛、跌打损伤"),
    ("皮肤科", "皮疹、瘙痒、过敏、痤疮"),
    ("儿科", "婴幼儿及儿童常见病"),
    ("妇产科", "孕期、月经、妇科疾病"),
    ("眼科 / 耳鼻喉科", "视力、耳痛、咽喉不适"),
    ("精神心理科", "焦虑、失眠、情绪问题"),
]


def _triage_departments(state: dict, symptom: str = "") -> str:
    """根据症状推荐就诊科室（内置分诊知识，无需外部表）。"""
    lines = ["常见科室分诊参考："]
    for name, desc in _DEPARTMENTS:
        lines.append(f"- {name}：{desc}")
    if symptom:
        lines.append(
            f"\n您提到的症状「{symptom}」建议优先到对应科室就诊；"
            "若症状紧急或持续加重，请直接前往急诊科。"
        )
    lines.append("温馨提示：最终就诊科室以医院现场分诊与医生判断为准。")
    return "\n".join(lines)


def _query_patient_records(state: dict, keyword: str = "") -> str:
    """查询病历汇总：当前用户（或按关键词）的住院记录。

    对应《Agent项目要点.md》P2：把长期记忆作为可被 Agent 调用的工具。
    """
    user_id = state.get("user_id")
    if keyword:
        like = f"%{keyword}%"
        rows = fetchall(
            "SELECT h.id, u.name AS patient_name, h.department, h.diagnosis, h.admit_date "
            "FROM hospitalizations h LEFT JOIN users u ON h.patient_id = u.id "
            "WHERE u.name LIKE %s OR h.department LIKE %s OR h.diagnosis LIKE %s "
            "ORDER BY h.admit_date DESC LIMIT 10",
            (like, like, like),
        )
    else:
        rows = fetchall(
            "SELECT h.id, h.department, h.diagnosis, h.admit_date, h.discharge_date "
            "FROM hospitalizations h WHERE h.patient_id = %s "
            "ORDER BY h.admit_date DESC LIMIT 10",
            (user_id,),
        )
    if not rows:
        return "未查询到相关病历记录。"
    lines = []
    for r in rows:
        dis = r.get("discharge_date") or "在院"
        lines.append(
            f"住院号{r['id']}：科室 {r.get('department','')}，诊断 {r.get('diagnosis','')}，"
            f"入院 {r.get('admit_date')}，出院 {dis}。"
        )
    return "病历汇总：\n" + "\n".join(lines)


def _create_appointment(
    state: dict,
    department: str,
    date: str,
    time_slot: str,
    doctor_id: int = None,
    symptom: str = "",
    patient_name: str = "",
    patient_id: int = None,
) -> str:
    """提交预约挂号请求（写操作，需医生复核后才生效）。

    该工具**不会**直接写入 appointments 表，而是写入 appointment_requests
    （review_status='pending'），由医生在 /api/review/appointments 复核通过后才真正建单。
    这是《Agent项目要点.md》§6「动作护栏：写操作需 human_review + 审计落库」的落地。
    """
    department = (department or "").strip()
    date = (date or "").strip()
    time_slot = (time_slot or "").strip()
    if not department or not date or not time_slot:
        return "预约请求失败：科室、就诊日期、时段均为必填。"

    # 解析预约人（患者）。医护代约时必须指明患者。
    role = state.get("role", "patient")
    if role in ("doctor", "nurse", "admin"):
        pid = patient_id if isinstance(patient_id, int) else None
        if not pid and patient_name:
            row = fetchone(
                "SELECT id FROM users WHERE name LIKE %s AND role='patient' LIMIT 1",
                (f"%{patient_name}%",),
            )
            pid = row["id"] if row else None
        if not pid:
            return "预约请求失败：请指明预约患者（patient_name 或 patient_id），以便医生复核。"
    else:
        pid = patient_id if isinstance(patient_id, int) else state.get("user_id")

    payload = {
        "patient_id": pid,
        "doctor_id": doctor_id if isinstance(doctor_id, int) else None,
        "department": department,
        "date": date,
        "time_slot": time_slot,
        "symptom": (symptom or "").strip(),
    }
    execute(
        "INSERT INTO appointment_requests (conversation_id, user_id, request_json, review_status) "
        "VALUES (%s, %s, %s, 'pending')",
        (state.get("conversation_id"), pid, json.dumps(payload, ensure_ascii=False)),
    )
    req = fetchone(
        "SELECT id FROM appointment_requests WHERE user_id=%s ORDER BY id DESC LIMIT 1",
        (pid,),
    )
    req_id = req["id"] if req else "?"
    return (
        f"已生成预约请求 #{req_id}（科室：{department}，日期：{date}，时段：{time_slot}），"
        f"已提交医生复核，待批准后正式生效。请勿重复提交。"
    )


# ---------------------------------------------------------------------------
# 工具注册表
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="search_knowledge",
        description=(
            "检索医学知识库，获取与用户问题相关的权威资料片段。"
            "凡是涉及疾病、症状、用药、护理、健康知识类问题，都应先调用本工具。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词或问题"},
                "top_k": {"type": "integer", "description": "返回条数，默认 5"},
            },
            "required": ["query"],
        },
        func=_search_knowledge,
    ),
    Tool(
        name="reverse_geocode",
        description="将经纬度反查为可读的城市/地区名称，用于定位用户所在城市。",
        parameters={
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "纬度"},
                "lon": {"type": "number", "description": "经度"},
            },
            "required": ["lat", "lon"],
        },
        func=_reverse_geocode,
    ),
    Tool(
        name="get_weather",
        description="根据用户经纬度获取当前天气与今日气温（最高/最低），用于回答天气相关问题。",
        parameters={
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "纬度"},
                "lon": {"type": "number", "description": "经度"},
            },
            "required": ["lat", "lon"],
        },
        func=_get_weather,
    ),
    Tool(
        name="query_hospitalizations",
        description="按患者姓名、科室或诊断查询住院信息，用于医护咨询住院患者病情。",
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "患者姓名 / 科室 / 诊断关键词"},
            },
            "required": ["keyword"],
        },
        func=_query_hospitalizations,
    ),
    Tool(
        name="query_appointments",
        description="按患者姓名或科室查询预约信息，用于导诊或预约相关咨询。",
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "患者姓名 / 科室关键词"},
            },
            "required": ["keyword"],
        },
        func=_query_appointments,
    ),
    Tool(
        name="triage_departments",
        description="根据症状推荐就诊科室，用于导诊分流。输入症状描述，返回常见科室分诊建议。",
        parameters={
            "type": "object",
            "properties": {
                "symptom": {"type": "string", "description": "用户描述的症状/主诉"},
            },
            "required": [],
        },
        func=_triage_departments,
    ),
    Tool(
        name="query_patient_records",
        description=(
            "查询病历汇总（住院记录）。不传 keyword 时查询当前登录用户的病历；"
            "传入 keyword 时按患者姓名/科室/诊断检索。用于医生/护士智能体结合患者背景作答。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "可选：患者姓名 / 科室 / 诊断关键词"},
            },
            "required": [],
        },
        func=_query_patient_records,
    ),
    Tool(
        name="create_appointment",
        description=(
            "提交预约挂号请求（写操作，需医生复核）。将预约需求（科室/日期/时段/症状）"
            "提交给医生复核，医生批准后才会正式建立预约。适用于患者自助预约或医护代为预约。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "就诊科室，如 骨科 / 心血管内科"},
                "date": {"type": "string", "description": "就诊日期，如 2026-09-01"},
                "time_slot": {"type": "string", "description": "就诊时段，如 上午 / 09:00-09:30"},
                "doctor_id": {"type": "integer", "description": "可选：指定医生 id"},
                "symptom": {"type": "string", "description": "可选：主诉/症状"},
                "patient_name": {"type": "string", "description": "可选：医护代约时填写的患者姓名"},
                "patient_id": {"type": "integer", "description": "可选：医护代约时填写的患者 id"},
            },
            "required": ["department", "date", "time_slot"],
        },
        func=_create_appointment,
    ),
]

_TOOL_MAP = {t.name: t for t in TOOLS}


def get_tool(name: str) -> Optional[Tool]:
    return _TOOL_MAP.get(name)


def get_tool_schemas() -> list[dict]:
    return [t.to_openai_schema() for t in TOOLS]


def run_tool(state: dict, name: str, **kwargs) -> str:
    """便捷执行：编排器用它在离线/规则路径里直接调用工具。"""
    tool = _TOOL_MAP.get(name)
    if not tool:
        return f"未知工具：{name}"
    try:
        return tool.run(state, **kwargs)
    except Exception as e:  # noqa: BLE001
        return f"工具 {name} 执行出错：{e}"
