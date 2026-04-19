from .base import BaseHarness


class NaiveHarness(BaseHarness):
    """
    Builds context by dumping structured patient records directly into the
    prompt. No retrieval, no tools — the model reasons from raw text alone.
    """

    def build_context(self, patient_id: int) -> str:
        sections = [
            self._demographics(patient_id),
            self._admissions(patient_id),
            self._diagnoses(patient_id),
            self._procedures(patient_id),
            self._prescriptions(patient_id),
            self._icu_stays(patient_id),
        ]
        return "\n\n".join(s for s in sections if s)

    # ------------------------------------------------------------------

    def _demographics(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT gender, anchor_age, anchor_year_group, dod
            FROM mimiciv_hosp.patients
            WHERE subject_id = %s
        """, (patient_id,))
        if not rows:
            return ""
        r = rows[0]
        dod = f", deceased {r['dod']}" if r["dod"] else ""
        return (
            f"DEMOGRAPHICS\n"
            f"Gender: {r['gender']}, Age: {r['anchor_age']}, "
            f"Period: {r['anchor_year_group']}{dod}"
        )

    def _admissions(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT admittime, dischtime, admission_type, admission_location,
                   discharge_location, insurance, race, hospital_expire_flag
            FROM mimiciv_hosp.admissions
            WHERE subject_id = %s
            ORDER BY admittime
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["ADMISSIONS"]
        for r in rows:
            expired = " [expired]" if r["hospital_expire_flag"] else ""
            lines.append(
                f"  {r['admittime'].date()} – {r['dischtime'].date() if r['dischtime'] else '?'}"
                f" | {r['admission_type']} | from {r['admission_location']}"
                f" → {r['discharge_location']}{expired}"
            )
        return "\n".join(lines)

    def _diagnoses(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT d.long_title
            FROM mimiciv_hosp.diagnoses_icd di
            JOIN mimiciv_hosp.d_icd_diagnoses d
              ON d.icd_code = di.icd_code AND d.icd_version = di.icd_version
            WHERE di.subject_id = %s
            ORDER BY di.hadm_id, di.seq_num
            LIMIT 30
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["DIAGNOSES"] + [f"  - {r['long_title']}" for r in rows]
        return "\n".join(lines)

    def _procedures(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT p.chartdate, d.long_title
            FROM mimiciv_hosp.procedures_icd p
            JOIN mimiciv_hosp.d_icd_procedures d
              ON d.icd_code = p.icd_code AND d.icd_version = p.icd_version
            WHERE p.subject_id = %s
            ORDER BY p.chartdate
            LIMIT 20
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["PROCEDURES"]
        for r in rows:
            date = r["chartdate"] or "unknown date"
            lines.append(f"  {date}: {r['long_title']}")
        return "\n".join(lines)

    def _prescriptions(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT DISTINCT drug, dose_val_rx, dose_unit_rx, route, starttime
            FROM mimiciv_hosp.prescriptions
            WHERE subject_id = %s AND drug IS NOT NULL
            ORDER BY starttime
            LIMIT 30
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["PRESCRIPTIONS"]
        for r in rows:
            dose = f"{r['dose_val_rx']} {r['dose_unit_rx']}" if r["dose_val_rx"] else ""
            route = f"via {r['route']}" if r["route"] else ""
            lines.append(f"  - {r['drug']} {dose} {route}".strip())
        return "\n".join(lines)

    def _icu_stays(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT first_careunit, last_careunit, intime, outtime, los
            FROM mimiciv_icu.icustays
            WHERE subject_id = %s
            ORDER BY intime
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["ICU STAYS"]
        for r in rows:
            los = f"{r['los']:.1f} days" if r["los"] else "?"
            lines.append(
                f"  {r['intime'].date()} – {r['outtime'].date() if r['outtime'] else '?'}"
                f" | {r['first_careunit']} → {r['last_careunit']} | LOS: {los}"
            )
        return "\n".join(lines)
