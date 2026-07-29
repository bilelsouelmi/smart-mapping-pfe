import asyncio
from app.database import SessionLocal
from app.services import ai_learning_service as als_module
from app.services.llm_service import LLMService

async def main(model_name):
    # Monkey-patch _suggest_via_llm's LLMService instantiation to use the requested model
    original_init = LLMService.__init__
    def patched_init(self, base_url=None, model=None):
        original_init(self, base_url=base_url, model=model_name)
    LLMService.__init__ = patched_init

    db = SessionLocal()
    try:
        result = await als_module.ai_learning_service.suggest_field_mapping(
            field_id=":26T:",
            field_name="Transaction Type Code",
            sample_data=None,
            message_description_id=None,
            db=db,
            mt_type="MT103",
            iso_target="pacs.008.001.08",
        )
        print(f"\n=== Model: {model_name} ===")
        print("target:", result.get("target"))
        print("confidence:", result.get("confidence"))
        print("suggestion_source:", result.get("suggestion_source"))
    finally:
        db.close()
        LLMService.__init__ = original_init

import sys
asyncio.run(main(sys.argv[1]))
