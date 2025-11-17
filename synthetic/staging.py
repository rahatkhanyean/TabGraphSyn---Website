from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from .constants import UPLOAD_MARKER


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
    def profile_path(self) -> Path:
        return self.root / 'profile.json'


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _slugify(raw: str, fallback: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9]+', '_', raw).strip('_')
    if not cleaned:
        return fallback
    return cleaned.lower()


def _write_upload(upload: UploadedFile, destination: Path) -> None:
    with destination.open('wb') as target:
        for chunk in upload.chunks():
            target.write(chunk)


def _infer_column_type(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return 'datetime'
    if pd.api.types.is_bool_dtype(series):
        return 'boolean'
    if pd.api.types.is_numeric_dtype(series):
        return 'numerical'
    return 'categorical'


def _infer_representation(series: pd.Series) -> str:
    series_no_na = series.dropna()
    if series_no_na.empty:
        return 'Float'
    if pd.api.types.is_integer_dtype(series_no_na):
        return 'Int64'
    try:
        as_float = series_no_na.astype(float)
    except (TypeError, ValueError):
        return 'Float'
    if np.allclose(as_float, np.round(as_float)):
        return 'Int64'
    return 'Float'


def stage_upload(upload: UploadedFile, *, dataset_name: str | None = None, table_name: str | None = None) -> StageData:
    token = uuid4().hex
    _ensure_dir(STAGING_ROOT)
    stage_root = STAGING_ROOT / token
    stage_root.mkdir(parents=True, exist_ok=False)

    source_path = stage_root / 'source.csv'
    _write_upload(upload, source_path)

    try:
        df = pd.read_csv(source_path)
    except Exception as exc:
        raise ValueError(f'Failed to read CSV file: {exc}') from exc

    if df.empty:
        raise ValueError('Uploaded dataset must contain at least one row.')

    base_name = upload.name.rsplit('.', 1)[0]
    display_dataset = dataset_name or base_name
    display_table = table_name or display_dataset
    inferred_dataset = _slugify(display_dataset, 'dataset')
    inferred_table = _slugify(display_table, DEFAULT_TABLE_NAME)

    columns_profile: list[dict[str, Any]] = []
    for name in df.columns:
        series = df[name]
        inferred_type = _infer_column_type(series)
        representation = _infer_representation(series) if inferred_type == 'numerical' else None
        columns_profile.append(
            {
                'name': str(name),
                'inferred_type': inferred_type,
                'allow_missing': bool(series.isna().any()),
                'representation': representation,
            }
        )

    profile = {
        'token': token,
        'dataset_name': inferred_dataset,
        'table_name': inferred_table,
        'display_dataset_name': display_dataset,
        'display_table_name': display_table,
        'row_count': int(len(df)),
        'columns': columns_profile,
        'source_filename': upload.name,
    }

    with (stage_root / 'profile.json').open('w', encoding='utf-8') as stream:
        json.dump(profile, stream, indent=2)

    return StageData(token=token, root=stage_root, source_path=source_path, profile=profile)


def load_stage(token: str) -> StageData:
    stage_root = STAGING_ROOT / token
    profile_path = stage_root / 'profile.json'
    source_path = stage_root / 'source.csv'
    if not profile_path.exists() or not source_path.exists():
        raise FileNotFoundError('Staged upload not found.')
    with profile_path.open('r', encoding='utf-8') as stream:
        profile = json.load(stream)
    return StageData(token=token, root=stage_root, source_path=source_path, profile=profile)


def save_metadata(token: str, metadata: dict[str, Any]) -> Path:
    stage = load_stage(token)
    with stage.metadata_path.open('w', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
    return stage.metadata_path


def metadata_exists(token: str) -> bool:
    stage = load_stage(token)
    return stage.metadata_path.exists()


def update_stage_profile(
    token: str,
    *,
    dataset_name: str | None = None,
    table_name: str | None = None,
    preserve_table_name: bool = False,
) -> StageData:
    stage = load_stage(token)
    updated = False
    if dataset_name:
        stage.profile['dataset_name'] = _slugify(dataset_name, stage.profile['dataset_name'])
        stage.profile['display_dataset_name'] = dataset_name
        updated = True
    if table_name:
        if preserve_table_name:
            stage.profile['table_name'] = table_name
        else:
            stage.profile['table_name'] = _slugify(table_name, stage.profile['table_name'])
        stage.profile['display_table_name'] = table_name
        updated = True
    if updated:
        with stage.profile_path.open('w', encoding='utf-8') as stream:
            json.dump(stage.profile, stream, indent=2)
    return stage


def build_metadata_from_profile(
    stage: StageData,
    *,
    primary_key: str | None = None,
    column_overrides: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    column_overrides = column_overrides or {}
    profile_columns = {entry['name']: entry for entry in stage.profile['columns']}
    columns: dict[str, Any] = {}

    for name, profile_entry in profile_columns.items():
        override = column_overrides.get(name, {})
        final_kind = override.get('kind', profile_entry.get('inferred_type'))
        profile_entry['inferred_type'] = final_kind
        sdtype = _sdtype_from_kind(final_kind)

        column_payload: dict[str, Any] = {'sdtype': sdtype}
        if sdtype == 'numerical':
            representation = override.get('representation') or profile_entry.get('representation') or 'Float'
            profile_entry['representation'] = representation
            column_payload['computer_representation'] = representation
        else:
            profile_entry.pop('representation', None)

        columns[name] = column_payload

    metadata = {
        'tables': {
            stage.profile['table_name']: {
                'columns': columns,
            }
        }
    }
    target_table = metadata['tables'][stage.profile['table_name']]
    if primary_key and primary_key in columns:
        target_table['primary_key'] = primary_key
        target_table['columns'][primary_key] = {'sdtype': 'id'}
    metadata.setdefault('relationships', [])

    with stage.profile_path.open('w', encoding='utf-8') as stream:
        json.dump(stage.profile, stream, indent=2)

    return metadata


def materialize_to_pipeline(
    stage: StageData,
    *,
    dataset_name: str,
    table_name: str,
    metadata_path: Path,
) -> Path:
    _ensure_dir(DATA_ROOT)
    dataset_root = DATA_ROOT / dataset_name
    marker_path = dataset_root / UPLOAD_MARKER

    if dataset_root.exists():
        if marker_path.exists():
            shutil.rmtree(dataset_root)
        else:
            raise FileExistsError(
                'A packaged dataset with this name already exists. '
                'Choose a different dataset name for uploaded data.'
            )

    dataset_root.mkdir(parents=True, exist_ok=True)

    destination_csv = dataset_root / f'{table_name}.csv'
    shutil.copy2(stage.source_path, destination_csv)
    shutil.copy2(metadata_path, dataset_root / 'metadata.json')

    marker_payload = {
        'token': stage.token,
        'source': stage.profile.get('source_filename'),
    }
    with marker_path.open('w', encoding='utf-8') as marker_file:
        json.dump(marker_payload, marker_file, indent=2)

    return dataset_root


def _sdtype_from_kind(kind: str) -> str:
    mapping = {
        'numerical': 'numerical',
        'categorical': 'categorical',
        'datetime': 'datetime',
        'boolean': 'categorical',
        'id': 'id',
    }
    return mapping.get(kind, 'categorical')
