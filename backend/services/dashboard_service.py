"""
仪表盘服务：系统统计数据。
"""
from backend.utils.db import fetchone, fetchall


def get_user_stats() -> dict:
    """用户统计。"""
    total = fetchone("SELECT COUNT(*) AS cnt FROM users")["cnt"]
    by_role = {}
    for r in fetchall("SELECT role, COUNT(*) AS cnt FROM users GROUP BY role"):
        by_role[r["role"]] = r["cnt"]
    return {"total": total, "by_role": by_role}


def get_kb_stats() -> dict:
    """知识库统计。"""
    kb_total = fetchone("SELECT COUNT(*) AS cnt FROM knowledge_bases")["cnt"]
    doc_total = fetchone("SELECT COUNT(*) AS cnt FROM documents")["cnt"]
    doc_ready = fetchone("SELECT COUNT(*) AS cnt FROM documents WHERE status = 'ready'")["cnt"]
    total_chunks = fetchone("SELECT COALESCE(SUM(chunk_count), 0) AS cnt FROM documents")["cnt"]
    return {
        "kb_count": kb_total,
        "doc_count": doc_total,
        "doc_ready": doc_ready,
        "total_chunks": total_chunks,
    }


def get_business_stats() -> dict:
    """业务统计。"""
    return {
        "hospitalizations": fetchone("SELECT COUNT(*) AS cnt FROM hospitalizations")["cnt"],
        "bills": fetchone("SELECT COUNT(*) AS cnt FROM bills")["cnt"],
        "appointments": fetchone("SELECT COUNT(*) AS cnt FROM appointments")["cnt"],
        "nursing_records": fetchone("SELECT COUNT(*) AS cnt FROM nursing_records")["cnt"],
        "schedules": fetchone("SELECT COUNT(*) AS cnt FROM schedules")["cnt"],
    }


def get_chat_stats() -> dict:
    """咨询统计。"""
    conv_count = fetchone("SELECT COUNT(*) AS cnt FROM conversations")["cnt"]
    msg_count = fetchone("SELECT COUNT(*) AS cnt FROM messages")["cnt"]
    citation_count = fetchone("SELECT COUNT(*) AS cnt FROM citations")["cnt"]
    return {
        "conversations": conv_count,
        "messages": msg_count,
        "citations": citation_count,
    }


def get_revenue_stats() -> dict:
    """收入统计。"""
    total = fetchone("SELECT COALESCE(SUM(amount), 0) AS total FROM bills WHERE status = 'paid'")
    paid = float(total["total"]) if total else 0
    unpaid_row = fetchone("SELECT COALESCE(SUM(amount), 0) AS total FROM bills WHERE status = 'unpaid'")
    unpaid = float(unpaid_row["total"]) if unpaid_row else 0
    return {"paid": round(paid, 2), "unpaid": round(unpaid, 2), "total": round(paid + unpaid, 2)}


def get_system_overview() -> dict:
    """系统总览。"""
    return {
        "users": get_user_stats(),
        "knowledge_bases": get_kb_stats(),
        "business": get_business_stats(),
        "chat": get_chat_stats(),
        "revenue": get_revenue_stats(),
    }


def get_patient_overview(patient_id: int) -> dict:
    """患者个人总览。"""
    hosp = fetchone("SELECT COUNT(*) AS cnt FROM hospitalizations WHERE patient_id = %s", (patient_id,))
    bills = fetchone("SELECT COUNT(*) AS cnt FROM bills WHERE patient_id = %s", (patient_id,))
    appts = fetchone("SELECT COUNT(*) AS cnt FROM appointments WHERE patient_id = %s", (patient_id,))
    convs = fetchone("SELECT COUNT(*) AS cnt FROM conversations WHERE user_id = %s", (patient_id,))

    # 消费统计
    paid_row = fetchone("SELECT COALESCE(SUM(amount), 0) AS total FROM bills WHERE patient_id = %s AND status = 'paid'", (patient_id,))
    unpaid_row = fetchone("SELECT COALESCE(SUM(amount), 0) AS total FROM bills WHERE patient_id = %s AND status = 'unpaid'", (patient_id,))

    return {
        "hospitalization_count": hosp["cnt"] if hosp else 0,
        "bill_count": bills["cnt"] if bills else 0,
        "appointment_count": appts["cnt"] if appts else 0,
        "conversation_count": convs["cnt"] if convs else 0,
        "total_paid": round(float(paid_row["total"]) if paid_row else 0, 2),
        "total_unpaid": round(float(unpaid_row["total"]) if unpaid_row else 0, 2),
    }


def get_department_distribution() -> list[dict]:
    """科室分布统计。"""
    rows = fetchall(
        "SELECT department, COUNT(*) AS count FROM hospitalizations GROUP BY department ORDER BY count DESC"
    )
    return rows


def get_bill_category_distribution() -> list[dict]:
    """消费类别分布。"""
    rows = fetchall(
        "SELECT category, COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total "
        "FROM bills GROUP BY category ORDER BY total DESC"
    )
    return rows
