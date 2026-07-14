"""Compatibility entrypoint.

The real Flask application lives in server.py. Render starts it with
`gunicorn server:app`, which prevents accidental circular imports when a test
file is mistakenly named app.py.
"""

from server import (  # noqa: F401
    LinkItem,
    Payment,
    PendingCheckout,
    User,
    app,
    create_app,
    db,
)

__all__ = [
    "app",
    "create_app",
    "db",
    "User",
    "LinkItem",
    "Payment",
    "PendingCheckout",
]
