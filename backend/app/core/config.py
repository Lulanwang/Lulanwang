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

    deid_date_shift_days_max: int = 90

    seed_admin_email: str = "admin@lulan.local"
    seed_admin_password: str = "admin_demo_password"
    seed_clinician_email: str = "clinician@lulan.local"
    seed_clinician_password: str = "clinician_demo_password"


settings = Settings()
