from __future__ import annotations

import base64
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from django.conf import settings
from scipy.spatial import ConvexHull

try:
    import eval_func
except ModuleNotFoundError as exc:
    eval_func = None
    EVAL_FUNC_IMPORT_ERROR = exc
else:
    EVAL_FUNC_IMPORT_ERROR = None


def calculate_area(
    foreground_points: np.ndarray,
    background_points: np.ndarray,
    vantage_point: float,
    scanning_window: float,
    angle_range: np.ndarray,
    resolution: int,
    mode: str,
) -> tuple[float, np.ndarray]:
    """Proxy coverage metric compatible with eval_func expectations."""
    try:
        fg_hull = ConvexHull(foreground_points)
        bg_hull = ConvexHull(background_points)
        fg_area = float(fg_hull.volume)
        bg_area = float(bg_hull.volume)
        ratio = fg_area / bg_area if bg_area > 0 else math.nan
    except Exception:
        ratio = math.nan
    diffs = np.zeros_like(angle_range, dtype=float)
    return (float(ratio) if not math.isnan(ratio) else math.nan, diffs)


def evaluate_synthetic_run(dataset: str, table: str, synthetic_path: Path | str | None) -> dict[str, Any]:
    """Run the evaluation pipeline for a generated dataset."""
    if synthetic_path is None:
        return {
            'status': 'skipped',
            'error': 'Synthetic output not available.',
        }

    synthetic_path = Path(synthetic_path)
    base_dir = Path(settings.BASE_DIR)
    real_path = base_dir / 'src' / 'data' / 'original' / dataset / f'{table}.csv'

    paths_payload = {
        'train': _rel_to_base(real_path),
        'synthetic': _rel_to_base(synthetic_path),
    }

    if eval_func is None:
        error_message = 'Evaluation dependencies are missing.'
        if 'EVAL_FUNC_IMPORT_ERROR' in globals() and EVAL_FUNC_IMPORT_ERROR is not None:
            error_message = f'Failed to import evaluation utilities: {EVAL_FUNC_IMPORT_ERROR}'
        return {
            'status': 'missing_dependency',
            'error': error_message,
            'paths': paths_payload,
            'resolution': 'Install the `umap-learn` package in the environment running this server.',
        }

    if not real_path.exists():
        return {
            'status': 'missing_real_data',
            'error': f'Real dataset not found at {real_path.as_posix()}',
            'paths': paths_payload,
        }
    if not synthetic_path.exists():
        return {
            'status': 'missing_synthetic',
            'error': f'Synthetic output not found at {synthetic_path.as_posix()}',
            'paths': paths_payload,
        }

    eval_func.calculate_area = calculate_area

    plots_dir = base_dir / 'Someplots'
    plots_dir.mkdir(parents=True, exist_ok=True)

    try:
        results_df = eval_func.evaluation_func(
            fake_file_ls=[synthetic_path.as_posix()],
            dataset_name=dataset,
            train_name=real_path.as_posix(),
        )
    except Exception as exc:
        return {
            'status': 'error',
            'error': str(exc),
            'paths': paths_payload,
        }

    metrics = _stringify_records(results_df)
    suffix = _infer_suffix(synthetic_path)
    plot_filename = f'UMAP_{dataset}{suffix}.png'
    plot_path = _locate_umap_plot(plots_dir, plot_filename, dataset)
    plot_payload = {
        'filename': plot_path.name if plot_path else plot_filename,
        'path': _rel_to_base(plot_path) if plot_path else None,
        'data_uri': _encode_image(plot_path) if plot_path else None,
    }

    # Generate UMAP coordinates for interactive visualization
    umap_coordinates = _generate_umap_coordinates(real_path, synthetic_path)

    return {
        'status': 'success',
        'metrics': metrics,
        'plot': plot_payload,
        'paths': paths_payload,
        'umap_coordinates': umap_coordinates,
    }


