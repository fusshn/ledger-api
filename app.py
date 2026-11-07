"""個人記帳本 RESTful API。

目前只有健康檢查端點。記帳相關的路由與資料表之後再加，
資料表設計見 docs/資料表設計.md。
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from database_url import normalize_database_url
from extensions import db


def api_response(code, message, data=None):
    """統一回應封裝：{"code": ..., "message": ..., "data": ...}

    code 與 HTTP 狀態碼相同。
    """
    return jsonify({"code": code, "message": message, "data": data}), code


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_app():
    app = Flask(__name__)
    app.json.ensure_ascii = False  # 讓中文直接顯示，而非 \uXXXX 跳脫字元

    # 本機開發：把專案目錄 .env 的值載入環境變數。
    # override=False：程序環境已經有的變數優先，.env 不會蓋掉它。
    # Vercel 上沒有 .env，這行不做任何事，照樣讀平台設定的環境變數。
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "缺少環境變數 DATABASE_URL。請設定 PostgreSQL 連線字串後再啟動，"
            "格式見 .env.example。"
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(database_url)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,  # 取用連線前先確認它還活著
        "connect_args": {"connect_timeout": 5},  # 連不上時 5 秒內放棄
    }
    db.init_app(app)

    register_routes(app)
    register_error_handlers(app)
    return app


def register_routes(app):
    @app.get("/api/health")
    def health_check():
        # 不查資料庫：資料庫離線時這裡仍回 200。
        return api_response(
            200,
            "伺服器運作正常，測試正常可以進行其他任務。",
            {"status": "ok", "time": now_iso()},
        )

    @app.get("/api/health/db")
    def health_check_db():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            # 原始錯誤只寫進伺服器日誌，不回給呼叫端。
            app.logger.exception("資料庫健康檢查失敗")
            return api_response(500, "資料庫暫時連不上")
        return api_response(200, "資料庫連線正常", {"status": "ok"})


def register_error_handlers(app):
    @app.errorhandler(404)
    def handle_not_found(_e):
        return api_response(404, "找不到這一筆")

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return api_response(e.code, e.description)

    @app.errorhandler(Exception)
    def handle_unexpected_exception(_e):
        app.logger.exception("Unhandled exception")
        return api_response(500, "伺服器內部錯誤")


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
