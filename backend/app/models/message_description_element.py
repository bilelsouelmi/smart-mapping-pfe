from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class MessageDescriptionElement(Base):
    __tablename__ = "message_description_elements"

    id = Column(Integer, primary_key=True, index=True)

    message_description_id = Column(
        Integer,
        ForeignKey("message_descriptions.id", ondelete="CASCADE"),
        nullable=False
    )

    parent_id = Column(
        Integer,
        ForeignKey("message_description_elements.id", ondelete="CASCADE"),
        nullable=True
    )

    name = Column(String(200), nullable=False)
    element_type = Column(String(50), nullable=True)
    field_tag = Column(String(20), nullable=True)
    fin_format = Column(String(50), nullable=True)
    min_length = Column(Integer, nullable=True)
    max_length = Column(Integer, nullable=True)
    min_occurs = Column(Integer, default=1)
    max_occurs = Column(Integer, nullable=True)
    mandatory = Column(Boolean, default=True)
    pattern = Column(String(200), nullable=True)
    precision = Column(Integer, nullable=True)
    prefix = Column(String(50), nullable=True)
    suffix = Column(String(50), nullable=True)
    separator = Column(String(20), nullable=True)
    mandatory_separator = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    example_value = Column(String(200), nullable=True)
    position = Column(Integer, default=0)
    # Opts this field into a live Reference Data lookup instead of a fixed
    # pattern/enum (e.g. "ISO_CURRENCY", "COUNTRY") — copied onto the
    # generated ValidationRule by import_rules_from_md, and checked by
    # _validate_field the same way the hardcoded :71A: Charge Code check
    # already works, just generic instead of tag-specific.
    reference_category = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Simple — SANS back_populates vers MessageDescription
    message_description = relationship("MessageDescription")

    parent = relationship(
        "MessageDescriptionElement",
        remote_side=[id],
        back_populates="children"
    )
    children = relationship(
        "MessageDescriptionElement",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="MessageDescriptionElement.position"
    )