from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin, generate_uuid

class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    action = Column(String(100), nullable=False)  # CREATE_CASE, UPLOAD_DOCUMENT, RUN_RECONCILIATION, APPROVE_FINDING, etc.
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=False)
    payload_before = Column(JSON, nullable=True)
    payload_after = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)

class ExportRecord(Base, TimestampMixin):
    __tablename__ = "export_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("reconciliation_cases.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    generated_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    format = Column(String(20), nullable=False)  # CSV, PDF
    file_name = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    record_count = Column(Integer, default=0, nullable=False)
    total_leakage_amount = Column(Numeric(18, 4), default=0, nullable=False)

    case = relationship("ReconciliationCase", back_populates="exports")

