import enum
from sqlalchemy import Column, String, ForeignKey, Enum, Date
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin, generate_uuid

class CaseStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    RECONCILED = "RECONCILED"
    REVIEWED = "REVIEWED"
    ARCHIVED = "ARCHIVED"

class ReconciliationCase(Base, TimestampMixin):
    __tablename__ = "reconciliation_cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    created_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title = Column(String(255), nullable=False)
    case_reference = Column(String(100), nullable=False, unique=True)
    currency = Column(String(10), default="GBP", nullable=False)
    status = Column(String(50), default=CaseStatus.DRAFT.value, nullable=False)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    notes = Column(String(1000), nullable=True)

    organization = relationship("Organization", back_populates="cases")
    workspace = relationship("Workspace", back_populates="cases")
    supplier = relationship("Supplier", back_populates="cases")
    created_by = relationship("User", back_populates="created_cases")
    
    documents = relationship("UploadedDocument", back_populates="case", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="case", cascade="all, delete-orphan")
    contracts = relationship("Contract", back_populates="case", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="case", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="case", cascade="all, delete-orphan")
    goods_received_notes = relationship("GoodsReceivedNote", back_populates="case", cascade="all, delete-orphan")
    exports = relationship("ExportRecord", back_populates="case", cascade="all, delete-orphan")

