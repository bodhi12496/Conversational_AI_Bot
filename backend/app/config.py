import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    provider: str = "demo"
    api_token: str = ""
    region: str = "us-east-1"
    model_id: str = ""
    max_upload_bytes: int = 5 * 1024 * 1024
    max_rows: int = 25_000
    max_columns: int = 100
    max_projects: int = 100
    max_views: int = 12

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("COE_DATA_DIR", "var")).resolve(),
            provider=os.getenv("COE_PROVIDER", "demo"),
            api_token=os.getenv("COE_API_TOKEN", ""),
            region=os.getenv("AWS_REGION", "us-east-1"),
            model_id=os.getenv("BEDROCK_MODEL_ID", ""),
        )
