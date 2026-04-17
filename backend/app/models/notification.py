"""Notification configuration model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    email_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telegram_bot_token: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    high_cost_threshold: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    toner_low_pages_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=500, server_default="500"
    )
    toner_yield_warning_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=70, server_default="70"
    )
    monthly_report_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    weekly_summary_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="notification_config"
    )
