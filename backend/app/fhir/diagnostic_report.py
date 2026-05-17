"""Hand-built FHIR DiagnosticReport + ImagingStudy.

We avoid the fhir.resources dep to keep the build lean and to sidestep
its frequent Pydantic-major-version drift. The shapes below conform to
FHIR R4 and validate against the public profiles.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

# LOINC modality categorization codes
LOINC_BY_MODALITY = {
    "CT": ("18746-5", "Diagnostic imaging Study CT"),
    "MR": ("18755-6", "Diagnostic imaging Study MR"),
    "MG": ("38070-5", "Diagnostic imaging Study Mammography"),
    "CR": ("18748-4", "Diagnostic imaging Study X-Ray"),
    "DX": ("18748-4", "Diagnostic imaging Study X-Ray"),
}


def imaging_study(
    *,
    study_instance_uid: str,
    patient_pseudonym: str,
    modality: str,
    started: datetime | None,
    description: str,
) -> dict[str, Any]:
    return {
        "resourceType": "ImagingStudy",
        "id": str(uuid.uuid4()),
        "identifier": [
            {
                "system": "urn:dicom:uid",
                "value": f"urn:oid:{study_instance_uid}",
            }
        ],
        "status": "available",
        "modality": [
            {"system": "http://dicom.nema.org/resources/ontology/DCM", "code": modality}
        ],
        "subject": {"reference": f"Patient/{patient_pseudonym}"},
        "started": (started or datetime.now(timezone.utc)).isoformat(),
        "description": description or "",
    }


def diagnostic_report(
    *,
    study_instance_uid: str,
    patient_pseudonym: str,
    modality: str,
    impression: str,
    icd10_codes: list[str],
    model_name: str,
    model_version: str,
    narrative: str | None = None,
    rads_scores: list[dict] | None = None,
) -> dict[str, Any]:
    code, display = LOINC_BY_MODALITY.get(modality.upper(), ("18748-4", "Diagnostic imaging Study"))
    now = datetime.now(timezone.utc).isoformat()
    conclusion = (
        impression
        + "\n\nRESEARCH USE ONLY — NOT FOR DIAGNOSIS. Requires licensed radiologist review and signature before clinical use."
    )
    if narrative:
        conclusion += (
            "\n\nClinical narrative (MedGemma, RESEARCH USE ONLY):\n" + narrative
        )
    return {
        "resourceType": "DiagnosticReport",
        "id": str(uuid.uuid4()),
        "status": "preliminary",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "RAD",
                        "display": "Radiology",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {"system": "http://loinc.org", "code": code, "display": display}
            ]
        },
        "subject": {"reference": f"Patient/{patient_pseudonym}"},
        "effectiveDateTime": now,
        "issued": now,
        "performer": [
            {
                "display": f"{model_name} v{model_version} (AI; RESEARCH USE ONLY)"
            }
        ],
        "imagingStudy": [
            {"identifier": {"system": "urn:dicom:uid", "value": f"urn:oid:{study_instance_uid}"}}
        ],
        "conclusion": conclusion,
        "conclusionCode": [
            {
                "coding": [
                    {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": c}
                ]
            }
            for c in icd10_codes
        ]
        + [
            {
                "coding": [
                    {
                        "system": f"urn:rads:{r['scheme']}",
                        "code": r["code"],
                        "display": r["descriptor"],
                    }
                ]
            }
            for r in (rads_scores or [])
        ],
    }
