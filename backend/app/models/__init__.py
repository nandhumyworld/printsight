"""ORM model package.

Importing from this module ensures every mapped class is registered with
``Base.metadata`` so that Alembic's autogenerate (and ``Base.metadata.create_all``
in tests) can discover all tables.
"""

from app.models.user import User, UserRole, RefreshToken
from app.models.printer import Printer, PrinterApiKey
from app.models.paper import Paper, PrinterPaper
from app.models.toner import Toner, TonerType, TonerReplacementLog
from app.models.upload import (
    UploadBatch,
    UploadSource,
    UploadStatus,
    PrintJob,
)
from app.models.notification import NotificationConfig
from app.models.webhook import WebhookConfig, WebhookDeliveryLog

__all__ = [
    "User",
    "UserRole",
    "RefreshToken",
    "Printer",
    "PrinterApiKey",
    "Paper",
    "PrinterPaper",
    "Toner",
    "TonerType",
    "TonerReplacementLog",
    "UploadBatch",
    "UploadSource",
    "UploadStatus",
    "PrintJob",
    "NotificationConfig",
    "WebhookConfig",
    "WebhookDeliveryLog",
]
