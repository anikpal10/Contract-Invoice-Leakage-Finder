from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin, generate_uuid

class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    canonical_name = Column(String(255), nullable=False)
    supplier_code = Column(String(100), nullable=True)
    tax_id = Column(String(100), nullable=True)
    payment_terms = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=True)

    organization = relationship("Organization", back_populates="suppliers")
    cases = relationship("ReconciliationCase", back_populates="supplier")

