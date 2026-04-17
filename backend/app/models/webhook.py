"""Webhook configuration and delivery log models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    events: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    owner: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="webhook_configs"
    )
    delivery_logs: Mapped[List["WebhookDeliveryLog"]] = relationship(
        "WebhookDeliveryLog",
        back_populates="webhook_config",
        cascade="all, delete-orphan",
    )


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    webhook_config_id: Mapped[int] = mapped_column(
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    failed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    webhook_config: Mapped["WebhookConfig"] = relationship(
        "WebhookConfig", back_populates="delivery_logs"
    )
