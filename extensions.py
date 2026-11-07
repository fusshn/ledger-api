"""Flask 擴充套件。這裡只建立物件，不綁定 Flask 實例。"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
