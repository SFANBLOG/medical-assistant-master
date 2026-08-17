"""API 蓝图注册。"""
from flask import Blueprint

from api.decorators import health_bp  # noqa: F401
from api.auth import auth_bp
from api.kb import kb_bp
from api.chat import chat_bp
from api.dashboard import dashboard_bp
from api.patient import patient_bp
from api.doctor import doctor_bp
from api.nurse import nurse_bp
from api.schedule import schedule_bp
from api.admin import admin_bp


def register_blueprints(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(kb_bp, url_prefix="/api/kb")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(patient_bp, url_prefix="/api/patient")
    app.register_blueprint(doctor_bp, url_prefix="/api/doctor")
    app.register_blueprint(nurse_bp, url_prefix="/api/nurse")
    app.register_blueprint(schedule_bp, url_prefix="/api/schedule")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
