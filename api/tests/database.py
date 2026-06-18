from __future__ import annotations

from sqlalchemy.orm import scoped_session, sessionmaker

scoped_session_for_testing = scoped_session(
    sessionmaker(autocommit=False, autoflush=False)
)
