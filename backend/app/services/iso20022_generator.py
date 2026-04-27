"""
ISO 20022 XML Generator
Generates valid ISO 20022 XML files from flat mapped data.
Supports pacs.008 (MT103) and pacs.009 (MT202).
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ISO 20022 namespaces
ISO_NAMESPACES = {
    "pacs.008.001.08": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
    "pacs.009.001.08": "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08",
    "camt.053.001.08": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08",
}

# Root element names by ISO target
ISO_ROOT_ELEMENTS = {
    "pacs.008.001.08": "FIToFICstmrCdtTrf",
    "pacs.009.001.08": "FICdtTrf",
    "camt.053.001.08": "BkToCstmrStmt",
}


class ISO20022Generator:

    def generate(
        self,
        mapped_data: Dict[str, Any],
        iso_target: str,
        mt_type: str = None
    ) -> str:
        """
        Generate ISO 20022 XML from flat mapped data.

        Args:
            mapped_data: flat dict {ISO_path: value}
            iso_target: e.g. "pacs.008.001.08"
            mt_type: e.g. "MT103"

        Returns:
            Pretty-printed XML string
        """
        namespace = ISO_NAMESPACES.get(iso_target, ISO_NAMESPACES["pacs.008.001.08"])
        root_elem = ISO_ROOT_ELEMENTS.get(iso_target, "FIToFICstmrCdtTrf")

        # Register namespace
        ET.register_namespace('', namespace)

        # Root document element
        doc = ET.Element(f"{{{namespace}}}Document")

        # Main message element
        msg = ET.SubElement(doc, f"{{{namespace}}}{root_elem}")

        # Build XML from mapped data
        self._build_xml(msg, mapped_data, namespace, iso_target, mt_type)

        # Pretty print
        xml_str = ET.tostring(doc, encoding='unicode', xml_declaration=False)
        pretty = self._prettify(xml_str, namespace)

        return f'<?xml version="1.0" encoding="UTF-8"?>\n{pretty}'

    def _build_xml(
        self,
        parent: ET.Element,
        mapped_data: Dict[str, Any],
        namespace: str,
        iso_target: str,
        mt_type: str
    ):
        """Build XML tree from flat ISO paths."""

        # Add GrpHdr (Group Header) — always required
        grp_hdr = ET.SubElement(parent, f"{{{namespace}}}GrpHdr")
        ET.SubElement(grp_hdr, f"{{{namespace}}}MsgId").text = \
            mapped_data.get("GrpHdr.MsgId") or \
            mapped_data.get("CdtTrfTxInf.EndToEndId") or \
            f"MSG{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        ET.SubElement(grp_hdr, f"{{{namespace}}}CreDtTm").text = \
            datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        ET.SubElement(grp_hdr, f"{{{namespace}}}NbOfTxs").text = "1"

        if iso_target == "pacs.008.001.08":
            self._build_pacs008(parent, mapped_data, namespace)
        elif iso_target == "pacs.009.001.08":
            self._build_pacs009(parent, mapped_data, namespace)

    def _build_pacs008(self, parent, data, ns):
        """Build pacs.008 — Customer Credit Transfer (MT103)."""
        txn = ET.SubElement(parent, f"{{{ns}}}CdtTrfTxInf")

        # Payment ID
        pmt_id = ET.SubElement(txn, f"{{{ns}}}PmtId")
        ET.SubElement(pmt_id, f"{{{ns}}}EndToEndId").text = \
            data.get("CdtTrfTxInf.EndToEndId", "NOTPROVIDED")

        # Amount
        if data.get("CdtTrfTxInf.Amt.InstdAmt"):
            amt_elem = ET.SubElement(txn, f"{{{ns}}}Amt")
            instd = ET.SubElement(amt_elem, f"{{{ns}}}InstdAmt")
            instd.text = str(data.get("CdtTrfTxInf.Amt.InstdAmt", "0"))
            ccy = data.get("PmtInf.DbtrAcct.Ccy", "EUR")
            instd.set("Ccy", ccy)

        # Charge Bearer
        if data.get("PmtInf.ChrgBr"):
            chgbr_map = {"SHA": "SHAR", "OUR": "DEBT", "BEN": "CRED"}
            chgbr_val = chgbr_map.get(data.get("PmtInf.ChrgBr"), data.get("PmtInf.ChrgBr"))
            ET.SubElement(txn, f"{{{ns}}}ChrgBr").text = chgbr_val

        # Debtor Agent
        if data.get("PmtInf.DbtrAgt.FinInstnId.BIC"):
            dbtr_agt = ET.SubElement(txn, f"{{{ns}}}DbtrAgt")
            fin_instn = ET.SubElement(dbtr_agt, f"{{{ns}}}FinInstnId")
            ET.SubElement(fin_instn, f"{{{ns}}}BICFI").text = \
                data.get("PmtInf.DbtrAgt.FinInstnId.BIC")

        # Debtor
        if data.get("PmtInf.Dbtr.Nm"):
            dbtr = ET.SubElement(txn, f"{{{ns}}}Dbtr")
            ET.SubElement(dbtr, f"{{{ns}}}Nm").text = data.get("PmtInf.Dbtr.Nm")

        # Debtor Account
        if data.get("PmtInf.DbtrAcct.Id.IBAN"):
            dbtr_acct = ET.SubElement(txn, f"{{{ns}}}DbtrAcct")
            acct_id = ET.SubElement(dbtr_acct, f"{{{ns}}}Id")
            ET.SubElement(acct_id, f"{{{ns}}}IBAN").text = \
                data.get("PmtInf.DbtrAcct.Id.IBAN")

        # Creditor Agent
        if data.get("CdtTrfTxInf.CdtrAgt.FinInstnId.BIC"):
            cdtr_agt = ET.SubElement(txn, f"{{{ns}}}CdtrAgt")
            fin_instn = ET.SubElement(cdtr_agt, f"{{{ns}}}FinInstnId")
            ET.SubElement(fin_instn, f"{{{ns}}}BICFI").text = \
                data.get("CdtTrfTxInf.CdtrAgt.FinInstnId.BIC")

        # Creditor
        if data.get("CdtTrfTxInf.Cdtr.Nm"):
            cdtr = ET.SubElement(txn, f"{{{ns}}}Cdtr")
            ET.SubElement(cdtr, f"{{{ns}}}Nm").text = data.get("CdtTrfTxInf.Cdtr.Nm")

        # Creditor Account
        if data.get("CdtTrfTxInf.CdtrAcct.Id.IBAN"):
            cdtr_acct = ET.SubElement(txn, f"{{{ns}}}CdtrAcct")
            acct_id = ET.SubElement(cdtr_acct, f"{{{ns}}}Id")
            ET.SubElement(acct_id, f"{{{ns}}}IBAN").text = \
                data.get("CdtTrfTxInf.CdtrAcct.Id.IBAN")

        # Remittance Info
        if data.get("CdtTrfTxInf.RmtInf.Ustrd"):
            rmt_inf = ET.SubElement(txn, f"{{{ns}}}RmtInf")
            ET.SubElement(rmt_inf, f"{{{ns}}}Ustrd").text = \
                data.get("CdtTrfTxInf.RmtInf.Ustrd")

        # Requested Execution Date
        if data.get("PmtInf.ReqdExctnDt"):
            ET.SubElement(txn, f"{{{ns}}}ReqdExctnDt").text = \
                str(data.get("PmtInf.ReqdExctnDt"))

    def _build_pacs009(self, parent, data, ns):
        """Build pacs.009 — Financial Institution Credit Transfer (MT202)."""
        txn = ET.SubElement(parent, f"{{{ns}}}CdtTrfTxInf")

        # Payment ID
        pmt_id = ET.SubElement(txn, f"{{{ns}}}PmtId")
        ET.SubElement(pmt_id, f"{{{ns}}}EndToEndId").text = \
            data.get("CdtTrfTxInf.EndToEndId", "NOTPROVIDED")
        if data.get("GrpHdr.MsgId"):
            ET.SubElement(pmt_id, f"{{{ns}}}TxId").text = data.get("GrpHdr.MsgId")

        # Amount
        if data.get("CdtTrfTxInf.Amt.InstdAmt"):
            amt_elem = ET.SubElement(txn, f"{{{ns}}}Amt")
            instd = ET.SubElement(amt_elem, f"{{{ns}}}InstdAmt")
            instd.text = str(data.get("CdtTrfTxInf.Amt.InstdAmt", "0"))
            ccy = data.get("PmtInf.DbtrAcct.Ccy", "EUR")
            instd.set("Ccy", ccy)

        # Ordering Institution (Debtor Agent) — :52A
        if data.get("PmtInf.DbtrAgt.FinInstnId.BIC"):
            instg_agt = ET.SubElement(txn, f"{{{ns}}}InstgAgt")
            fin_instn = ET.SubElement(instg_agt, f"{{{ns}}}FinInstnId")
            ET.SubElement(fin_instn, f"{{{ns}}}BICFI").text = \
                data.get("PmtInf.DbtrAgt.FinInstnId.BIC")

        # Intermediary Agent — :56A
        if data.get("CdtTrfTxInf.IntrmyAgt1.FinInstnId.BIC"):
            intrmy = ET.SubElement(txn, f"{{{ns}}}IntrmyAgt1")
            fin_instn = ET.SubElement(intrmy, f"{{{ns}}}FinInstnId")
            ET.SubElement(fin_instn, f"{{{ns}}}BICFI").text = \
                data.get("CdtTrfTxInf.IntrmyAgt1.FinInstnId.BIC")

        # Creditor Agent — :57A
        if data.get("CdtTrfTxInf.CdtrAgt.FinInstnId.BIC"):
            cdtr_agt = ET.SubElement(txn, f"{{{ns}}}CdtrAgt")
            fin_instn = ET.SubElement(cdtr_agt, f"{{{ns}}}FinInstnId")
            ET.SubElement(fin_instn, f"{{{ns}}}BICFI").text = \
                data.get("CdtTrfTxInf.CdtrAgt.FinInstnId.BIC")

        # Creditor (Beneficiary Institution) — :58A
        if data.get("CdtTrfTxInf.Cdtr.FinInstnId.BIC"):
            cdtr = ET.SubElement(txn, f"{{{ns}}}Cdtr")
            fin_instn = ET.SubElement(cdtr, f"{{{ns}}}FinInstnId")
            ET.SubElement(fin_instn, f"{{{ns}}}BICFI").text = \
                data.get("CdtTrfTxInf.Cdtr.FinInstnId.BIC")

        # Sender to Receiver Info — :72
        if data.get("CdtTrfTxInf.InstrForCdtrAgt.InstrInf"):
            instr = ET.SubElement(txn, f"{{{ns}}}InstrForCdtrAgt")
            ET.SubElement(instr, f"{{{ns}}}InstrInf").text = \
                data.get("CdtTrfTxInf.InstrForCdtrAgt.InstrInf")

        # Requested Execution Date
        if data.get("PmtInf.ReqdExctnDt"):
            ET.SubElement(txn, f"{{{ns}}}ReqdExctnDt").text = \
                str(data.get("PmtInf.ReqdExctnDt"))

    def _prettify(self, xml_str: str, namespace: str) -> str:
        """Return pretty-printed XML string."""
        try:
            reparsed = minidom.parseString(xml_str.encode('utf-8'))
            pretty = reparsed.toprettyxml(indent="  ")
            # Remove extra XML declaration added by minidom
            lines = pretty.split('\n')
            if lines[0].startswith('<?xml'):
                lines = lines[1:]
            return '\n'.join(lines)
        except Exception:
            return xml_str


# Singleton
iso20022_generator = ISO20022Generator()