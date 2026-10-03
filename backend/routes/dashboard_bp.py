"""仪表盘路由（FastAPI APIRouter）。"""
from fastapi import APIRouter, Depends

from backend.services import dashboard_service
from backend.utils.jwt_utils import get_current_user, require_roles

router = APIRouter()


@router.get("/overview")
def overview(user: dict = Depends(get_current_user)):
    """系统总览（管理员可见完整数据，其他角色看精简版）。"""
    if user["role"] == "admin":
        return dashboard_service.get_system_overview()
    elif user["role"] in ("patient", "public"):
        return dashboard_service.get_patient_overview(user["user_id"])
    else:
        # 医生/护士看业务统计
        return {
            "business": dashboard_service.get_business_stats(),
            "chat": dashboard_service.get_chat_stats(),
        }


@router.get("/users")
def user_stats(user: dict = Depends(require_roles("admin"))):
    return dashboard_service.get_user_stats()


@router.get("/knowledge-bases")
def kb_stats(user: dict = Depends(get_current_user)):
    return dashboard_service.get_kb_stats()


@router.get("/business")
def business_stats(user: dict = Depends(require_roles("doctor", "admin"))):
    return dashboard_service.get_business_stats()


@router.get("/chat")
def chat_stats(user: dict = Depends(get_current_user)):
    return dashboard_service.get_chat_stats()


@router.get("/revenue")
def revenue_stats(user: dict = Depends(require_roles("admin", "doctor"))):
    return dashboard_service.get_revenue_stats()


@router.get("/department-distribution")
def dept_distribution(user: dict = Depends(require_roles("doctor", "admin"))):
    return dashboard_service.get_department_distribution()


@router.get("/bill-category-distribution")
def bill_category_distribution(user: dict = Depends(require_roles("admin", "doctor"))):
    return dashboard_service.get_bill_category_distribution()
