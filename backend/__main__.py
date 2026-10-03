"""
后端启动入口：python -m backend  （从项目根目录执行）

等效于直接运行 app.main()，会自动建库建表、播种演示数据并启动 uvicorn（FastAPI）。
"""
from backend.app import main

if __name__ == "__main__":
    main()
