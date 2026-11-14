"""帳戶：/api/accounts"""

from decimal import ROUND_HALF_UP, Decimal

from flask import Blueprint, abort
from sqlalchemy import func, or_, select

from extensions import db
from models import ACCOUNT_KINDS, Account, Transfer, utc_now
from responses import api_response, decimal_str, iso_datetime
from validation import Parser, get_json_object

bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")

# 對應 numeric(18,4)
AMOUNT_DIGITS = {"int_digits": 14, "scale": 4}
TWD_QUANT = Decimal("0.0001")

# PATCH 只能改這三欄；下面這些欄位建立後就不能改。
EDITABLE_FIELDS = ("name", "statement_day", "payment_day")
IMMUTABLE_FIELDS = ("kind", "currency", "opening_balance")


def account_to_dict(account: Account):
    return {
        "id": account.id,
        "name": account.name,
        "kind": account.kind,
        "currency": account.currency,
        "opening_balance": decimal_str(account.opening_balance),
        "statement_day": account.statement_day,
        "payment_day": account.payment_day,
        "created_at": iso_datetime(account.created_at),
        "updated_at": iso_datetime(account.updated_at),
    }


def get_account_or_404(account_id):
    account = db.session.get(Account, account_id)
    if account is None:
        abort(404, description="找不到這個帳戶")
    return account


def _parse_days(parser):
    for field in ("statement_day", "payment_day"):
        parser.integer(field, nullable=True, min_value=1, max_value=31)


@bp.get("")
def list_accounts():
    accounts = db.session.scalars(select(Account).order_by(Account.id)).all()
    return api_response(200, "成功", [account_to_dict(a) for a in accounts])


@bp.post("")
def create_account():
    # 只取下面列出的欄位；客戶端送來的 id、created_at、updated_at 一律不採用。
    parser = Parser(get_json_object())
    parser.text("name", required=True)
    parser.choice("kind", ACCOUNT_KINDS, required=True)
    parser.currency("currency")
    parser.decimal("opening_balance", **AMOUNT_DIGITS)
    _parse_days(parser)
    values = parser.finish()

    # 沒送的欄位不帶進 INSERT，交給資料庫預設值（currency 'TWD'、opening_balance 0）。
    account = Account(**values)
    db.session.add(account)
    db.session.commit()  # 名稱重複等約束錯誤由 app.py 統一轉成 4xx
    # commit 後屬性已過期，下面讀取時會重新 SELECT，回傳的就是資料庫裡的那一列。
    return api_response(201, "已新增帳戶", account_to_dict(account))


@bp.get("/<int:account_id>")
def get_account(account_id):
    return api_response(200, "成功", account_to_dict(get_account_or_404(account_id)))


@bp.patch("/<int:account_id>")
def update_account(account_id):
    account = get_account_or_404(account_id)

    parser = Parser(get_json_object())
    parser.reject(IMMUTABLE_FIELDS, "建立後不可修改")
    parser.text("name")
    _parse_days(parser)
    values = parser.finish()

    if not values:
        return api_response(
            400, "沒有可更新的欄位，可修改：" + "、".join(EDITABLE_FIELDS)
        )

    for field, value in values.items():
        setattr(account, field, value)
    # 明確寫入，即使新值與舊值相同也會更新時間。
    account.updated_at = utc_now()
    db.session.commit()
    return api_response(200, "已更新帳戶", account_to_dict(account))


@bp.get("/<int:account_id>/balance")
def get_account_balance(account_id):
    account = get_account_or_404(account_id)
    return api_response(200, "成功", compute_balance(account))


def compute_balance(account: Account):
    """餘額 = 期初金額 + 轉入 − 轉出。

    台幣金額是每一筆移轉各自乘上自己的 fx_rate_to_twd 再加總。
    期初金額沒有匯率：台幣帳戶視為 1；外幣帳戶期初不是 0 時無法換算，
    台幣的期初與餘額回傳 null。
    只讀取，不寫入。
    """
    incoming = Transfer.to_account_id == account.id
    outgoing = Transfer.from_account_id == account.id
    twd_amount = Transfer.amount * Transfer.fx_rate_to_twd
    zero = Decimal(0)

    row = db.session.execute(
        select(
            func.coalesce(func.sum(Transfer.amount).filter(incoming), zero),
            func.coalesce(func.sum(Transfer.amount).filter(outgoing), zero),
            func.coalesce(func.sum(twd_amount).filter(incoming), zero),
            func.coalesce(func.sum(twd_amount).filter(outgoing), zero),
        ).where(or_(incoming, outgoing))
    ).one()
    in_amount, out_amount, in_twd, out_twd = (Decimal(v) for v in row)

    opening = account.opening_balance
    if account.currency == "TWD" or opening == 0:
        opening_twd = opening
    else:
        opening_twd = None

    def twd(value):
        if value is None:
            return None
        return str(value.quantize(TWD_QUANT, rounding=ROUND_HALF_UP))

    balance_twd = None if opening_twd is None else opening_twd + in_twd - out_twd
    return {
        "account_id": account.id,
        "currency": account.currency,
        "opening_balance": decimal_str(opening),
        "transfers_in": decimal_str(in_amount),
        "transfers_out": decimal_str(out_amount),
        "balance": decimal_str(opening + in_amount - out_amount),
        "opening_balance_twd": twd(opening_twd),
        "transfers_in_twd": twd(in_twd),
        "transfers_out_twd": twd(out_twd),
        "balance_twd": twd(balance_twd),
    }
