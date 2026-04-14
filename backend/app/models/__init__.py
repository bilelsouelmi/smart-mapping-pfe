from app.models.user import User
from app.models.ai_learning import AILearning  # ← AJOUTE CETTE LIGNE
from app.models.message_description import MessageDescription
from app.models.mapping_formula import MappingFormula
from app.models.file_upload import FileUpload
from app.models.transformation_job import TransformationJob
from app.models.validation_report import ValidationReport
from app.models.knowledge_base_entry import KnowledgeBaseEntry
from app.models.standard_element import StandardElement

__all__ = [
    "User",
    "AILearning",  # ← AJOUTE CETTE LIGNE
    "MessageDescription",
    "MappingFormula",
    "FileUpload",
    "TransformationJob",
    "ValidationReport",
    "KnowledgeBaseEntry",
    "StandardElement",
]