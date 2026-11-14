"""移轉：/api/transfers"""

from decimal import Decimal

from flask import Blueprint, abort
from sqlalchemy import select

from extensions import db
from models import Account, Transfer
from responses import api_response, decimal_str, iso_date, iso_datetime
from validation import Parser, ValidationError, get_json_object

bp = Blueprint("transfers", __name__, url_prefix="/api/transfers")


def transfer_to_dict(transfer: Transfer):
    return {
        "id": transfer.id,
        "transferred_on": iso_date(transfer.transferred_on),
        "amount": decimal_str(transfer.amount),
        "currency": transfer.currency,
        "fx_rate_to_twd": decimal_str(transfer.fx_rate_to_twd),
        "from_account_id": transfer.from_account_id,
        "to_account_id": transfer.to_account_id,
        "note": transfer.note,
        "created_at": iso_datetime(transfer.created_at),
        "updated_at": iso_datetime(transfer.updated_at),
    }


@bp.get("")
def list_transfers():
    transfers = db.session.scalars(
        select(Transfer).order_by(
            Transfer.transferred_on.desc(), Transfer.id.desc()
        )
    ).all()
    return api_response(200, "成功", [transfer_to_dict(t) for t in transfers])


@bp.get("/<int:transfer_id>")
def get_transfer(transfer_id):
    transfer = db.session.get(Transfer, transfer_id)
    if transfer is None:
        abort(404, description="找不到這筆移轉")
    return api_response(200, "成功", transfer_to_dict(transfer))


@bp.post("")
def create_transfer():
    # 只取下面列出的欄位；客戶端送來的 id、created_at、updated_at 一律不採用。
    parser = Parser(get_json_object())
    parser.date("transferred_on", required=True)
    parser.decimal("amount", required=True, positive=True, int_digits=14, scale=4)
    currency = parser.currency("currency", required=True)
    fx_rate = parser.decimal(
        "fx_rate_to_twd", required=True, positive=True, int_digits=10, scale=8
    )
    from_id = parser.integer("from_account_id", required=True, min_value=1)
    to_id = parser.integer("to_account_id", required=True, min_value=1)
    parser.text("note", nullable=True)

    if currency == "TWD" and fx_rate is not None and fx_rate != Decimal(1):
        parser.errors["fx_rate_to_twd"] = "幣別是 TWD 時匯率必須是 1"
    if from_id is not None and from_id == to_id:
        parser.errors["to_account_id"] = "轉出與轉入不可以是同一個帳戶"
    values = parser.finish()

    _check_accounts(values)

    transfer = Transfer(**values)
    db.session.add(transfer)
    db.session.commit()
    return api_response(201, "已新增移轉", transfer_to_dict(transfer))


def _check_accounts(values):
    """兩個帳戶都要存在，幣別也都要等於移轉的幣別。

    移轉只有一個金額，兩邊帳戶幣別不同時餘額會算錯，所以這裡擋下。
    """
    errors = {}
    for field in ("from_account_id", "to_account_id"):
        account = db.session.get(Account, values[field])
        if account is None:
            errors[field] = "找不到這個帳戶"
        elif account.currency != values["currency"]:
            errors[field] = (
                f"帳戶幣別是 {account.currency}，與移轉幣別 {values['currency']} 不同"
            )
    if errors:
        raise ValidationError(errors, "帳戶不存在或幣別不符", status=422)
