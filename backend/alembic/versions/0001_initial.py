"""Schéma initial.

Les tables de cette révision sont créées depuis les modèles tels qu'ils étaient à la sortie 1.0.
Toute évolution ultérieure doit être une révision incrémentale (op.add_column, etc.), jamais une
modification de celle-ci. Sur PostgreSQL, l'extension PostGIS est activée sauf si NV_USE_POSTGIS=false.

Revision ID: 0001
Revises:
"""
from alembic import op

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and get_settings().use_postgis:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
