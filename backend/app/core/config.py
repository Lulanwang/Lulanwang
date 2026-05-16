from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret: str = "change-me"
    public_base_url: str = "http://localhost"

    jwt_secret: str = "change-me-jwt"
    jwt_ttl_minutes: int = 30

    database_url: str = "postgresql+psycopg://lulan:lulan_dev_password@postgres:5432/app"

    orthanc_url: str = "http://orthanc:8042"
    orthanc_user: str = "orthanc"
    orthanc_password: str = "orthanc_dev_password"
    orthanc_dicomweb_prefix: str = "/dicom-web"

    artifact_dir: str = "/data/artifacts"

    mock_inference: bool = True
    monai_bundle_dir: str = "/data/monai-bundles"
    breast_mammo_weights: str = ""

    # --- MedGemma narrative writer ---
    # backend: "mock" (default, deterministic template) or "hf"
    # (POST to a Hugging Face Inference Endpoint serving MedGemma).
    medgemma_backend: str = "mock"
    # Set this to whatever model id your endpoint reports at GET /v1/models —
    # e.g. "google/medgemma-27b-text-it" (text-only 27B) or
    # "google/medgemma-4b-it" (multimodal 4B). For self-hosted vLLM/TGI
    # endpoints, this MUST match the --served-model-name flag.
    medgemma_model_id: str = "google/medgemma-27b-text-it"
    medgemma_hf_endpoint_url: str = ""
    medgemma_hf_token: str = ""
    medgemma_max_new_tokens: int = 512
    medgemma_timeout_seconds: int = 20

    deid_date_shift_days_max: int = 90

    seed_admin_email: str = "admin@lulan.local"
    seed_admin_password: str = "admin_demo_password"
    seed_clinician_email: str = "clinician@lulan.local"
    seed_clinician_password: str = "clinician_demo_password"


settings = Settings()
