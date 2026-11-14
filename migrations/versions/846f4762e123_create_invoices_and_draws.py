"""create invoices, invoice_items, draw_periods, draw_prizes

Revision ID: 846f4762e123
Revises: ad38fcafabd0
Create Date: 2026-11-14 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "846f4762e123"
down_revision: Union[str, Sequence[str], None] = "ad38fcafabd0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps():
    # created_at 由資料庫在插入時填 now()；timestamptz 內部一律存 UTC。
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "invoices",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=True), primary_key=True
        ),
        sa.Column("number", sa.CHAR(10), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "currency", sa.CHAR(3), nullable=False, server_default=sa.text("'TWD'")
        ),
        sa.Column("fx_rate_to_twd", sa.Numeric(18, 8), nullable=False),
        sa.Column("random_code", sa.CHAR(4), nullable=True),
        sa.Column("seller_name", sa.Text(), nullable=True),
        sa.Column("seller_ban", sa.CHAR(8), nullable=True),
        sa.Column(
            "prize_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unchecked'"),
        ),
        *_timestamps(),
        sa.UniqueConstraint("number", name="uq_invoices_number"),
        sa.CheckConstraint(
            "number ~ '^[A-Z]{2}[0-9]{8}$'", name="ck_invoices_number"
        ),
        sa.CheckConstraint("amount > 0", name="ck_invoices_amount_positive"),
        sa.CheckConstraint(
            "kind IN ('paper', 'electronic')", name="ck_invoices_kind"
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_invoices_currency"),
        sa.CheckConstraint(
            "fx_rate_to_twd > 0", name="ck_invoices_fx_rate_positive"
        ),
        sa.CheckConstraint(
            "currency <> 'TWD' OR fx_rate_to_twd = 1",
            name="ck_invoices_twd_rate_one",
        ),
        sa.CheckConstraint(
            "random_code ~ '^[0-9]{4}$'", name="ck_invoices_random_code"
        ),
        sa.CheckConstraint(
            "seller_ban ~ '^[0-9]{8}$'", name="ck_invoices_seller_ban"
        ),
        sa.CheckConstraint(
            "prize_status IN ('unchecked', 'lost', 'won', 'claimed', 'void')",
            name="ck_invoices_prize_status",
        ),
    )

    op.create_table(
        "invoice_items",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=True), primary_key=True
        ),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_amount", sa.Numeric(18, 4), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_invoice_items_invoice_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "btrim(name) <> ''", name="ck_invoice_items_name_not_blank"
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_invoice_items_quantity_positive"
        ),
        sa.CheckConstraint(
            "unit_price > 0", name="ck_invoice_items_unit_price_positive"
        ),
        sa.CheckConstraint(
            "line_amount > 0", name="ck_invoice_items_line_amount_positive"
        ),
    )
    # PostgreSQL 不會自動替外鍵建索引；查品項與連動刪除都會用到。
    op.create_index(
        "ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"]
    )

    op.create_table(
        "draw_periods",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=True), primary_key=True
        ),
        sa.Column("period_key", sa.CHAR(6), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("period_key", name="uq_draw_periods_period_key"),
        sa.CheckConstraint(
            "period_key ~ '^[0-9]{4}(01|03|05|07|09|11)$'",
            name="ck_draw_periods_period_key",
        ),
    )

    op.create_table(
        "draw_prizes",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=True), primary_key=True
        ),
        sa.Column("draw_period_id", sa.BigInteger(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("matching_number", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["draw_period_id"],
            ["draw_periods.id"],
            name="fk_draw_prizes_draw_period_id",
            ondelete="CASCADE",
        ),
        # 以 draw_period_id 開頭，同時充當外鍵索引。
        sa.UniqueConstraint(
            "draw_period_id",
            "tier",
            "matching_number",
            name="uq_draw_prizes_period_tier_number",
        ),
        sa.CheckConstraint(
            "tier IN ('special', 'grand', 'first', 'second', 'third', "
            "'fourth', 'fifth', 'sixth', 'extra_sixth')",
            name="ck_draw_prizes_tier",
        ),
        sa.CheckConstraint(
            "matching_number ~ '^[0-9]{3,8}$'",
            name="ck_draw_prizes_matching_number",
        ),
        sa.CheckConstraint(
            "amount >= 0", name="ck_draw_prizes_amount_non_negative"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("draw_prizes")
    op.drop_table("draw_periods")
    op.drop_index("ix_invoice_items_invoice_id", table_name="invoice_items")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
