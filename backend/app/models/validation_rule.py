from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ValidationRule(Base):
    __tablename__ = "validation_rules"

    id = Column(Integer, primary_key=True, index=True)
    
    # MT type this rule belongs to
    mt_type = Column(String(20), nullable=False, index=True)  # MT103, MT202, MT940

    # file_type of the MessageDescription these rules were imported from
    # (e.g. "XML_MT" for a genuine SWIFT text upload, "XML_ISO20022" for an
    # ISO 20022 XML upload). Two structurally incompatible rule sets can
    # share the same mt_type — a real MT103 text file and a pacs.008 XML
    # both disambiguate to mt_type="MT103" — so mt_type alone isn't a
    # unique key; import_rules_from_md scopes its replace-on-import by
    # (mt_type, source_file_type) instead of wiping every rule for the
    # mt_type regardless of which kind of file they came from. Nullable
    # for rows created before this column existed.
    source_file_type = Column(String(20), nullable=True, index=True)

    # Block and field identification
    block_name = Column(String(50), nullable=True)   # block1, block2, block4...
    # 255, not 50: classic SWIFT tags (":20", "block1.ApplicationIdentifier")
    # fit either width, but a deeply-nested ISO 20022 XML path used as a
    # field_tag for an XML-sourced reference (e.g. camt.054's
    # "Ntfctn.Ntry.NtryDtls.TxDtls.RltdAgts.IntrmyAgt1.FinInstnId.BICFI",
    # 66 chars) does not — VARCHAR(50) silently failed the entire bulk
    # insert for any MD whose structure went this deep.
    field_tag = Column(String(255), nullable=True)   # :20, :32A, block1.ApplicationIdentifier
    field_name = Column(String(200), nullable=False) # TransactionReference, ApplicationIdentifier
    
    # Validation rules
    mandatory = Column(Boolean, default=False)
    min_length = Column(Integer, nullable=True)
    max_length = Column(Integer, nullable=True)
    fin_format = Column(String(50), nullable=True)   # 16x, 6!n, 3!a...
    pattern = Column(String(500), nullable=True)     # regex
    element_type = Column(String(50), nullable=True) # STRING, INTEGER, DECIMAL, DATE, CODE
    
    # Meta
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ValidationRule {self.mt_type} {self.field_tag}>"