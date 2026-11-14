"""個人記帳本 RESTful API。

目前有健康檢查、帳戶（/api/accounts）與移轉（/api/transfers）。
資料表設計見 docs/資料表設計.md。
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import HTTPException, NotFound

from database_url import normalize_database_url
from extensions import db
from responses import api_response, now_iso
from routes import register_blueprints
from validation import ValidationError

# 資料庫約束名稱 → 回給呼叫端的說明。名稱與 models.py、遷移檔一致。
CONSTRAINT_MESSAGES = {
    "uq_accounts_name": ("name", "帳戶名稱已經存在"),
    "fk_transfers_from_account_id": ("from_account_id", "找不到這個帳戶"),
    "fk_transfers_to_account_id": ("to_account_id", "找不到這個帳戶"),
}
# PostgreSQL SQLSTATE → HTTP 狀態碼
SQLSTATE_STATUS = {
    "23505": (409, "資料重複"),  # unique_violation
    "23503": (422, "參照的資料不存在或仍被使用"),  # foreign_key_violation
    "23514": (400, "輸入資料不符合規則"),  # check_violation
    "23502": (400, "缺少必填欄位"),  # not_null_violation
}


def create_app():
    app = Flask(__name__)
    app.json.ensure_ascii = False  # 讓中文直接顯示，而非 \uXXXX 跳脫字元
    # app.url_map.strict_slashes = False  # 網址結尾多一個斜線也能對到路由

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
    register_blueprints(app)
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
    def handle_not_found(e):
        # 路由用 abort(404, description=...) 指定的訊息照原樣回傳。
        if e.description and e.description != NotFound.description:
            return api_response(404, e.description)
        return api_response(404, "找不到這一筆")

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        return api_response(e.status, e.message, {"errors": e.errors})

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        # API 先檢查過，這裡處理的是同時寫入等少數情況，交由資料庫約束把關。
        db.session.rollback()
        orig = getattr(e, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None)
        diag = getattr(orig, "diag", None)
        constraint = getattr(diag, "constraint_name", None)
        status, message = SQLSTATE_STATUS.get(sqlstate, (500, "伺服器內部錯誤"))
        if status == 500:
            app.logger.exception("Unhandled integrity error")
            return api_response(status, message)
        errors = None
        if constraint in CONSTRAINT_MESSAGES:
            field, reason = CONSTRAINT_MESSAGES[constraint]
            errors = {field: reason}
            message = reason
        elif constraint:
            errors = {"constraint": constraint}
        return api_response(status, message, {"errors": errors} if errors else None)

    @app.errorhandler(OperationalError)
    def handle_operational_error(_e):
        # 連不上資料庫、連線中斷或逾時。原始錯誤只寫進伺服器日誌。
        db.session.rollback()
        app.logger.exception("資料庫操作失敗")
        return api_response(500, "資料庫暫時連不上，請稍後再試")

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
