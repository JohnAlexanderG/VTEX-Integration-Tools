"""
SQLAlchemy ORM models: Tenant, User, TenantConfig.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    superadmin = "superadmin"   # Laburu Agencia — acceso total
    admin      = "admin"        # Admin del tenant — gestiona su cuenta
    operator   = "operator"     # Operador — ejecuta pipelines/tools


# ─────────────────────────────────────────────────────────────────────────────
# Tenant
# ─────────────────────────────────────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    slug       = Column(String(50),  nullable=False, unique=True, index=True)
    is_active  = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    users  = relationship("User",         back_populates="tenant", cascade="all, delete-orphan")
    config = relationship("TenantConfig", back_populates="tenant", uselist=False,
                          cascade="all, delete-orphan")
    permissions = relationship("TenantModulePermission", back_populates="tenant",
                               cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# User
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_tenant_username"),
    )

    id              = Column(Integer, primary_key=True, index=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    username        = Column(String(50),  nullable=False)
    email           = Column(String(150))
    hashed_password = Column(Text, nullable=False)
    role            = Column(SAEnum(UserRole), nullable=False, default=UserRole.operator)
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


# ─────────────────────────────────────────────────────────────────────────────
# TenantConfig  (reemplaza el .env global — credenciales por tenant)
# ─────────────────────────────────────────────────────────────────────────────

class TenantConfig(Base):
    __tablename__ = "tenant_config"

    id                = Column(Integer, primary_key=True, index=True)
    tenant_id         = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                               nullable=False, unique=True, index=True)

    # VTEX
    vtex_account_name = Column(String(100))
    vtex_environment  = Column(String(50), default="vtexcommercestable")
    vtex_api_key      = Column(Text)      # guardado en texto plano (cifrar con FERNET_KEY)
    vtex_api_token    = Column(Text)      # cifrado con Fernet

    # FTP
    ftp_server        = Column(String(150))
    ftp_user          = Column(String(100))
    ftp_password      = Column(Text)      # cifrado con Fernet
    ftp_port          = Column(Integer, default=21)

    # AWS Lambda
    lambda_function   = Column(String(100))
    aws_region        = Column(String(50), default="us-east-1")

    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="config")


# ─────────────────────────────────────────────────────────────────────────────
# TenantModulePermission
# ─────────────────────────────────────────────────────────────────────────────

class TenantModulePermission(Base):
    __tablename__ = "tenant_module_permissions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_key", name="uq_tenant_module_permission"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    tenant_id  = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    module_key = Column(String(100), nullable=False)
    enabled    = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="permissions")
