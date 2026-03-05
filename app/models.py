import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    query_params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    path_params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    response_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admin_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    config_links: Mapped[list["CustomerConfigMatrix"]] = relationship(back_populates="customer")
    notes: Mapped[list["CustomerNote"]] = relationship(back_populates="customer")


class CustomerNote(Base):
    __tablename__ = "customer_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="notes")


class PresetConfig(Base):
    __tablename__ = "preset_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    config_links: Mapped[list["CustomerConfigMatrix"]] = relationship(back_populates="preset_config")


class CustomConfig(Base):
    __tablename__ = "custom_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    config_links: Mapped[list["CustomerConfigMatrix"]] = relationship(back_populates="custom_config")


class CustomerConfigMatrix(Base):
    __tablename__ = "customer_config_matrix"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    preset_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("preset_configs.id"), nullable=True
    )
    custom_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("custom_configs.id"), nullable=True
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="config_links")
    preset_config: Mapped["PresetConfig | None"] = relationship(back_populates="config_links")
    custom_config: Mapped["CustomConfig | None"] = relationship(back_populates="config_links")
