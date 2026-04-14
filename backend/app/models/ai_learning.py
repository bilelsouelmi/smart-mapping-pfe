from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AILearning(Base):
    __tablename__ = "ai_learning"

    id = Column(Integer, primary_key=True, index=True)

    # Pattern du champ (pour matching)
    field_pattern = Column(String, index=True, nullable=False)
    field_tag = Column(String, nullable=True)
    original_field_name = Column(String, nullable=False)

    # Suggestion proposée par l'IA
    suggested_element_id = Column(String, nullable=True)
    suggested_description = Column(Text, nullable=True)
    suggested_source = Column(String, nullable=True)
    suggested_target = Column(String, nullable=True)
    suggested_transformation = Column(String, nullable=True)
    suggested_criticality = Column(String, nullable=True)
    suggestion_source = Column(String, nullable=True)
    # ── NOUVEAU : mapping_formula suggérée ────────────────────────────────────
    suggested_mapping_formula = Column(JSON, nullable=True)
    # ── FIN NOUVEAU ───────────────────────────────────────────────────────────

    # Action de l'utilisateur
    user_action = Column(String, nullable=False)

    # Valeurs finales (après édition si applicable)
    final_element_id = Column(String, nullable=True)
    final_description = Column(Text, nullable=True)
    final_source = Column(String, nullable=True)
    final_target = Column(String, nullable=True)
    final_transformation = Column(String, nullable=True)
    final_criticality = Column(String, nullable=True)
    # ── NOUVEAU : mapping_formula finale (après édition) ──────────────────────
    final_mapping_formula = Column(JSON, nullable=True)
    # ── FIN NOUVEAU ───────────────────────────────────────────────────────────

    # Métadonnées
    message_description_id = Column(Integer, ForeignKey('message_descriptions.id'), nullable=True)
    mapping_formula_id = Column(Integer, ForeignKey('mapping_formulas.id'), nullable=True)
    confidence_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relations
    user = relationship("User", back_populates="ai_learning_entries")
    message_description = relationship("MessageDescription")
    mapping_formula = relationship("MappingFormula")


# Index
Index('idx_ai_learning_field_pattern', AILearning.field_pattern)
Index('idx_ai_learning_field_tag', AILearning.field_tag)
Index('idx_ai_learning_user_action', AILearning.user_action)
Index('idx_ai_learning_created_at', AILearning.created_at)
Index('idx_ai_learning_message_desc', AILearning.message_description_id)
Index('idx_ai_learning_created_by', AILearning.created_by)