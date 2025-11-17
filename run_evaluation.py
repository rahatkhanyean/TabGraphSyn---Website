import os
import numpy as np
from scipy.spatial import ConvexHull
import eval_func


def calculate_area(
    foreground_points,
    background_points,
    vantage_point,
    scanning_window,
    angle_range,
    resolution,
    mode,
):
    """Approximate coverage ratio between real and combined embeddings."""
    try:
        fg_hull = ConvexHull(foreground_points)
        bg_hull = ConvexHull(background_points)
        fg_area = float(fg_hull.volume)
        bg_area = float(bg_hull.volume)
        ratio = fg_area / bg_area if bg_area > 0 else np.nan
    except Exception:
        ratio = np.nan
    diffs = np.zeros_like(angle_range, dtype=float)
    return float(ratio) if not np.isnan(ratio) else float("nan"), diffs


def main():
    train_path = r"D:\Personal\Assessment - UAB\TabGraphSyn - Django\src\data\original\aids_aids_single_table_1\aids_aids_single_table_1.csv"
    synthetic_path = r"D:\Personal\Assessment - UAB\TabGraphSyn - Django\src\data\synthetic\aids_aids_single_table_1\SingleTable\single_table\aids_aids_single_table_1.csv"

    eval_func.calculate_area = calculate_area

    os.makedirs('Someplots', exist_ok=True)

    results = eval_func.evaluation_func(
        fake_file_ls=[synthetic_path],
        dataset_name='AIDS',
        train_name=train_path,
    )

    print('Evaluation results:')
    print(results.to_string(index=False))
    results.to_csv('evaluation_results.csv', index=False)


if __name__ == '__main__':
    main()
