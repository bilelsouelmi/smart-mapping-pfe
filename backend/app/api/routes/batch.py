import json
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.routes.transform_mapping import transform_with_mapping
from app.core.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter()

_FILENAME_RE = re.compile(r'filename="([^"]+)"')


def _extract_output_filename(response) -> Optional[str]:
    cd = response.headers.get('content-disposition', '')
    m = _FILENAME_RE.search(cd)
    return m.group(1) if m else None


@router.post("/mapping/{mapping_id}/batch")
async def batch_transform(
    mapping_id: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run every uploaded file through the exact same per-file pipeline as
    the single-file transform endpoint (transform_with_mapping) — same
    validation gates, same sanctions/PEP/duplicate checks, same
    large-amount and PEP holds, same audit trail — just looped, with one
    file's failure reported in the results list instead of aborting the
    rest of the batch. Deliberately calls that function directly rather
    than re-implementing any of its logic, so there is exactly one place
    the actual transform rules live; a batch upload gets no special
    treatment; each file is independently subject to everything a
    single-file upload would be (including duplicate-reference detection
    AGAINST EACH OTHER — two files in the same batch reusing the same
    :20: reference will correctly flag the second one, since the first's
    successful transform is committed before the second is processed).
    """
    results = []
    for f in files:
        try:
            response = await transform_with_mapping(
                mapping_id=mapping_id, file=f, current_user=current_user, db=db
            )
        except HTTPException as e:
            db.rollback()
            results.append({
                "filename": f.filename, "status": "failed",
                "http_status": e.status_code, "detail": e.detail
            })
            continue
        except Exception as e:
            db.rollback()
            results.append({
                "filename": f.filename, "status": "failed",
                "http_status": 500, "detail": str(e)
            })
            continue

        if response.status_code == 202:
            body = json.loads(response.body)
            results.append({"filename": f.filename, "status": "held", **body})
        else:
            results.append({
                "filename": f.filename, "status": "success",
                "output_filename": _extract_output_filename(response)
            })

    summary = {
        "total": len(results),
        "success": sum(1 for r in results if r["status"] == "success"),
        "held": sum(1 for r in results if r["status"] == "held"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
    }
    return {"summary": summary, "results": results}