def _generate_umap_coordinates(real_path: Path, synthetic_path: Path) -> list[dict[str, Any]] | None:
    """
    Generate UMAP coordinates for both real and synthetic data for interactive visualization.
    Returns a list of coordinate dictionaries with x, y, type, and index.
    """
    try:
        # Import UMAP here to avoid dependency issues
        from umap import UMAP
        from sklearn.preprocessing import StandardScaler

        # Load real and synthetic data
        real_df = pd.read_csv(real_path)
        synthetic_df = pd.read_csv(synthetic_path)

        # Select only numeric columns for UMAP
        real_numeric = real_df.select_dtypes(include=[np.number])
        synthetic_numeric = synthetic_df.select_dtypes(include=[np.number])

        # Ensure both have the same columns
        common_cols = list(set(real_numeric.columns) & set(synthetic_numeric.columns))
        if not common_cols:
            return None

        real_numeric = real_numeric[common_cols].fillna(0)
        synthetic_numeric = synthetic_numeric[common_cols].fillna(0)

        # Combine data for UMAP fitting
        combined_data = pd.concat([real_numeric, synthetic_numeric], axis=0)

        # Standardize the data
        scaler = StandardScaler()
        combined_scaled = scaler.fit_transform(combined_data)

        # Apply UMAP
        umap_model = UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
        umap_coords = umap_model.fit_transform(combined_scaled)

        # Split back into real and synthetic
        n_real = len(real_numeric)
        real_coords = umap_coords[:n_real]
        synthetic_coords = umap_coords[n_real:]

        # Format coordinates for JavaScript
        coordinates = []

        # Add real data points
        for i, (x, y) in enumerate(real_coords):
            coordinates.append({
                'x': float(x),
                'y': float(y),
                'type': 'real',
                'index': i
            })

        # Add synthetic data points
        for i, (x, y) in enumerate(synthetic_coords):
            coordinates.append({
                'x': float(x),
                'y': float(y),
                'type': 'synthetic',
                'index': i
            })

        return coordinates

    except ImportError:
        # UMAP not available, return None
        return None
    except Exception as e:
        # Log error and return None
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to generate UMAP coordinates: {e}")
        return None


def _locate_umap_plot(plots_dir: Path, expected_name: str, dataset: str) -> Path | None:
    candidate = plots_dir / expected_name
    if candidate.exists():
        return candidate
    expected_lower = expected_name.lower()
    for path in plots_dir.glob('UMAP_*.png'):
        if path.name.lower() == expected_lower:
            return path
    dataset_tokens = [dataset.lower(), dataset.replace('/', '_').lower()]
    try:
        candidates = sorted(plots_dir.glob('UMAP_*.png'), key=lambda p: p.stat().st_mtime, reverse=True)
    except FileNotFoundError:
        return None
    for candidate in candidates:
        name_lower = candidate.name.lower()
        if any(token in name_lower for token in dataset_tokens):
            return candidate
    return None

def _stringify_records(df: pd.DataFrame | None) -> list[dict[str, str]]:
    if df is None or df.empty:
        return []
    records: list[dict[str, str]] = []
    for raw_record in df.to_dict(orient='records'):
        record: dict[str, str] = {}
        for key, value in raw_record.items():
            record[str(key)] = _stringify(value)
        records.append(record)
    return records


def _stringify(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, float):
        if math.isnan(value):
            return ''
        return f"{value}"
    if isinstance(value, (int, bool, str)):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    if pd.isna(value):
        return ''
    try:
        scalar = value.item()  # type: ignore[attr-defined]
    except AttributeError:
        scalar = value
    except Exception:
        return str(value)
    if isinstance(scalar, float) and math.isnan(scalar):
        return ''
    return str(scalar)


def _infer_suffix(fake_path: Path) -> str:
    normalised = fake_path.as_posix().lower()
    if '/singletable/single_table/' in normalised:
        return '_Cond'
    if '/baseline/unconditional/' in normalised:
        return '_Uncond'
    return ''


def _encode_image(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    encoded = base64.b64encode(raw).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def _rel_to_base(path: Path) -> str:
    base_dir = Path(settings.BASE_DIR)
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return path.as_posix()
