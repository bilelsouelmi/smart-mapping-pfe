"""
ISO 20022 XML Parser
Parses ISO 20022 XML files and extracts fields into MT-like structure.
Supports: pacs.008, pacs.009, camt.053, camt.054
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
import logging
import re

logger = logging.getLogger(__name__)

NS_TO_MT = {
    "pacs.008.001.08": "MT103",
    "pacs.008.001.09": "MT103",
    "pacs.009.001.08": "MT202",
    "pacs.009.001.09": "MT202",
    "camt.053.001.08": "MT950",
    "camt.053.001.09": "MT950",
    "camt.054.001.08": "MT900",
    "camt.054.001.09": "MT900",
}

ISO_FIELD_DEFINITIONS = {
    "pacs.008": [
        (":20:", "Transaction Reference", "FIToFICstmrCdtTrf/GrpHdr/MsgId"),
        (":21:", "Related Reference", "FIToFICstmrCdtTrf/CdtTrfTxInf/PmtId/EndToEndId"),
        (":32A_amount:", "Amount", "FIToFICstmrCdtTrf/CdtTrfTxInf/Amt/InstdAmt"),
        (":32A_date:", "Value Date", "FIToFICstmrCdtTrf/CdtTrfTxInf/IntrBkSttlmDt"),
        (":32A_amount:", "Amount", "FIToFICstmrCdtTrf/CdtTrfTxInf/IntrBkSttlmAmt"),
        (":50K_iban:", "Ordering Customer IBAN", "FIToFICstmrCdtTrf/CdtTrfTxInf/DbtrAcct/Id/IBAN"),
        (":50K_name:", "Ordering Customer Name", "FIToFICstmrCdtTrf/CdtTrfTxInf/Dbtr/Nm"),
        (":52A:", "Ordering Institution", "FIToFICstmrCdtTrf/CdtTrfTxInf/DbtrAgt/FinInstnId/BICFI"),
        (":57A:", "Account With Institution", "FIToFICstmrCdtTrf/CdtTrfTxInf/CdtrAgt/FinInstnId/BICFI"),
        (":59_iban:", "Beneficiary IBAN", "FIToFICstmrCdtTrf/CdtTrfTxInf/CdtrAcct/Id/IBAN"),
        (":59_name:", "Beneficiary Name", "FIToFICstmrCdtTrf/CdtTrfTxInf/Cdtr/Nm"),
        (":70:", "Remittance Information", "FIToFICstmrCdtTrf/CdtTrfTxInf/RmtInf/Ustrd"),
        (":71A:", "Details of Charges", "FIToFICstmrCdtTrf/CdtTrfTxInf/ChrgBr"),
    ],
    "pacs.009": [
        # NOTE: GrpHdr/MsgId <- :21: and PmtId/EndToEndId <- :20: (not the
        # other way around) — matches the forward MT202->pacs.009 mapping's
        # deliberate convention (see MT202_to_pacs009.xml MAPPING_01:
        # GrpHdr.MsgId = MT.F21.trim(), CdtTrfTxInf.PmtId.EndToEndId =
        # MT.F20.trim()). Swapping these back here keeps the round-trip
        # consistent with that choice instead of silently reversing it.
        (":21:", "Related Reference", "FICdtTrf/GrpHdr/MsgId"),
        (":20:", "Transaction Reference", "FICdtTrf/CdtTrfTxInf/PmtId/EndToEndId"),
        (":32A:", "Value Date/Currency/Amount", "FICdtTrf/CdtTrfTxInf/IntrBkSttlmAmt"),
        (":52A:", "Ordering Institution", "FICdtTrf/CdtTrfTxInf/InstgAgt/FinInstnId/BICFI"),
        (":56A:", "Intermediary Institution", "FICdtTrf/CdtTrfTxInf/IntrmyAgt1/FinInstnId/BICFI"),
        (":57A:", "Account With Institution", "FICdtTrf/CdtTrfTxInf/CdtrAgt/FinInstnId/BICFI"),
        (":58A:", "Beneficiary Institution", "FICdtTrf/CdtTrfTxInf/Cdtr/FinInstnId/BICFI"),
    ],
    "camt.053": [
        (":20:", "Transaction Reference", "BkToCstmrStmt/GrpHdr/MsgId"),
        (":25:", "Account Identification", "BkToCstmrStmt/Stmt/Acct/Id/IBAN"),
        (":25:", "Account Identification", "BkToCstmrStmt/Stmt/Acct/Id"),
        # FIX: use ElctrncSeqNb (integer e.g. "1") instead of Stmt/Id (text string
        # like "STMTID20260629001"). Post-processing formats this as "00001/01"
        # which is the correct SWIFT :28C: format (statement_num/page_seq_num).
        (":28C:", "Statement Number", "BkToCstmrStmt/Stmt/ElctrncSeqNb"),
        # :61:/:86: are NOT extracted via this generic single-xpath table —
        # :61: is a composite (value date + D/C mark + amount + reference)
        # that needs its own builder; see the dedicated Ntry parsing below,
        # which sets extracted[':61:']/[':86:'] to their real values.
    ],
    "camt.054": [
        (":20:", "Transaction Reference", "BkToCstmrDbtCdtNtfctn/GrpHdr/MsgId"),
        (":21:", "Related Reference", "BkToCstmrDbtCdtNtfctn/Ntfctn/Ntry/NtryDtls/TxDtls/Refs/InstrId"),
        (":25:", "Account Identification", "BkToCstmrDbtCdtNtfctn/Ntfctn/Acct/Id/IBAN"),
        (":25:", "Account Identification", "BkToCstmrDbtCdtNtfctn/Ntfctn/Acct/Id"),
        (":32A_date:", "Value Date", "BkToCstmrDbtCdtNtfctn/Ntfctn/Ntry/NtryDtls/TxDtls/RltdDts/IntrBkSttlmDt"),
        (":32A_amount:", "Amount", "BkToCstmrDbtCdtNtfctn/Ntfctn/Ntry/Amt"),
        (":52A:", "Ordering Institution", "BkToCstmrDbtCdtNtfctn/Ntfctn/Ntry/NtryDtls/TxDtls/RltdAgts/DbtrAgt/FinInstnId/BICFI"),
        (":72:", "Sender to Receiver Information", "BkToCstmrDbtCdtNtfctn/Ntfctn/Ntry/NtryDtls/TxDtls/AddtlTxInf"),
    ],
}


class ISO20022Parser:

    def detect_iso_type(self, file_path: str) -> Optional[str]:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            tag = root.tag
            ns_match = re.search(r'\{urn:iso:std:iso:20022:tech:xsd:([^}]+)\}', tag)
            if ns_match:
                return ns_match.group(1)
            root_tag = tag.split('}')[-1] if '}' in tag else tag
            if 'Document' in root_tag:
                for child in root:
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if 'FIToFICstmrCdtTrf' in child_tag:
                        return 'pacs.008.001.08'
                    elif 'FICdtTrf' in child_tag:
                        return 'pacs.009.001.08'
                    elif 'BkToCstmrStmt' in child_tag:
                        return 'camt.053.001.08'
                    elif 'BkToCstmrDbtCdtNtfctn' in child_tag:
                        return 'camt.054.001.08'
            if root_tag.startswith('MT') and root_tag[2:].isdigit():
                mt_num = root_tag[2:]
                custom_map = {
                    '103': 'pacs.008.001.08', '202': 'pacs.009.001.08',
                    '900': 'camt.054.001.08', '910': 'camt.054.001.08',
                    '940': 'camt.053.001.08', '950': 'camt.053.001.08',
                }
                return custom_map.get(mt_num, 'pacs.008.001.08')
        except Exception as e:
            logger.error(f"Failed to detect ISO type: {e}")
        return None

    def _disambiguate_mt_subtype(self, iso_type: str, msg_family: str, root) -> str:
        """NS_TO_MT alone can't tell MT900 from MT910 (both target
        camt.054) or MT940 from MT950 (both target camt.053) — this is
        the fallback for XML that never went through this project (so has
        no SWIFT_ENVELOPE comment recording the real source type; see
        transform.py's auto_transform, which prefers that when present).
        Uses real content signals instead of guessing:
          - camt.054: CdtDbtInd is a direct signal — DBIT means this is a
            debit confirmation (MT900), CRDT means credit (MT910).
          - camt.053: MT940 carries per-entry narrative (RmtInf or
            AddtlNtryInf); a bare balance-only statement with no entry
            narrative is MT950.
        """
        if msg_family == 'camt.054':
            for elem in root.iter():
                local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if local == 'CdtDbtInd' and elem.text:
                    return 'MT900' if elem.text.strip().upper() == 'DBIT' else 'MT910'
            return 'MT900'
        if msg_family == 'camt.053':
            for elem in root.iter():
                local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if local in ('RmtInf', 'AddtlNtryInf') and ((elem.text or '').strip() or len(list(elem)) > 0):
                    return 'MT940'
            return 'MT950'
        return NS_TO_MT.get(iso_type, 'MT103')

    def _to_swift_amount(self, amt_str: str) -> str:
        """Convert an ISO decimal amount string to SWIFT format.
        '10000.00' -> '10000,00'  (decimal comma, no trailing comma needed)
        '10000'    -> '10000,'    (integer, add trailing comma as decimal separator)
        """
        amt = str(amt_str).replace('.', ',')
        # Only add trailing comma if no comma present (integer amounts).
        # Decimal amounts like "10000,00" already have a comma - don't double it.
        if ',' not in amt:
            amt += ','
        return amt

    def parse_custom_mt_xml(self, file_path: str, root_tag: str) -> Dict[str, Any]:
        tree = ET.parse(file_path)
        root = tree.getroot()
        mt_num = root_tag[2:]
        mt_type = f"MT{mt_num}"

        field_name_to_tag = {}
        try:
            from app.services.xml_mapping_parser import XMLMappingParser
            mappings_dir = '/app/dataset/mappings'
            parser = XMLMappingParser(mappings_dir)
            all_mappings = parser.load_all_mappings()
            for mid, mdata in all_mappings.items():
                if mt_num not in str(mid):
                    continue
                for field in mdata.get('source_message', {}).get('fields', []):
                    name = field.get('field_name', '').lower().strip()
                    tag = field.get('field_tag', '').strip()
                    if name and tag:
                        field_name_to_tag[name] = tag
                        clean = re.sub(r'[^a-z0-9]', '', name)
                        field_name_to_tag[clean] = tag
                break
        except Exception as e:
            logger.warning(f"Could not load mapping files: {e}")

        fallback = {
            'transactionreference': ':20:', 'transactionreferencenumber': ':20:',
            'relatedreference': ':21:', 'accountidentification': ':25:', 'accountid': ':25:',
            'statementnumber': ':28C:', 'statementnumbersequencenumber': ':28C:',
            'openingbalance': ':60F:', 'openingbalancefirst': ':60F:',
            'closingbalance': ':62F:', 'closingbalancefinal': ':62F:',
            'bankoperationcode': ':23B:', 'valuedate': ':32A:',
            'valuedatecurrencyamount': ':32A:', 'amount': ':32A:',
            'orderingcustomer': ':50K:', 'orderinginstitution': ':52A:',
            'beneficiarycustomer': ':59:', 'beneficiary': ':59:',
            'remittanceinformation': ':70:', 'detailsofcharges': ':71A:', 'charges': ':71A:',
            'sendertoreceiverinfo': ':72:', 'intermediaryinstitution': ':56A:',
        }
        field_name_to_tag = {**fallback, **field_name_to_tag}

        def normalize(s):
            return re.sub(r'[^a-z0-9]', '', s.lower())

        def get_text(el):
            return el.text.strip() if el is not None and el.text else ''

        def build_balance(el):
            if el is None:
                return ''
            dc = get_text(el.find('DebitCredit')) or 'C'
            date = get_text(el.find('Date')) or ''
            ccy = get_text(el.find('Currency')) or 'EUR'
            amt = self._to_swift_amount(get_text(el.find('Amount')) or '0')
            return f"{dc}{date}{ccy}{amt}"

        extracted = {}

        def process_element(el, parent_tag=''):
            tag = el.tag
            norm_tag = normalize(tag)
            text = get_text(el)
            children = list(el)

            if norm_tag in ('amount', 'valuedatecurrencyamount'):
                date = get_text(el.find('Date')) or ''
                ccy = get_text(el.find('Currency')) or 'EUR'
                val = self._to_swift_amount(get_text(el.find('Value')) or text or '0')
                if date:
                    extracted[':32A:'] = f"{date}{ccy}{val}"
                return
            if norm_tag in ('openingbalance', 'openingbalancefirstnonpaginated'):
                val = build_balance(el)
                if val:
                    extracted[':60F:'] = val
                return
            if norm_tag in ('closingbalance', 'closingbalancefinal'):
                val = build_balance(el)
                if val:
                    extracted[':62F:'] = val
                return
            if norm_tag == 'statementnumber':
                num = get_text(el.find('Number')) or ''
                seq = get_text(el.find('Sequence')) or ''
                if num.isdigit():
                    num = f"{int(num):05d}"
                if seq.isdigit():
                    seq = f"{int(seq):02d}"
                extracted[':28C:'] = f"{num}/{seq}" if seq else f"{num}/01"
                return
            if norm_tag == 'orderingcustomer':
                acct = get_text(el.find('Account'))
                name = get_text(el.find('Name'))
                bic = get_text(el.find('BIC'))
                if bic:
                    extracted[':50A:'] = bic
                elif acct:
                    extracted[':50K:'] = ("/" + acct + "\n" + name) if name else ("/" + acct)
                return
            if norm_tag == 'orderinginstitution':
                bic = get_text(el.find('BIC'))
                if bic:
                    extracted[':52A:'] = bic
                return
            if norm_tag in ('beneficiary', 'beneficiarycustomer'):
                acct = get_text(el.find('Account'))
                name = get_text(el.find('Name'))
                bic = get_text(el.find('BIC'))
                if bic:
                    extracted[':58A:'] = bic
                elif acct:
                    extracted[':59:'] = ("/" + acct + "\n" + name) if name else ("/" + acct)
                return
            if norm_tag == 'intermediaryinstitution':
                bic = get_text(el.find('BIC'))
                if bic:
                    extracted[':56A:'] = bic
                return
            if not children and text:
                mt_tag = field_name_to_tag.get(norm_tag, '')
                if mt_tag:
                    extracted[mt_tag] = text

        for child in root:
            process_element(child)

        columns = [{'name': k, 'display_name': k, 'type': 'string', 'sample_value': v}
                   for k, v in extracted.items()]
        return {
            'file_type': 'XML_CUSTOM_MT', 'mt_type': mt_type,
            'iso_target': '', 'iso_source': '',
            'mt_blocks': {'block4': {'sub_fields': {k: {'value': v} for k, v in extracted.items()}}},
            'columns': columns, 'sample_data': [extracted], 'extracted_fields': extracted,
        }

    def parse(self, file_path: str) -> Dict[str, Any]:
        try:
            tree_check = ET.parse(file_path)
            root_check = tree_check.getroot()
            root_tag = root_check.tag.split('}')[-1] if '}' in root_check.tag else root_check.tag
            if root_tag.startswith('MT') and root_tag[2:].isdigit():
                return self.parse_custom_mt_xml(file_path, root_tag)

            iso_type = self.detect_iso_type(file_path)
            if not iso_type:
                raise ValueError("Not a valid ISO 20022 XML file")

            msg_family = '.'.join(iso_type.split('.')[:2])

            tree = ET.parse(file_path)
            root = tree.getroot()

            ns = ''
            ns_match = re.search(r'\{([^}]+)\}', root.tag)
            if ns_match:
                ns = ns_match.group(1)

            mt_type = self._disambiguate_mt_subtype(iso_type, msg_family, root)

            def find_text(xpath_rel: str) -> str:
                parts = xpath_rel.split('/')
                current = root
                for part in parts:
                    found = None
                    for child in current:
                        child_tag = child.tag.replace(f'{{{ns}}}', '') if ns else child.tag
                        if child_tag == part:
                            found = child
                            break
                    if found is None:
                        return ''
                    current = found
                return (current.text or '').strip()

            field_defs = ISO_FIELD_DEFINITIONS.get(msg_family, [])
            extracted = {}
            columns = []
            sample_row = {}

            for field_tag, field_name, xpath in field_defs:
                if field_tag in extracted:
                    continue
                value = find_text(xpath)
                if value:
                    extracted[field_tag] = value
                    display_tag = field_tag.replace('_date', '').replace('_amount', '')
                    if not any(c['name'] == display_tag for c in columns):
                        columns.append({'name': display_tag, 'display_name': field_name,
                                        'type': 'string', 'sample_value': value})
                    sample_row[field_tag] = value

            # FIX: :28C: formatting for camt.053
            # ElctrncSeqNb gives a plain integer like "1", but SWIFT :28C:
            # requires NNNNN/NN format e.g. "00001/01"
            if ':28C:' in extracted and msg_family == 'camt.053':
                seq_num = extracted[':28C:'].strip()
                if seq_num.isdigit():
                    extracted[':28C:'] = f"{int(seq_num):05d}/01"

            # Extract camt.053 balance elements
            if msg_family == 'camt.053':
                def parse_bal_element(bal_el) -> str:
                    if bal_el is None:
                        return ''
                    dc_el = bal_el.find(f'{{{ns}}}CdtDbtInd') if ns else bal_el.find('CdtDbtInd')
                    dc = 'C' if (dc_el is not None and (dc_el.text or '').strip() == 'CRDT') else 'D'
                    dt_el = bal_el.find(f'{{{ns}}}Dt/{{{ns}}}Dt') if ns else bal_el.find('Dt/Dt')
                    iso_date = (dt_el.text or '').strip() if dt_el is not None else ''
                    if iso_date and len(iso_date) == 10:
                        date_str = iso_date[2:4] + iso_date[5:7] + iso_date[8:10]
                    else:
                        date_str = ''
                    amt_el = bal_el.find(f'{{{ns}}}Amt') if ns else bal_el.find('Amt')
                    ccy = (amt_el.get('Ccy', 'EUR') if amt_el is not None else 'EUR')
                    amt_raw = (amt_el.text or '0').strip() if amt_el is not None else '0'
                    # FIX: only add trailing comma if no comma already present.
                    # "10000.00" -> "10000,00" (already has decimal separator, stop)
                    # "10000"    -> "10000,"   (integer, add trailing comma)
                    amt = self._to_swift_amount(amt_raw)
                    return f"{dc}{date_str}{ccy}{amt}"

                stmt_path = 'BkToCstmrStmt/Stmt'
                parts = stmt_path.split('/')
                stmt_el = root
                for p in parts:
                    found = None
                    for child in stmt_el:
                        ctag = child.tag.replace(f'{{{ns}}}', '') if ns else child.tag
                        if ctag == p:
                            found = child
                            break
                    if found is None:
                        break
                    stmt_el = found

                if stmt_el is not root:
                    opbd_val = ''
                    clbd_val = ''
                    for child in stmt_el:
                        ctag = child.tag.replace(f'{{{ns}}}', '') if ns else child.tag
                        if ctag == 'Bal':
                            cd_el = None
                            for desc in child.iter():
                                dtag = desc.tag.replace(f'{{{ns}}}', '') if ns else desc.tag
                                if dtag == 'Cd':
                                    cd_el = desc
                                    break
                            if cd_el is not None:
                                code = (cd_el.text or '').strip()
                                bal_val = parse_bal_element(child)
                                if code == 'OPBD' and not opbd_val:
                                    opbd_val = bal_val
                                elif code == 'CLBD' and not clbd_val:
                                    clbd_val = bal_val
                    if opbd_val:
                        extracted[':60F:'] = opbd_val
                        columns.append({'name': ':60F:', 'display_name': 'Opening Balance',
                                        'type': 'string', 'sample_value': opbd_val})
                        sample_row[':60F:'] = opbd_val
                    if clbd_val:
                        extracted[':62F:'] = clbd_val
                        columns.append({'name': ':62F:', 'display_name': 'Closing Balance',
                                        'type': 'string', 'sample_value': clbd_val})
                        sample_row[':62F:'] = clbd_val

                    # :61: Statement Line — a composite of value date, D/C
                    # mark, amount, transaction type code and reference.
                    # NOTE: this only reconstructs the FIRST <Ntry> — MT940
                    # allows repeating :61:/:86: pairs (one per
                    # transaction), but extracted/sample_row here are flat
                    # single-value dicts, so only the first is recovered.
                    # Multi-entry round-trip would need a broader rework of
                    # this dict shape, not just this one field.
                    ntry_el = None
                    for child in stmt_el:
                        ctag = child.tag.replace(f'{{{ns}}}', '') if ns else child.tag
                        if ctag == 'Ntry':
                            ntry_el = child
                            break

                    if ntry_el is not None:
                        def _find_local(parent, path):
                            cur = parent
                            for p in path.split('/'):
                                found = None
                                for c in cur:
                                    ctag = c.tag.replace(f'{{{ns}}}', '') if ns else c.tag
                                    if ctag == p:
                                        found = c
                                        break
                                if found is None:
                                    return None
                                cur = found
                            return cur

                        dc_el = _find_local(ntry_el, 'CdtDbtInd')
                        dc = 'C' if (dc_el is not None and (dc_el.text or '').strip().upper() == 'CRDT') else 'D'

                        valdt_el = _find_local(ntry_el, 'ValDt/Dt')
                        iso_date = (valdt_el.text or '').strip() if valdt_el is not None else ''
                        date_str = (iso_date[2:4] + iso_date[5:7] + iso_date[8:10]) if len(iso_date) == 10 else ''

                        amt_el = _find_local(ntry_el, 'Amt')
                        amt_raw = (amt_el.text or '0').strip() if amt_el is not None else '0'
                        amt = self._to_swift_amount(amt_raw)

                        ref = ''
                        for desc in ntry_el.iter():
                            dtag = desc.tag.replace(f'{{{ns}}}', '') if ns else desc.tag
                            if dtag in ('InstrId', 'EndToEndId') and (desc.text or '').strip():
                                ref = desc.text.strip()
                                break

                        if date_str:
                            extracted[':61:'] = f"{date_str}{dc}{amt}NTRF{ref or 'NONREF'}"
                            columns.append({'name': ':61:', 'display_name': 'Statement Line',
                                            'type': 'string', 'sample_value': extracted[':61:']})
                            sample_row[':61:'] = extracted[':61:']

                        ustrd_el = None
                        for desc in ntry_el.iter():
                            dtag = desc.tag.replace(f'{{{ns}}}', '') if ns else desc.tag
                            if dtag == 'Ustrd' and (desc.text or '').strip():
                                ustrd_el = desc
                                break
                        if ustrd_el is not None:
                            extracted[':86:'] = ustrd_el.text.strip()
                            columns.append({'name': ':86:', 'display_name': 'Information to Account Owner',
                                            'type': 'string', 'sample_value': extracted[':86:']})
                            sample_row[':86:'] = extracted[':86:']

            # Combine :50K_iban: + :50K_name: into :50K:
            if ':50K_iban:' in extracted or ':50K_name:' in extracted:
                iban = extracted.pop(':50K_iban:', '')
                name = extracted.pop(':50K_name:', '')
                extracted[':50K:'] = ("/" + iban + "\n" + name) if (iban and name) else ("/" + iban if iban else name)

            # Combine :59_iban: + :59_name: into :59:
            if ':59_iban:' in extracted or ':59_name:' in extracted:
                iban = extracted.pop(':59_iban:', '')
                name = extracted.pop(':59_name:', '')
                extracted[':59:'] = ("/" + iban + "\n" + name) if (iban and name) else ("/" + iban if iban else name)

            # For pacs.008: handle date
            if msg_family == 'pacs.008' and ':32A_date:' not in extracted:
                date_val = extracted.get(':32A_date:', '')
                if date_val and len(date_val) == 10 and date_val[4] == '-':
                    parts = date_val.split('-')
                    extracted[':32A_date:'] = f"{parts[0][2:]}{parts[1]}{parts[2]}"
                else:
                    credt_val = find_text('FIToFICstmrCdtTrf/GrpHdr/CreDtTm')
                    if credt_val and len(credt_val) >= 10:
                        parts = credt_val[:10].split('-')
                        if len(parts) == 3:
                            extracted[':32A_date:'] = f"{parts[0][2:]}{parts[1]}{parts[2]}"

            # For pacs.009: same idea, but its settlement date/amount live at
            # a different XPath root (FICdtTrf, not FIToFICstmrCdtTrf) that
            # none of the fallbacks below were ever written to check — so
            # :32A: previously came out as a bare, uncurrencied,
            # undated amount for every pacs.009 file.
            if msg_family == 'pacs.009' and ':32A_date:' not in extracted:
                date_val = find_text('FICdtTrf/CdtTrfTxInf/IntrBkSttlmDt')
                if date_val and len(date_val) == 10 and date_val[4] == '-':
                    parts = date_val.split('-')
                    extracted[':32A_date:'] = f"{parts[0][2:]}{parts[1]}{parts[2]}"

            # Combine :32A_date: and :32A_amount: into :32A:
            date_val = extracted.get(':32A_date:', '')
            amt_val = extracted.get(':32A_amount:', '')

            if not amt_val:
                amt_val = (find_text('BkToCstmrDbtCdtNtfctn/Ntfctn/Ntry/Amt') or
                           find_text('BkToCstmrDbtCdtNtfctn/Ntfctn/Ntry/NtryDtls/TxDtls/Amt') or
                           find_text('FIToFICstmrCdtTrf/CdtTrfTxInf/IntrBkSttlmAmt') or
                           find_text('FICdtTrf/CdtTrfTxInf/IntrBkSttlmAmt') or
                           # This project's OWN MT202->pacs.009 mapping puts
                           # the amount at Amt/InstdAmt rather than the
                           # "real" ISO IntrBkSttlmAmt path above — check
                           # both so our own generated XML round-trips too.
                           find_text('FICdtTrf/CdtTrfTxInf/Amt/InstdAmt') or '')

            currency = 'EUR'
            try:
                for elem in root.iter():
                    local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    if local in ('Amt', 'IntrBkSttlmAmt') and elem.get('Ccy'):
                        currency = elem.get('Ccy')
                        if not amt_val and elem.text:
                            amt_val = elem.text.strip()
                        break
            except Exception:
                pass

            if date_val or amt_val:
                if date_val and len(date_val) == 10 and date_val[4] == '-':
                    parts = date_val.split('-')
                    date_str = f"{parts[0][2:]}{parts[1]}{parts[2]}"
                else:
                    date_str = date_val
                if amt_val:
                    import re as _re
                    amt_str = str(amt_val).replace('.', ',')
                    amt_str = _re.sub(r',0+$', ',', amt_str)
                    if not amt_str.endswith(','):
                        amt_str += ','
                    extracted[':32A:'] = f"{date_str}{currency}{amt_str}"
                elif date_str:
                    extracted[':32A:'] = f"{date_str}{currency}0,"

            mt_blocks = {
                'block1': {
                    'raw': f'F01SMRT{mt_type}0000000000',
                    'sub_fields': {
                        'ApplicationIdentifier': {'value': 'F'},
                        'ServiceIdentifier': {'value': '01'},
                        'LogicalTerminalAddress': {'value': f'SMRT{mt_type}XXXX'},
                    }
                },
                'block2': {
                    'raw': f'I{mt_type.replace("MT","")}BNPAFRPPXXXXN',
                    'sub_fields': {'MessageType': {'value': mt_type.replace('MT', '')}}
                },
                'block4': {
                    'raw': '\n'.join([f'{k}:{v}' for k, v in extracted.items()]),
                    'sub_fields': {tag: {'value': val, 'field_tag': tag} for tag, val in extracted.items()}
                }
            }

            logger.info(f"✅ ISO 20022 Parser: {iso_type} -> {mt_type}, {len(extracted)} fields extracted")

            return {
                'file_type': 'XML_ISO20022', 'mt_type': mt_type,
                'iso_target': iso_type, 'iso_source': iso_type,
                'mt_blocks': mt_blocks, 'columns': columns,
                'sample_data': [sample_row] if sample_row else [],
                'column_structure': columns, 'extracted_fields': extracted,
            }

        except Exception as e:
            logger.error(f"ISO 20022 parse error: {e}")
            raise ValueError(f"Failed to parse ISO 20022 XML: {str(e)}")


# Singleton
iso20022_parser = ISO20022Parser()