import enum
from sqlalchemy import Column, String, Integer, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin, generate_uuid

class DocumentCategory(str, enum.Enum):
    CONTRACT = "CONTRACT"
    PRICE_SCHEDULE = "PRICE_SCHEDULE"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    INVOICE = "INVOICE"
    GOODS_RECEIVED_NOTE = "GOODS_RECEIVED_NOTE"

class ProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"

class UploadedDocument(Base, TimestampMixin):
    __tablename__ = "uploaded_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("reconciliation_cases.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, csv, xlsx
    category = Column(String(50), default=DocumentCategory.INVOICE.value, nullable=False)
    storage_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    
    processing_status = Column(String(50), default=ProcessingStatus.PENDING.value, nullable=False)
    error_message = Column(String(1000), nullable=True)
    extracted_metadata = Column(JSON, nullable=True)

    case = relationship("ReconciliationCase", back_populates="documents")
    extracted_fields = relationship("ExtractedDocumentField", back_populates="document", cascade="all, delete-orphan")
    contract = relationship("Contract", back_populates="document", uselist=False, cascade="all, delete-orphan")
    purchase_order = relationship("PurchaseOrder", back_populates="document", uselist=False, cascade="all, delete-orphan")
    invoice = relationship("Invoice", back_populates="document", uselist=False, cascade="all, delete-orphan")
    goods_received_note = relationship("GoodsReceivedNote", back_populates="document", uselist=False, cascade="all, delete-orphan")

