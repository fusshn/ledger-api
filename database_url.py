"""DATABASE_URL 的共用處理，app.py 與 migrations/env.py 都用這裡。"""


def normalize_database_url(url):
    """把連線字串整理成 SQLAlchemy 接受的格式。

    有些服務給的是 postgres:// 開頭，SQLAlchemy 只接受 postgresql://。
    """
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url
