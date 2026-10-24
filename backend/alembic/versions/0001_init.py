"""initial operational tables

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

J = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("state", J, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tool_trace", J, nullable=True),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("module", sa.String(40), nullable=False),
        sa.Column("record_id", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("field_names", J, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_audit_logs_session_id", "audit_logs", ["session_id"])
    op.create_index("ix_audit_logs_idempotency_key", "audit_logs", ["idempotency_key"])
    op.create_table(
        "retry_queue",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("payload", J, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("next_attempt_at", TS, nullable=False),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_retry_queue_status", "retry_queue", ["status"])


def downgrade() -> None:
    for t in ("retry_queue", "audit_logs", "chat_messages", "chat_sessions"):
        op.drop_table(t)
