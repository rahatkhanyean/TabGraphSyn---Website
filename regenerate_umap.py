#!/usr/bin/env python
"""
Script to regenerate UMAP coordinates for existing result files.
This adds interactive UMAP data to results that were generated before
the interactive feature was implemented.
"""

import json
import sys
from pathlib import Path

# Add the project directory to the Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Set up Django
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabgraphsyn_site.settings')
django.setup()

from synthetic.evaluation import _generate_umap_coordinates


def regenerate_umap_for_result(metadata_path: Path):
    """Regenerate UMAP coordinates for a single result file."""
    print(f"Processing: {metadata_path.name}")

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Check if it already has UMAP coordinates
    evaluation = metadata.get('evaluation', {})
    if evaluation.get('umap_coordinates'):
        print(f"  [OK] Already has UMAP coordinates, skipping")
        return

    # Check if we have the necessary paths
    if evaluation.get('status') != 'success':
        print(f"  [SKIP] Evaluation not successful, skipping")
        return

    paths = evaluation.get('paths', {})
    real_path_str = paths.get('train')
    synthetic_path_str = paths.get('synthetic')

    if not real_path_str or not synthetic_path_str:
        print(f"  [SKIP] Missing data paths, skipping")
        return

    # Convert relative paths to absolute
    real_path = Path(BASE_DIR) / real_path_str
    synthetic_path = Path(BASE_DIR) / synthetic_path_str

    if not real_path.exists():
        print(f"  [ERROR] Real data not found: {real_path}")
        return

    if not synthetic_path.exists():
        print(f"  [ERROR] Synthetic data not found: {synthetic_path}")
        return

    # Generate UMAP coordinates
    print(f"  [INFO] Generating UMAP coordinates...")
    try:
        umap_coords = _generate_umap_coordinates(real_path, synthetic_path)
    except Exception as e:
        print(f"  [ERROR] Exception during UMAP generation: {e}")
        return

    if umap_coords is None:
        print(f"  [ERROR] Failed to generate UMAP coordinates (returned None)")
        return

    # Update the metadata
    metadata['evaluation']['umap_coordinates'] = umap_coords

    # Save the updated metadata
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"  [SUCCESS] Added UMAP coordinates ({len(umap_coords)} points)")


def main():
    """Process all result metadata files."""
    generated_dir = BASE_DIR / 'media' / 'generated'

    if not generated_dir.exists():
        print(f"Generated directory not found: {generated_dir}")
        return

    # Find all metadata JSON files
    metadata_files = list(generated_dir.glob('*.json'))

    if not metadata_files:
        print("No result files found")
        return

    print(f"Found {len(metadata_files)} result file(s)")
    print("=" * 60)

    success_count = 0
    for metadata_path in metadata_files:
        try:
            regenerate_umap_for_result(metadata_path)
            success_count += 1
        except Exception as e:
            print(f"  [ERROR] Error processing {metadata_path.name}: {e}")

    print("=" * 60)
    print(f"Completed: {success_count}/{len(metadata_files)} files processed successfully")


if __name__ == '__main__':
    main()
