from sqlalchemy import Column, String, Integer, Numeric, Boolean, Date, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin, generate_uuid

class ExtractedDocumentField(Base, TimestampMixin):
    __tablename__ = "extracted_document_fields"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False)
    
    field_name = Column(String(100), nullable=False)
    extracted_value = Column(String(500), nullable=True)
    source_page_or_cell = Column(String(100), nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)  # 0.0000 - 1.0000
    extraction_method = Column(String(50), default="GEMINI_API", nullable=False)  # GEMINI_API, HEURISTIC_PARSER, MANUAL_EDIT
    requires_review = Column(Boolean, default=False, nullable=False)
    reviewed_value = Column(String(500), nullable=True)

    document = relationship("UploadedDocument", back_populates="extracted_fields")

class Contract(Base, TimestampMixin):
    __tablename__ = "contracts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("reconciliation_cases.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String(36), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False)

    contract_reference = Column(String(100), nullable=False)
    supplier_name = Column(String(255), nullable=False)
    effective_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    currency = Column(String(10), default="GBP", nullable=False)
    payment_terms_days = Column(Integer, nullable=True)
    notes = Column(String(1000), nullable=True)

    case = relationship("ReconciliationCase", back_populates="contracts")
    document = relationship("UploadedDocument", back_populates="contract")
    line_items = relationship("ContractLineItem", back_populates="contract", cascade="all, delete-orphan")

class ContractLineItem(Base, TimestampMixin):
    __tablename__ = "contract_line_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)

    item_code = Column(String(100), nullable=True)
    description = Column(String(500), nullable=False)
    contracted_unit_price = Column(Numeric(18, 4), nullable=False)
    unit_of_measure = Column(String(50), default="EA", nullable=False)
    min_quantity = Column(Numeric(18, 4), default=0, nullable=True)
    tier_discount_pct = Column(Numeric(5, 2), default=0, nullable=True)
    source_page_or_row = Column(String(100), nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)

    contract = relationship("Contract", back_populates="line_items")

class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("reconciliation_cases.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String(36), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False)

    po_number = Column(String(100), nullable=False)
    supplier_name = Column(String(255), nullable=False)
    order_date = Column(Date, nullable=True)
    currency = Column(String(10), default="GBP", nullable=False)
    total_amount = Column(Numeric(18, 4), nullable=True)

    case = relationship("ReconciliationCase", back_populates="purchase_orders")
    document = relationship("UploadedDocument", back_populates="purchase_order")
    line_items = relationship("POLineItem", back_populates="purchase_order", cascade="all, delete-orphan")

class POLineItem(Base, TimestampMixin):
    __tablename__ = "po_line_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    po_id = Column(String(36), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)

    line_number = Column(Integer, nullable=True)
    item_code = Column(String(100), nullable=True)
    description = Column(String(500), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    unit_price = Column(Numeric(18, 4), nullable=False)
    line_total = Column(Numeric(18, 4), nullable=False)
    source_page_or_row = Column(String(100), nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)

    purchase_order = relationship("PurchaseOrder", back_populates="line_items")

class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("reconciliation_cases.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String(36), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False)

    invoice_number = Column(String(100), nullable=False)
    supplier_name = Column(String(255), nullable=False)
    invoice_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    po_reference = Column(String(100), nullable=True)
    contract_reference = Column(String(100), nullable=True)
    currency = Column(String(10), default="GBP", nullable=False)
    subtotal = Column(Numeric(18, 4), nullable=False)
    tax_amount = Column(Numeric(18, 4), default=0, nullable=False)
    total_amount = Column(Numeric(18, 4), nullable=False)
    is_credit_note = Column(Boolean, default=False, nullable=False)

    case = relationship("ReconciliationCase", back_populates="invoices")
    document = relationship("UploadedDocument", back_populates="invoice")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceLineItem(Base, TimestampMixin):
    __tablename__ = "invoice_line_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)

    line_number = Column(Integer, nullable=True)
    item_code = Column(String(100), nullable=True)
    description = Column(String(500), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    unit_price = Column(Numeric(18, 4), nullable=False)
    line_total = Column(Numeric(18, 4), nullable=False)
    tax_rate = Column(Numeric(5, 2), default=20.0, nullable=True)
    matched_contract_line_id = Column(String(36), nullable=True)
    matched_po_line_id = Column(String(36), nullable=True)
    source_page_or_row = Column(String(100), nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)

    invoice = relationship("Invoice", back_populates="line_items")

class GoodsReceivedNote(Base, TimestampMixin):
    __tablename__ = "goods_received_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("reconciliation_cases.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String(36), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False)

    grn_number = Column(String(100), nullable=False)
    po_reference = Column(String(100), nullable=True)
    received_date = Column(Date, nullable=True)
    supplier_name = Column(String(255), nullable=True)

    case = relationship("ReconciliationCase", back_populates="goods_received_notes")
    document = relationship("UploadedDocument", back_populates="goods_received_note")
    line_items = relationship("GRNLineItem", back_populates="goods_received_note", cascade="all, delete-orphan")

class GRNLineItem(Base, TimestampMixin):
    __tablename__ = "grn_line_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    grn_id = Column(String(36), ForeignKey("goods_received_notes.id", ondelete="CASCADE"), nullable=False)

    item_code = Column(String(100), nullable=True)
    description = Column(String(500), nullable=False)
    quantity_received = Column(Numeric(18, 4), nullable=False)
    source_page_or_row = Column(String(100), nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)

    goods_received_note = relationship("GoodsReceivedNote", back_populates="line_items")

