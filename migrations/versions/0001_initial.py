"""Initial schema.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("species", sa.String(length=50), nullable=False),
        sa.Column("breed", sa.String(length=100), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pet_id", sa.String(length=36), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "feeding",
                "walk",
                "symptom",
                "wellbeing",
                "training",
                "medication",
                "weight",
                "vet_visit",
                "note",
                name="entrytype",
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pet_id"], ["pets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_entries_occurred_at"), "entries", ["occurred_at"], unique=False)
    op.create_index(op.f("ix_entries_pet_id"), "entries", ["pet_id"], unique=False)
    op.create_index(op.f("ix_entries_type"), "entries", ["type"], unique=False)
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entry_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(op.f("ix_attachments_entry_id"), "attachments", ["entry_id"], unique=False)
    op.create_index(op.f("ix_attachments_sha256"), "attachments", ["sha256"], unique=False)


def downgrade() -> None:
    op.drop_table("attachments")
    op.drop_table("entries")
    op.drop_table("pets")
