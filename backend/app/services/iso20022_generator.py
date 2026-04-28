"""
ISO 20022 XML Generator
Supports pacs.008 (MT103), pacs.009 (MT202), camt.053 (MT940).
"""

import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

ISO_NAMESPACES = {
    "pacs.008.001.08": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
    "pacs.009.001.08": "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08",
    "camt.053.001.08": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08",
}

ISO_ROOT_ELEMENTS = {
    "pacs.008.001.08": "FIToFICstmrCdtTrf",
    "pacs.009.001.08": "FICdtTrf",
    "camt.053.001.08": "BkToCstmrStmt",
}


class ISO20022Generator:

    def generate(self, mapped_data, iso_target, mt_type=None):
        namespace = ISO_NAMESPACES.get(iso_target, ISO_NAMESPACES["pacs.008.001.08"])
        root_elem = ISO_ROOT_ELEMENTS.get(iso_target, "FIToFICstmrCdtTrf")
        ET.register_namespace('', namespace)
        doc = ET.Element(f"{{{namespace}}}Document")
        msg = ET.SubElement(doc, f"{{{namespace}}}{root_elem}")
        self._build_xml(msg, mapped_data, namespace, iso_target, mt_type)
        xml_str = ET.tostring(doc, encoding='unicode', xml_declaration=False)
        pretty = self._prettify(xml_str, namespace)
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{pretty}'

    def _build_xml(self, parent, mapped_data, namespace, iso_target, mt_type):
        grp_hdr = ET.SubElement(parent, f"{{{namespace}}}GrpHdr")
        ET.SubElement(grp_hdr, f"{{{namespace}}}MsgId").text = (
            mapped_data.get("GrpHdr.MsgId") or
            mapped_data.get("CdtTrfTxInf.EndToEndId") or
            f"MSG{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        ET.SubElement(grp_hdr, f"{{{namespace}}}CreDtTm").text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        ET.SubElement(grp_hdr, f"{{{namespace}}}NbOfTxs").text = "1"

        if iso_target == "pacs.008.001.08":
            self._build_pacs008(parent, mapped_data, namespace)
        elif iso_target == "pacs.009.001.08":
            self._build_pacs009(parent, mapped_data, namespace)
        elif iso_target == "camt.053.001.08":
            self._build_camt053(parent, mapped_data, namespace)

    def _build_pacs008(self, parent, data, ns):
        txn = ET.SubElement(parent, f"{{{ns}}}CdtTrfTxInf")
        pmt_id = ET.SubElement(txn, f"{{{ns}}}PmtId")
        ET.SubElement(pmt_id, f"{{{ns}}}EndToEndId").text = data.get("CdtTrfTxInf.EndToEndId", "NOTPROVIDED")
        if data.get("CdtTrfTxInf.Amt.InstdAmt"):
            amt_elem = ET.SubElement(txn, f"{{{ns}}}Amt")
            instd = ET.SubElement(amt_elem, f"{{{ns}}}InstdAmt")
            instd.text = str(data.get("CdtTrfTxInf.Amt.InstdAmt", "0"))
            instd.set("Ccy", data.get("PmtInf.DbtrAcct.Ccy", "EUR"))
        if data.get("PmtInf.ChrgBr"):
            chgbr_map = {"SHA": "SHAR", "OUR": "DEBT", "BEN": "CRED"}
            ET.SubElement(txn, f"{{{ns}}}ChrgBr").text = chgbr_map.get(data.get("PmtInf.ChrgBr"), data.get("PmtInf.ChrgBr"))
        if data.get("PmtInf.DbtrAgt.FinInstnId.BIC"):
            a = ET.SubElement(txn, f"{{{ns}}}DbtrAgt")
            b = ET.SubElement(a, f"{{{ns}}}FinInstnId")
            ET.SubElement(b, f"{{{ns}}}BICFI").text = data.get("PmtInf.DbtrAgt.FinInstnId.BIC")
        if data.get("PmtInf.Dbtr.Nm"):
            a = ET.SubElement(txn, f"{{{ns}}}Dbtr")
            ET.SubElement(a, f"{{{ns}}}Nm").text = data.get("PmtInf.Dbtr.Nm")
        if data.get("PmtInf.DbtrAcct.Id.IBAN"):
            a = ET.SubElement(txn, f"{{{ns}}}DbtrAcct")
            b = ET.SubElement(a, f"{{{ns}}}Id")
            ET.SubElement(b, f"{{{ns}}}IBAN").text = data.get("PmtInf.DbtrAcct.Id.IBAN")
        if data.get("CdtTrfTxInf.CdtrAgt.FinInstnId.BIC"):
            a = ET.SubElement(txn, f"{{{ns}}}CdtrAgt")
            b = ET.SubElement(a, f"{{{ns}}}FinInstnId")
            ET.SubElement(b, f"{{{ns}}}BICFI").text = data.get("CdtTrfTxInf.CdtrAgt.FinInstnId.BIC")
        if data.get("CdtTrfTxInf.Cdtr.Nm"):
            a = ET.SubElement(txn, f"{{{ns}}}Cdtr")
            ET.SubElement(a, f"{{{ns}}}Nm").text = data.get("CdtTrfTxInf.Cdtr.Nm")
        if data.get("CdtTrfTxInf.CdtrAcct.Id.IBAN"):
            a = ET.SubElement(txn, f"{{{ns}}}CdtrAcct")
            b = ET.SubElement(a, f"{{{ns}}}Id")
            ET.SubElement(b, f"{{{ns}}}IBAN").text = data.get("CdtTrfTxInf.CdtrAcct.Id.IBAN")
        if data.get("CdtTrfTxInf.RmtInf.Ustrd"):
            a = ET.SubElement(txn, f"{{{ns}}}RmtInf")
            ET.SubElement(a, f"{{{ns}}}Ustrd").text = data.get("CdtTrfTxInf.RmtInf.Ustrd")
        if data.get("PmtInf.ReqdExctnDt"):
            ET.SubElement(txn, f"{{{ns}}}ReqdExctnDt").text = str(data.get("PmtInf.ReqdExctnDt"))

    def _build_pacs009(self, parent, data, ns):
        txn = ET.SubElement(parent, f"{{{ns}}}CdtTrfTxInf")
        pmt_id = ET.SubElement(txn, f"{{{ns}}}PmtId")
        ET.SubElement(pmt_id, f"{{{ns}}}EndToEndId").text = data.get("CdtTrfTxInf.EndToEndId", "NOTPROVIDED")
        if data.get("GrpHdr.MsgId"):
            ET.SubElement(pmt_id, f"{{{ns}}}TxId").text = data.get("GrpHdr.MsgId")
        if data.get("CdtTrfTxInf.Amt.InstdAmt"):
            amt_elem = ET.SubElement(txn, f"{{{ns}}}Amt")
            instd = ET.SubElement(amt_elem, f"{{{ns}}}InstdAmt")
            instd.text = str(data.get("CdtTrfTxInf.Amt.InstdAmt", "0"))
            instd.set("Ccy", data.get("PmtInf.DbtrAcct.Ccy", "EUR"))
        if data.get("PmtInf.DbtrAgt.FinInstnId.BIC"):
            a = ET.SubElement(txn, f"{{{ns}}}InstgAgt")
            b = ET.SubElement(a, f"{{{ns}}}FinInstnId")
            ET.SubElement(b, f"{{{ns}}}BICFI").text = data.get("PmtInf.DbtrAgt.FinInstnId.BIC")
        if data.get("CdtTrfTxInf.IntrmyAgt1.FinInstnId.BIC"):
            a = ET.SubElement(txn, f"{{{ns}}}IntrmyAgt1")
            b = ET.SubElement(a, f"{{{ns}}}FinInstnId")
            ET.SubElement(b, f"{{{ns}}}BICFI").text = data.get("CdtTrfTxInf.IntrmyAgt1.FinInstnId.BIC")
        if data.get("CdtTrfTxInf.CdtrAgt.FinInstnId.BIC"):
            a = ET.SubElement(txn, f"{{{ns}}}CdtrAgt")
            b = ET.SubElement(a, f"{{{ns}}}FinInstnId")
            ET.SubElement(b, f"{{{ns}}}BICFI").text = data.get("CdtTrfTxInf.CdtrAgt.FinInstnId.BIC")
        if data.get("CdtTrfTxInf.Cdtr.FinInstnId.BIC"):
            a = ET.SubElement(txn, f"{{{ns}}}Cdtr")
            b = ET.SubElement(a, f"{{{ns}}}FinInstnId")
            ET.SubElement(b, f"{{{ns}}}BICFI").text = data.get("CdtTrfTxInf.Cdtr.FinInstnId.BIC")
        if data.get("CdtTrfTxInf.InstrForCdtrAgt.InstrInf"):
            a = ET.SubElement(txn, f"{{{ns}}}InstrForCdtrAgt")
            ET.SubElement(a, f"{{{ns}}}InstrInf").text = data.get("CdtTrfTxInf.InstrForCdtrAgt.InstrInf")
        if data.get("PmtInf.ReqdExctnDt"):
            ET.SubElement(txn, f"{{{ns}}}ReqdExctnDt").text = str(data.get("PmtInf.ReqdExctnDt"))

    def _parse_mt940_balance(self, raw):
        """C260427EUR10000,00 → (CRDT, 2026-04-27, EUR, 10000.00)"""
        if not raw:
            return "CRDT", "2026-01-01", "EUR", "0.00"
        m = re.match(r'([CD])(\d{6})([A-Z]{3})([\d,]+)', str(raw).strip())
        if m:
            dc = "CRDT" if m.group(1) == "C" else "DBIT"
            d = m.group(2)
            date = f"20{d[0:2]}-{d[2:4]}-{d[4:6]}"
            ccy = m.group(3)
            amt = m.group(4).replace(',', '.')
            if amt.endswith('.'):
                amt += '00'
            return dc, date, ccy, amt
        return "CRDT", "2026-01-01", "EUR", str(raw)

    def _parse_mt940_entry(self, raw):
        """2604270427CR5000,NTRFREF → (CRDT, 5000.00)"""
        if not raw:
            return "CRDT", "0.00"
        m = re.match(r'\d{6}(\d{4})?([A-Z]{1,2})([\d,]+)', str(raw).strip())
        if m:
            dc = "CRDT" if "C" in m.group(2) else "DBIT"
            amt = m.group(3).replace(',', '.')
            if amt.endswith('.'):
                amt += '00'
            return dc, amt
        return "CRDT", str(raw)

    def _build_camt053(self, parent, data, ns):
        """Build camt.053 — Bank To Customer Statement (MT940)."""
        stmt = ET.SubElement(parent, f"{{{ns}}}Stmt")

        # :28C → Stmt.Id
        if data.get("Stmt.Id"):
            ET.SubElement(stmt, f"{{{ns}}}Id").text = str(data.get("Stmt.Id"))

        # :25 → Stmt.Acct.Id.IBAN (remove /EUR suffix)
        if data.get("Stmt.Acct.Id.IBAN"):
            iban = str(data.get("Stmt.Acct.Id.IBAN")).split('/')[0].strip()
            acct = ET.SubElement(stmt, f"{{{ns}}}Acct")
            acct_id = ET.SubElement(acct, f"{{{ns}}}Id")
            ET.SubElement(acct_id, f"{{{ns}}}IBAN").text = iban

        # :60F → Stmt.Bal.OPBD
        if data.get("Stmt.Bal.OPBD"):
            dc, date, ccy, amt = self._parse_mt940_balance(data.get("Stmt.Bal.OPBD"))
            bal = ET.SubElement(stmt, f"{{{ns}}}Bal")
            tp = ET.SubElement(bal, f"{{{ns}}}Tp")
            cd = ET.SubElement(tp, f"{{{ns}}}CdOrPrtry")
            ET.SubElement(cd, f"{{{ns}}}Cd").text = "OPBD"
            a = ET.SubElement(bal, f"{{{ns}}}Amt")
            a.text = amt
            a.set("Ccy", ccy)
            ET.SubElement(bal, f"{{{ns}}}CdtDbtInd").text = dc
            dt = ET.SubElement(bal, f"{{{ns}}}Dt")
            ET.SubElement(dt, f"{{{ns}}}Dt").text = date

        # :62F → Stmt.Bal.CLBD
        if data.get("Stmt.Bal.CLBD"):
            dc, date, ccy, amt = self._parse_mt940_balance(data.get("Stmt.Bal.CLBD"))
            bal = ET.SubElement(stmt, f"{{{ns}}}Bal")
            tp = ET.SubElement(bal, f"{{{ns}}}Tp")
            cd = ET.SubElement(tp, f"{{{ns}}}CdOrPrtry")
            ET.SubElement(cd, f"{{{ns}}}Cd").text = "CLBD"
            a = ET.SubElement(bal, f"{{{ns}}}Amt")
            a.text = amt
            a.set("Ccy", ccy)
            ET.SubElement(bal, f"{{{ns}}}CdtDbtInd").text = dc
            dt = ET.SubElement(bal, f"{{{ns}}}Dt")
            ET.SubElement(dt, f"{{{ns}}}Dt").text = date

        # :61 → Stmt.Ntry
        if data.get("Stmt.Ntry"):
            dc, amt = self._parse_mt940_entry(data.get("Stmt.Ntry"))
            ntry = ET.SubElement(stmt, f"{{{ns}}}Ntry")
            a = ET.SubElement(ntry, f"{{{ns}}}Amt")
            a.text = amt
            a.set("Ccy", "EUR")
            ET.SubElement(ntry, f"{{{ns}}}CdtDbtInd").text = dc
            ET.SubElement(ntry, f"{{{ns}}}Sts").text = "BOOK"
            # :86 → Stmt.Ntry.NtryDtls.TxDtls.RmtInf.Ustrd
            if data.get("Stmt.Ntry.NtryDtls.TxDtls.RmtInf.Ustrd"):
                nd = ET.SubElement(ntry, f"{{{ns}}}NtryDtls")
                td = ET.SubElement(nd, f"{{{ns}}}TxDtls")
                ri = ET.SubElement(td, f"{{{ns}}}RmtInf")
                ET.SubElement(ri, f"{{{ns}}}Ustrd").text = str(data.get("Stmt.Ntry.NtryDtls.TxDtls.RmtInf.Ustrd"))

    def _prettify(self, xml_str, namespace):
        try:
            reparsed = minidom.parseString(xml_str.encode('utf-8'))
            pretty = reparsed.toprettyxml(indent="  ")
            lines = pretty.split('\n')
            if lines[0].startswith('<?xml'):
                lines = lines[1:]
            return '\n'.join(lines)
        except Exception:
            return xml_str


# Singleton
iso20022_generator = ISO20022Generator()