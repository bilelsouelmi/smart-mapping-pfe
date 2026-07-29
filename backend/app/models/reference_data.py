from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ReferenceData(Base):
    """
    Admin-editable code lists (ISO currencies, countries, SWIFT charge-
    bearer codes, ...) that Validation Rules check field values against —
    the same "single editable source of truth instead of hardcoded
    values" reasoning as BusinessVariable, just for enumerated code lists
    rather than single constants. `category` groups rows into the
    separate lists shown on the Reference Data page (e.g. "ISO_CURRENCY",
    "COUNTRY", "CHARGE_CODE"); `code` is the value actually checked
    against a field (e.g. "SHA"), `name` is its human-readable label
    (e.g. "Shared"). A row can be deactivated (is_active=False) instead
    of deleted to stop a code from validating without losing the
    historical record of it having existed.

    `meta_data` holds whatever extra fields are specific to one category
    (e.g. a currency's symbol/decimal_places/exchange rates, a country's
    ISO3/numeric code) — named meta_data rather than `metadata` because
    that name is already taken by SQLAlchemy's own Base.metadata
    attribute; the API still exposes it to callers as "metadata".
    """
    __tablename__ = "reference_data"
    __table_args__ = (UniqueConstraint('category', 'code', name='uq_reference_data_category_code'),)

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    meta_data = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    updater = relationship("User", foreign_keys=[updated_by])
