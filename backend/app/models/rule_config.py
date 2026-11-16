from sqlalchemy import Column, String, Integer, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin, generate_uuid

class RuleConfiguration(Base, TimestampMixin):
    __tablename__ = "rule_configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True, nullable=False)

    price_variance_tolerance_pct = Column(Numeric(5, 2), default=0.00, nullable=False)  # 0.00%
    price_variance_tolerance_abs = Column(Numeric(18, 4), default=0.00, nullable=False) # £0.00
    quantity_variance_tolerance_pct = Column(Numeric(5, 2), default=0.00, nullable=False)
    duplicate_window_days = Column(Integer, default=90, nullable=False)
    fuzzy_match_threshold = Column(Integer, default=85, nullable=False)  # 85%
    high_severity_threshold = Column(Numeric(18, 4), default=500.00, nullable=False) # £500
    critical_severity_threshold = Column(Numeric(18, 4), default=2500.00, nullable=False) # £2500
    require_grn_for_goods = Column(Boolean, default=True, nullable=False)

    created_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_reason = Column(String(500), nullable=True)

    organization = relationship("Organization", back_populates="rule_configs")

