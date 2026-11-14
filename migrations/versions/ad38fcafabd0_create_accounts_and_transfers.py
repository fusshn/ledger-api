"""create accounts and transfers

Revision ID: ad38fcafabd0
Revises:
Create Date: 2026-11-14 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ad38fcafabd0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "accounts",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=True), primary_key=True
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "currency", sa.CHAR(3), nullable=False, server_default=sa.text("'TWD'")
        ),
        sa.Column(
            "opening_balance",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("statement_day", sa.SmallInteger(), nullable=True),
        sa.Column("payment_day", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_accounts_name"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_accounts_name_not_blank"),
        sa.CheckConstraint(
            "kind IN ('cash', 'bank', 'credit_card', 'broker')",
            name="ck_accounts_kind",
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_accounts_currency"),
        sa.CheckConstraint(
            "statement_day BETWEEN 1 AND 31", name="ck_accounts_statement_day"
        ),
        sa.CheckConstraint(
            "payment_day BETWEEN 1 AND 31", name="ck_accounts_payment_day"
        ),
    )

    op.create_table(
        "transfers",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=True), primary_key=True
        ),
        sa.Column("transferred_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("fx_rate_to_twd", sa.Numeric(18, 8), nullable=False),
        sa.Column("from_account_id", sa.BigInteger(), nullable=False),
        sa.Column("to_account_id", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["from_account_id"],
            ["accounts.id"],
            name="fk_transfers_from_account_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_account_id"],
            ["accounts.id"],
            name="fk_transfers_to_account_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("amount > 0", name="ck_transfers_amount_positive"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_transfers_currency"),
        sa.CheckConstraint(
            "fx_rate_to_twd > 0", name="ck_transfers_fx_rate_positive"
        ),
        sa.CheckConstraint(
            "currency <> 'TWD' OR fx_rate_to_twd = 1",
            name="ck_transfers_twd_rate_one",
        ),
        sa.CheckConstraint(
            "from_account_id <> to_account_id",
            name="ck_transfers_distinct_accounts",
        ),
    )
    # PostgreSQL 不會自動替外鍵建索引；餘額查詢與 RESTRICT 檢查都會用到。
    op.create_index(
        "ix_transfers_from_account_id", "transfers", ["from_account_id"]
    )
    op.create_index("ix_transfers_to_account_id", "transfers", ["to_account_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_transfers_to_account_id", table_name="transfers")
    op.drop_index("ix_transfers_from_account_id", table_name="transfers")
    op.drop_table("transfers")
    op.drop_table("accounts")
