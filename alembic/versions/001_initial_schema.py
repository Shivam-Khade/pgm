"""001 initial schema

Revision ID: 001
Revises: None
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("identification_budget_bits", sa.Float, nullable=False, server_default="20.0"),
        sa.Column("k_min", sa.Integer, nullable=False, server_default="100"),
        sa.Column("config_json", JSON, nullable=False, server_default="{}"),
    )

    # Memories
    op.create_table(
        "memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("slot_key", sa.String(255), nullable=False),
        sa.Column("tier", sa.Integer, nullable=False, server_default="0"),
        sa.Column("current_level", sa.Integer, nullable=False, server_default="0"),
        sa.Column("current_text", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("importance", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("user_pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("pin_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_decay_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", UUID(as_uuid=True), nullable=True),
        sa.Column("embedding_json", JSON, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_memories_user_category", "memories", ["user_id", "category"])
    op.create_index("ix_memories_user_slot", "memories", ["user_id", "category", "slot_key"])
    op.create_index("ix_memories_status", "memories", ["status"])

    # Ladders
    op.create_table(
        "ladders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("memory_id", UUID(as_uuid=True), nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("text_hash", sa.String(64), nullable=True),
        sa.Column("population_fraction", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("info_bits", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("source", sa.String(20), nullable=False, server_default="llm"),
        sa.Column("verification_json", JSON, nullable=False, server_default="{}"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ladders_memory_level", "ladders", ["memory_id", "level"], unique=True)

    # Memory events
    op.create_table(
        "memory_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("memory_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("from_level", sa.Integer, nullable=True),
        sa.Column("to_level", sa.Integer, nullable=True),
        sa.Column("reason_json", JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="CASCADE"),
    )

    # Risk snapshots
    op.create_table(
        "risk_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("k_hat", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("r_agg_bits", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("quasi_identifiers_json", JSON, nullable=False, server_default="{}"),
    )

    # Eval runs
    op.create_table(
        "eval_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("config_json", JSON, nullable=False, server_default="{}"),
        sa.Column("results_json", JSON, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("eval_runs")
    op.drop_table("risk_snapshots")
    op.drop_table("memory_events")
    op.drop_table("ladders")
    op.drop_table("memories")
    op.drop_table("users")
