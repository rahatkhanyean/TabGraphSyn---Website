from pathlib import Path

placeholder = """from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

STAGING_ROOT = Path(settings.MEDIA_ROOT) / 'uploads'
DEFAULT_TABLE_NAME = 'table'
DATA_ROOT = Path(settings.BASE_DIR) / 'src' / 'data' / 'original'


@dataclass
class StageData:
    token: str
    root: Path
    source_path: Path
    profile: dict[str, Any]

    @property
    def metadata_path(self) -> Path:
        return self.root / 'metadata.json'

    @property
    def marker_path(self) -> Path:
        return self.root / 'stage.json'

"""
