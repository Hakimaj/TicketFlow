"""Seed the local database with TicketFlow demonstration fixtures.

Usage (from backend/)::

    python -m scripts.seed

Safe to run repeatedly: rows are matched by stable public identifier and
existing rows are never updated or deleted. Refuses to run in production
unless ALLOW_DEMO_SEED=true is set explicitly.
"""

from __future__ import annotations

import json
import os
import sys

from app.core.config import get_settings
from app.db.session import build_engine, build_session_factory, session_scope
from app.seed import seed_demo_data


def main() -> int:
    settings = get_settings()
    if settings.app_env == "production" and os.getenv("ALLOW_DEMO_SEED") != "true":
        print(
            "Refusing to seed demonstration data with APP_ENV=production. "
            "Set ALLOW_DEMO_SEED=true only for a deliberate demo environment.",
            file=sys.stderr,
        )
        return 2

    engine = build_engine(settings)
    factory = build_session_factory(engine)
    try:
        with session_scope(factory) as session:
            report = seed_demo_data(session)
    finally:
        engine.dispose()

    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    created = sum(report.created.values())
    print(
        f"Seed complete: {created} row(s) created, "
        f"{sum(report.skipped.values())} existing row(s) left untouched."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
