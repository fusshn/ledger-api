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


INVOICE_KINDS = ("paper", "electronic")
INVOICE_PRIZE_STATUSES = ("unchecked", "lost", "won", "claimed", "void")
DRAW_PRIZE_TIERS = (
    "special",
    "grand",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "extra_sixth",
)


class Invoice(TimestampMixin, db.Model):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("number", name="uq_invoices_number"),
        CheckConstraint("number ~ '^[A-Z]{2}[0-9]{8}$'", name="ck_invoices_number"),
        CheckConstraint("amount > 0", name="ck_invoices_amount_positive"),
        CheckConstraint("kind IN ('paper', 'electronic')", name="ck_invoices_kind"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_invoices_currency"),
        CheckConstraint("fx_rate_to_twd > 0", name="ck_invoices_fx_rate_positive"),
        CheckConstraint(
            "currency <> 'TWD' OR fx_rate_to_twd = 1", name="ck_invoices_twd_rate_one"
        ),
        CheckConstraint(
            "random_code ~ '^[0-9]{4}$'", name="ck_invoices_random_code"
        ),
        CheckConstraint("seller_ban ~ '^[0-9]{8}$'", name="ck_invoices_seller_ban"),
        CheckConstraint(
            "prize_status IN ('unchecked', 'lost', 'won', 'claimed', 'void')",
            name="ck_invoices_prize_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    number: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'TWD'")
    )
    fx_rate_to_twd: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    random_code: Mapped[str | None] = mapped_column(CHAR(4), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_ban: Mapped[str | None] = mapped_column(CHAR(8), nullable=True)
    prize_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unchecked'")
    )

    # 刪除交給資料庫的 ON DELETE CASCADE；passive_deletes 讓 ORM 不先逐筆載入品項。
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self):
        return f"<Invoice {self.id} {self.number}>"


class InvoiceItem(TimestampMixin, db.Model):
    __tablename__ = "invoice_items"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_invoice_items_name_not_blank"),
        CheckConstraint("quantity > 0", name="ck_invoice_items_quantity_positive"),
        CheckConstraint(
            "unit_price > 0", name="ck_invoice_items_unit_price_positive"
        ),
        CheckConstraint(
            "line_amount > 0", name="ck_invoice_items_line_amount_positive"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    invoice_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "invoices.id", ondelete="CASCADE", name="fk_invoice_items_invoice_id"
        ),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="items")

    def __repr__(self):
        return f"<InvoiceItem {self.id} invoice={self.invoice_id} {self.name!r}>"


class DrawPeriod(TimestampMixin, db.Model):
    __tablename__ = "draw_periods"
    __table_args__ = (
        UniqueConstraint("period_key", name="uq_draw_periods_period_key"),
        # 期別 YYYYMM：西元年加該期第一個月（奇數月），見 docs/資料表設計.md 5.1。
        CheckConstraint(
            "period_key ~ '^[0-9]{4}(01|03|05|07|09|11)$'",
            name="ck_draw_periods_period_key",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    period_key: Mapped[str] = mapped_column(CHAR(6), nullable=False)

    prizes: Mapped[list["DrawPrize"]] = relationship(
        back_populates="draw_period", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self):
        return f"<DrawPeriod {self.id} {self.period_key}>"


class DrawPrize(TimestampMixin, db.Model):
    """某一期某個獎別的一組中獎號碼與獎金。獎金是資料，不寫死在程式裡。"""

    __tablename__ = "draw_prizes"
    __table_args__ = (
        UniqueConstraint(
            "draw_period_id",
            "tier",
            "matching_number",
            name="uq_draw_prizes_period_tier_number",
        ),
        CheckConstraint(
            "tier IN ('special', 'grand', 'first', 'second', 'third', "
            "'fourth', 'fifth', 'sixth', 'extra_sixth')",
            name="ck_draw_prizes_tier",
        ),
        # 特別獎、特獎、頭獎八碼；二獎到六獎是頭獎末 7 到 3 碼；增開六獎三碼。
        CheckConstraint(
            "matching_number ~ '^[0-9]{3,8}$'", name="ck_draw_prizes_matching_number"
        ),
        CheckConstraint("amount >= 0", name="ck_draw_prizes_amount_non_negative"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # 唯一約束以 draw_period_id 開頭，外鍵查詢直接用它，不另建索引。
    draw_period_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "draw_periods.id",
            ondelete="CASCADE",
            name="fk_draw_prizes_draw_period_id",
        ),
        nullable=False,
    )
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    matching_number: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    draw_period: Mapped[DrawPeriod] = relationship(back_populates="prizes")

    def __repr__(self):
        return f"<DrawPrize {self.id} {self.tier} {self.matching_number}>"
