# -*- coding: utf-8 -*-
"""Architecture guard tests: ORM model registration coverage.

Ensures that register_orm_models() registers all required tables
so that the application starts with a complete schema.
"""

import pytest

REQUIRED_TABLES = {"channels", "chat_sessions", "chat_messages"}


class TestOrmModelRegistration:
    """Ensure register_orm_models() registers all required tables."""

    def test_register_orm_models_registers_required_tables(self):
        """After register_orm_models(), Base.metadata must contain core tables."""
        from src.core.database import Base, register_orm_models

        register_orm_models()
        tables = set(Base.metadata.tables.keys())

        missing = REQUIRED_TABLES - tables
        if missing:
            pytest.fail(
                f"register_orm_models() did not register tables: {missing}\n"
                f"Registered tables: {sorted(tables)}"
            )
