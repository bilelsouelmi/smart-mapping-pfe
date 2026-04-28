"""Patch ai_learning_service.py to add direct Qdrant lookup"""
import re

content = open('/app/app/services/ai_learning_service.py').read()

# Find the _enrich_from_qdrant method and add direct lookup before the query
old = '''            query = f"field mapping {field_name or field_id} transformation rules compliance audit"'''

new = '''            # ── Direct Qdrant lookup by field_tag ────────────────────────
            src_target_path = None
            src_element_id = None
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                from app.services.qdrant_manager import qdrant_manager as _qm
                clean_tag = str(field_id).strip()
                tag_variants = [clean_tag, f":{clean_tag.strip(':')}:", f":{clean_tag.strip(':')}"]
                for tv in tag_variants:
                    _r = _qm.client.scroll(
                        collection_name=_qm.collection_name,
                        scroll_filter=Filter(must=[
                            FieldCondition(key='chunk_type', match=MatchValue(value='SOURCE_FIELD')),
                            FieldCondition(key='field_tag', match=MatchValue(value=tv))
                        ]),
                        limit=3, with_payload=True
                    )
                    for _p in _r[0]:
                        if _p.payload.get('target_path'):
                            src_target_path = _p.payload['target_path']
                            src_element_id = _p.payload.get('element_id')
                            break
                    if src_target_path:
                        break
            except Exception as _e:
                print(f"Direct lookup error: {_e}")
            # ── END Direct lookup ─────────────────────────────────────────────

            query = f"field mapping {field_name or field_id} transformation rules compliance audit"'''

if old in content:
    content = content.replace(old, new, 1)
    print("✅ Patch applied")
else:
    print("❌ Pattern not found")
    # Find nearby text
    idx = content.find('field mapping')
    print("Context:", content[idx-100:idx+200])

# Also fix the enrichment to use src_target_path
old2 = '''                "rag_target_path": src_target_path or best_meta.get('target_path'),
                "rag_element_id": src_element_id or best_meta.get('element_id'),'''

if old2 in content:
    print("✅ rag_target_path already correct")
else:
    print("❌ rag_target_path pattern not found")

open('/app/app/services/ai_learning_service.py', 'w').write(content)
print("Done")