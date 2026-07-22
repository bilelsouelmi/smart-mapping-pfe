from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
import logging
import json
import datetime
from pathlib import Path

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.message_description import MessageDescription
from app.models.mapping_formula import MappingFormula
from app.models.file_upload import FileUpload
from app.services.file_processor import FileProcessor
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

file_processor = FileProcessor()

# Output directory
OUTPUT_DIR = Path(settings.UPLOAD_DIR).parent / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/outputs")
async def list_outputs(
    current_user: User = Depends(get_current_user)
):
    """
    Liste tous les fichiers OUTPUT générés.
    """
    try:
        output_files = []

        if OUTPUT_DIR.exists():
            for file_path in list(OUTPUT_DIR.glob("*.json")) + list(OUTPUT_DIR.glob("*.xml")) + list(OUTPUT_DIR.glob("*.txt")):
                output_files.append({
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "created": file_path.stat().st_mtime
                })

        output_files.sort(key=lambda x: x['created'], reverse=True)

        return {
            "total_outputs": len(output_files),
            "files": output_files
        }

    except Exception as e:
        logger.error(f"Failed to list outputs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list outputs: {str(e)}"
        )


@router.get("/download/{filename}")
async def download_output(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """
    Télécharge un fichier output généré.
    """
    try:
        file_path = OUTPUT_DIR / filename

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {filename} not found"
            )

        if filename.endswith('.xml'):
            media_type = 'application/xml'
        elif filename.endswith('.json'):
            media_type = 'application/json'
        else:
            media_type = 'text/plain'
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type=media_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )


