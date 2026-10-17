"""任務管理系統（Tasks）最小可行 RESTful API。

資料儲存於記憶體內清單，伺服器重啟後即重置。
"""

from datetime import datetime, timezone

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.json.ensure_ascii = False  # 讓中文直接顯示，而非 \uXXXX 跳脫字元

# ---------------------------------------------------------------------------
# 記憶體內模擬資料
# ---------------------------------------------------------------------------
tasks = [
    {
        "id": 1,
        "title": "建立 Flask 專案",
        "description": "初始化虛擬環境並安裝 Flask",
        "completed": True,
        "created_at": "2026-10-17T00:00:00+00:00",
    },
    {
        "id": 2,
        "title": "實作任務 API",
        "description": "完成 GET 與 POST 端點",
        "completed": False,
        "created_at": "2026-10-17T00:00:00+00:00",
    },
]
next_id = 3


def api_response(status, message, data=None, code=200):
    """統一回應封裝：{"status": ..., "message": ..., "data": ...}"""
    return jsonify({"status": status, "message": message, "data": data}), code


def success(message, data=None, code=200):
    return api_response("success", message, data, code)


def error(message, code):
    return api_response("error", message, None, code)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 端點
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    return success("伺服器運行正常", {"server": "running", "time": now_iso()})


@app.get("/api/tasks")
def list_tasks():
    return success("成功取得任務清單", tasks)


@app.post("/api/tasks")
def create_task():
    global next_id

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須為合法的 JSON 物件", 400)

    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        return error("缺少必填欄位 title", 400)

    description = payload.get("description", "")
    if description is None:
        description = ""
    if not isinstance(description, str):
        return error("description 欄位必須為字串", 400)

    task = {
        "id": next_id,
        "title": title.strip(),
        "description": description.strip(),
        "completed": False,
        "created_at": now_iso(),
    }
    tasks.append(task)
    next_id += 1

    return success("任務新增成功", task, 201)


@app.get("/api/tasks/<int:task_id>")
def get_task(task_id):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return error(f"找不到 ID 為 {task_id} 的任務", 404)
    return success("成功取得任務", task)


# ---------------------------------------------------------------------------
# 錯誤處理：確保所有錯誤皆回傳統一 JSON 格式
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def handle_not_found(_e):
    return error("找不到請求的資源路徑", 404)


@app.errorhandler(HTTPException)
def handle_http_exception(e):
    return error(e.description, e.code)


@app.errorhandler(Exception)
def handle_unexpected_exception(_e):
    app.logger.exception("Unhandled exception")
    return error("伺服器內部錯誤", 500)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
