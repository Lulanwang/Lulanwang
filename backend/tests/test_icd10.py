from app.services import icd10


def test_search_returns_breast_codes():
    results = icd10.search("breast")
    codes = {c.code for c in results}
    # Spot-check the headline malignancy codes
    assert "C50.919" in codes or "C50.011" in codes


def test_suggest_brain():
    assert icd10.suggest_for("Suspected glioma", "BRAIN") == "C71.9"
    assert icd10.suggest_for("Peritumoral edema", "BRAIN") == "G93.6"
    assert icd10.suggest_for("Benign mass", "BRAIN") == "D33.2"


def test_suggest_lung():
    assert icd10.suggest_for("Solitary pulmonary nodule", "CHEST") == "R91.1"
    assert icd10.suggest_for("Mass right upper lobe", "LUNG") == "C34.90"
    assert icd10.suggest_for("Benign hamartoma", "LUNG") == "D14.30"


def test_suggest_breast():
    assert icd10.suggest_for("Cluster of microcalcifications", "BREAST") == "R92.0"
    assert icd10.suggest_for("Benign lesion", "BREAST") == "D24.9"
    assert icd10.suggest_for("Suspicious mass UOQ", "BREAST") == "C50.919"