@router.post("/auto")
async def auto_transform(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Automated transformation between SWIFT MT and ISO 20022 XML formats.
    Auto-detects file type, queries database mapping formulas, transforms,
    saves the output, and returns the converted file.

    (UNCHANGED from before — this endpoint already used the correct
    Mapping/MappingElement/evaluate_expression engine for the MT->ISO
    direction, and iso20022_parser/mt_generator for ISO->MT. It benefits
    automatically from the evaluate_expression() control-flow fix made in
    transform_mapping.py, with no changes needed here.)
    """
    import tempfile
    import os
    from app.models.mapping import Mapping, MappingElement
    from app.services.swift_txt_parser import swift_txt_parser
    from app.services.iso20022_parser import iso20022_parser
    from app.services.mt_generator import mt_generator
    from fastapi.responses import Response
    from app.api.routes.transform_mapping import (
        resolve_element_value,
        set_xpath_value,
        build_xml_from_dict,
        extract_source_fields,
        ISO_NAMESPACES,
        ISO_ROOT_ELEMENTS
    )

    content = await file.read()
    try:
        content_str = content.decode('utf-8')
    except Exception:
        content_str = content.decode('latin-1')

    with tempfile.NamedTemporaryFile(mode='w', suffix='.tmp', delete=False, encoding='utf-8') as tmp:
        tmp.write(content_str)
        tmp_path = tmp.name

    try:
        is_swift_mt = swift_txt_parser.is_swift_txt(tmp_path)

        if is_swift_mt:
            logger.info("Auto-transform: Detected SWIFT MT file.")
            parsed = swift_txt_parser.parse(tmp_path)
            mt_type = parsed.get("mt_type", "MT103")
            iso_target = parsed.get("iso_target", "pacs.008.001.08")
            mt_blocks = parsed.get("mt_blocks") or {}
            source_fields = extract_source_fields(mt_blocks)

            logger.info(f"Auto-transform: mt_type={mt_type}, iso_target={iso_target}")

            mapping = db.query(Mapping).filter(
                Mapping.source == mt_type
            ).order_by(desc(Mapping.status == 'active'), Mapping.id.desc()).first()

            target_data = {}
            mapping_source_name = "Default Mapping"

            if mapping:
                mapping_source_name = mapping.name
                elements = db.query(MappingElement).filter(
                    MappingElement.mapping_id == mapping.id,
                    MappingElement.status == 'mapped'
                ).all()

                for el in elements:
                    if not el.target_field:
                        continue
                    value = resolve_element_value(el, source_fields)
                    if value:
                        set_xpath_value(target_data, el.target_field, value)
            else:
                msg_desc = db.query(MessageDescription).filter(
                    MessageDescription.mt_type == mt_type
                ).order_by(MessageDescription.id.desc()).first()

                if msg_desc:
                    mapping_source_name = f"Formulas from {msg_desc.file_name}"
                    formulas = db.query(MappingFormula).filter(
                        MappingFormula.message_description_id == msg_desc.id
                    ).all()

                    formula_dicts = [
                        {
                            "target_column": f.target_path,
                            "source_column": f.source_path,
                            "transformation_type": f.transformation_type,
                            "transformation_rule": f.transformation_rule
                        }
                        for f in formulas
                    ]
                    transformed_data = file_processor.apply_transformation(
                        data=[source_fields],
                        mapping_formulas=formula_dicts
                    )
                    if transformed_data:
                        for k, v in transformed_data[0].items():
                            if v:
                                set_xpath_value(target_data, k, v)

            if not target_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"No mappings or formulas found for {mt_type}."
                )

            if 'GrpHdr' not in target_data:
                target_data['GrpHdr'] = {}
            if 'MsgId' not in target_data.get('GrpHdr', {}):
                target_data.setdefault('GrpHdr', {})['MsgId'] = f"MSG{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            if 'CreDtTm' not in target_data.get('GrpHdr', {}):
                target_data.setdefault('GrpHdr', {})['CreDtTm'] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            target_data.setdefault('GrpHdr', {}).setdefault('NbOfTxs', '1')
            _ctrl_sum = (
                target_data.get('CdtTrfTxInf', {}).get('Amt', {}).get('InstdAmt', '') or
                target_data.get('PmtInf', {}).get('Amt', '') or
                '0'
            )
            if isinstance(_ctrl_sum, dict):
                _ctrl_sum = '0'
            target_data.setdefault('GrpHdr', {}).setdefault('CtrlSum', str(_ctrl_sum))

            ordered_data = {}
            if 'GrpHdr' in target_data:
                ordered_data['GrpHdr'] = target_data.pop('GrpHdr')
            ordered_data.update(target_data)
            target_data = ordered_data

            namespace = ISO_NAMESPACES.get(iso_target, ISO_NAMESPACES.get('camt.053.001.08'))
            root_tag = ISO_ROOT_ELEMENTS.get(iso_target, 'BkToCstmrStmt')
            xml_content = build_xml_from_dict(target_data, namespace, root_tag, iso_target)

            def _get_sf(block, key):
                sf = block.get('sub_fields', {})
                val = sf.get(key, '')
                return val.get('value', '') if isinstance(val, dict) else str(val)

            b1 = mt_blocks.get('block1', {})
            b2 = mt_blocks.get('block2', {})
            b3 = mt_blocks.get('block3', {})
            b5 = mt_blocks.get('block5', {})
            envelope = json.dumps({
                'block1': _get_sf(b1,'ApplicationIdentifier') + _get_sf(b1,'ServiceIdentifier') + _get_sf(b1,'LogicalTerminalAddress') + _get_sf(b1,'SessionNumber') + _get_sf(b1,'SequenceNumber'),
                'block2_dest': _get_sf(b2,'DestinationAddress'),
                'block2_priority': _get_sf(b2,'Priority'),
                'block3_108': _get_sf(b3,'108') or _get_sf(b3,'Value'),
                'block5_chk': _get_sf(b5,'CHK') or _get_sf(b5,'Value') or '000000000000',
                # Several MT types share one ISO target (MT900/MT910 -> camt.054,
                # MT940/MT950 -> camt.053) — without the original type preserved
                # here, converting this XML back to SWIFT can only guess from
                # the ISO namespace alone, which is ambiguous. See
                # iso20022_parser.parse()'s envelope-first subtype detection.
                'block2_msgtype': mt_type
            })
            xml_content = xml_content.replace(
                '<?xml version="1.0" encoding="UTF-8"?>',
                f'<?xml version="1.0" encoding="UTF-8"?>\n<!-- SWIFT_ENVELOPE:{envelope} -->'
            )

            out_filename = f"auto_{mt_type}_to_{iso_target.replace('.','_')}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xml"
            out_path = OUTPUT_DIR / out_filename
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            logger.info(f"✅ Auto-transform saved: {out_filename}")

            return Response(
                content=xml_content,
                media_type='application/xml',
                headers={
                    'Content-Disposition': f'attachment; filename="{out_filename}"',
                    'X-Detected-Type': 'SWIFT_MT',
                    'X-Target-Type': 'ISO_20022_XML',
                    'X-Mapping-Source': mapping_source_name,
                    'X-Message-Type': mt_type,
                    'X-Target-Standard': iso_target
                }
            )

        else:
            logger.info("Auto-transform: Detected XML file.")
            try:
                parsed = iso20022_parser.parse(tmp_path)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse XML: {str(e)}"
                )

            extracted = parsed.get('extracted_fields', {})
            mt_type = parsed.get('mt_type', 'MT103')

            if not extracted:
                raise HTTPException(
                    status_code=400,
                    detail="No fields could be extracted from XML for SWIFT generation."
                )

            import re as _re
            envelope = {}
            envelope_match = _re.search(r'SWIFT_ENVELOPE:({[^}]+(?:}[^}]*)*})', content_str, _re.DOTALL)
            if envelope_match:
                try:
                    envelope = json.loads(envelope_match.group(1))
                    logger.info(f"✅ Restored SWIFT envelope: {envelope}")
                except Exception as e:
                    logger.warning(f"Failed to parse SWIFT envelope: {e}")

            # Several MT types share one ISO namespace (MT900/MT910 -> camt.054,
            # MT940/MT950 -> camt.053), so the namespace-only guess in
            # iso20022_parser.parse() can't distinguish them. Prefer the real
            # type this project itself stamped into the envelope comment when
            # it generated this XML — only falls back to the generic guess
            # for externally-produced XML that never went through us.
            envelope_mt_type = envelope.get('block2_msgtype')
            if envelope_mt_type and envelope_mt_type.upper().startswith('MT'):
                mt_type = envelope_mt_type.upper()

            mt_text = mt_generator.generate(extracted, mt_type, envelope=envelope)

            out_filename = f"auto_{mt_type}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}.txt"
            out_path = OUTPUT_DIR / out_filename
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(mt_text)
            logger.info(f"✅ Auto-transform saved: {out_filename}")

            return Response(
                content=mt_text,
                media_type='text/plain',
                headers={
                    'Content-Disposition': f'attachment; filename="{out_filename}"',
                    'X-Detected-Type': 'ISO_20022_XML',
                    'X-Target-Type': 'SWIFT_MT',
                    'X-Mapping-Source': 'XML parsing config',
                    'X-Message-Type': mt_type
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auto-transform error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Auto-transformation failed: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)