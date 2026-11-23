import enum
from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin, generate_uuid

class FindingCategory(str, enum.Enum):
    CONTRACT_PRICE_MISMATCH = "CONTRACT_PRICE_MISMATCH"
    POTENTIAL_UNDERCHARGE = "POTENTIAL_UNDERCHARGE"
    PO_PRICE_MISMATCH = "PO_PRICE_MISMATCH"
    QUANTITY_OVER_PO = "QUANTITY_OVER_PO"
    QUANTITY_OVER_GRN = "QUANTITY_OVER_GRN"
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    INCORRECT_LINE_TOTAL = "INCORRECT_LINE_TOTAL"
    INCORRECT_INVOICE_TOTAL = "INCORRECT_INVOICE_TOTAL"
    MISSING_CREDIT_OR_AMENDMENT = "MISSING_CREDIT_OR_AMENDMENT"

class Severity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class ReviewStatus(str, enum.Enum):
    NEW = "NEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"

class Finding(Base, TimestampMixin):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("reconciliation_cases.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    finding_category = Column(String(50), nullable=False)
    supplier_name = Column(String(255), nullable=False)
    invoice_reference = Column(String(100), nullable=False)
    line_number = Column(Integer, nullable=True)
    item_code = Column(String(100), nullable=True)
    item_description = Column(String(500), nullable=True)

    expected_amount = Column(Numeric(18, 4), nullable=False)
    invoiced_amount = Column(Numeric(18, 4), nullable=False)
    potential_difference = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(20), default="REVIEW_REQUIRED", nullable=False)

    severity = Column(String(50), default=Severity.HIGH.value, nullable=False)
    review_status = Column(String(50), default=ReviewStatus.NEW.value, nullable=False)

    calculation_explanation = Column(String(2000), nullable=False)
    source_document_references = Column(JSON, nullable=True)  # File name, document ID, page/row citations
    rule_version = Column(Integer, default=1, nullable=False)
    requires_more_info_reason = Column(String(1000), nullable=True)

    case = relationship("ReconciliationCase", back_populates="findings")
    decisions = relationship("ReviewDecision", back_populates="finding", cascade="all, delete-orphan")

class ReviewDecision(Base, TimestampMixin):
    __tablename__ = "review_decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    finding_id = Column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    action = Column(String(50), nullable=False)  # CONFIRM, REJECT, REQUEST_INFO, COMMENT, UPDATE_VALUE
    previous_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    comment = Column(String(2000), nullable=True)
    adjusted_amount = Column(Numeric(18, 4), nullable=True)

    finding = relationship("Finding", back_populates="decisions")
    reviewer = relationship("User", back_populates="review_decisions")
