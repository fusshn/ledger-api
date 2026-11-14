"""SQLAlchemy 模型。

這個模組只依賴 extensions，不可以 import app：
app.py 在模組層級執行 create_app()，import 它會要求 DATABASE_URL，
之後 app 若 import 這裡也會形成循環匯入。

約束名稱與 migrations/versions 裡的遷移一致，修改時兩邊要一起改。
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db

ACCOUNT_KINDS = ("cash", "bank", "credit_card", "broker")


def utc_now():
    return datetime.now(timezone.utc)


class TimestampMixin:
    # 插入時由資料庫填 now()。timestamptz 內部一律存 UTC。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # 資料庫不會自動改寫這個欄位。ORM 送出 UPDATE 時由程式填入當下 UTC；
    # 插入時保持空值。
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )


class Account(TimestampMixin, db.Model):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("name", name="uq_accounts_name"),
        CheckConstraint("btrim(name) <> ''", name="ck_accounts_name_not_blank"),
        CheckConstraint(
            "kind IN ('cash', 'bank', 'credit_card', 'broker')",
            name="ck_accounts_kind",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_accounts_currency"),
        CheckConstraint(
            "statement_day BETWEEN 1 AND 31", name="ck_accounts_statement_day"
        ),
        CheckConstraint("payment_day BETWEEN 1 AND 31", name="ck_accounts_payment_day"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3),
        nullable=False,
        server_default=text("'TWD'"),
    )
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    statement_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    payment_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    transfers_out: Mapped[list["Transfer"]] = relationship(
        back_populates="from_account", foreign_keys="Transfer.from_account_id"
    )
    transfers_in: Mapped[list["Transfer"]] = relationship(
        back_populates="to_account", foreign_keys="Transfer.to_account_id"
    )

    def __repr__(self):
        return f"<Account {self.id} {self.name!r}>"


class Transfer(TimestampMixin, db.Model):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transfers_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_transfers_currency"),
        CheckConstraint("fx_rate_to_twd > 0", name="ck_transfers_fx_rate_positive"),
        CheckConstraint(
            "currency <> 'TWD' OR fx_rate_to_twd = 1", name="ck_transfers_twd_rate_one"
        ),
        CheckConstraint(
            "from_account_id <> to_account_id", name="ck_transfers_distinct_accounts"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    transferred_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False
    )
    fx_rate_to_twd: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    from_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "accounts.id", ondelete="RESTRICT", name="fk_transfers_from_account_id"
        ),
        nullable=False,
        index=True,
    )
    to_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "accounts.id", ondelete="RESTRICT", name="fk_transfers_to_account_id"
        ),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    from_account: Mapped[Account] = relationship(
        back_populates="transfers_out", foreign_keys=[from_account_id]
    )
    to_account: Mapped[Account] = relationship(
        back_populates="transfers_in", foreign_keys=[to_account_id]
    )

    def __repr__(self):
        return f"<Transfer {self.id} {self.from_account_id}->{self.to_account_id}>"
