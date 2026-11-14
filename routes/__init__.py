"""API 路由。每個資源一個 Blueprint，由 register_blueprints 掛到 app。"""

from routes.accounts import bp as accounts_bp
from routes.transfers import bp as transfers_bp


def register_blueprints(app):
    app.register_blueprint(accounts_bp)
    app.register_blueprint(transfers_bp)
