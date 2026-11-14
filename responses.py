"""統一回應封裝與 JSON 序列化工具。

路由模組從這裡 import，不要 import app：app.py 會 import 路由，
反過來 import 會形成循環匯入，也會在匯入時觸發 create_app()。
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from flask import jsonify


def api_response(code, message, data=None):
    """統一回應封裝：{"code": ..., "message": ..., "data": ...}

    code 與 HTTP 狀態碼相同。
    """
    return jsonify({"code": code, "message": message, "data": data}), code


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def iso_datetime(value: datetime | None):
    """時間點一律轉成 UTC 的 ISO 8601。"""
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def iso_date(value: date | None):
    # Flask 預設會把 date 序列化成 RFC 822 字串，這裡明確輸出 YYYY-MM-DD。
    return None if value is None else value.isoformat()


def decimal_str(value: Decimal | None):
    # 金額以字串回傳，避免 JSON 浮點數失去精度。
    return None if value is None else str(value)
