# Epoch-Wise Evaluation Guide for TabGraphSyn

## Overview

This guide explains how to use the epoch-wise evaluation feature that tracks **Marginal Distribution Error** and **Pairwise Correlation Error** during diffusion model training.

## What Does It Do?

The epoch-wise evaluator:
- ✅ Generates synthetic samples at regular intervals during training
- ✅ Computes **Column Shapes** score (Marginal Distribution Error)
- ✅ Computes **Column Pair Trends** score (Pairwise Correlation Error)
- ✅ Logs all metrics to JSON and CSV files
- ✅ Provides a summary at the end of training

## Quick Start

### Basic Usage

To enable epoch-wise evaluation, simply add the `--enable-epoch-eval` flag when training:

```bash
python src/scripts/single_table_gen.py \
    --dataset-name WBCD \
    --target-table WBCD \
    --train \
    --epochs-diff 1000 \
    --enable-epoch-eval
```

### With Custom Evaluation Frequency

Evaluate every 20 epochs instead of the default 10:

```bash
python src/scripts/single_table_gen.py \
    --dataset-name WBCD \
    --target-table WBCD \
    --train \
    --epochs-diff 1000 \
    --enable-epoch-eval \
    --eval-frequency 20
```

### With Custom Sample Size

Generate 1000 samples per evaluation instead of the default 500:

```bash
python src/scripts/single_table_gen.py \
    --dataset-name WBCD \
    --target-table WBCD \
    --train \
    --epochs-diff 1000 \
    --enable-epoch-eval \
    --eval-frequency 10 \
    --eval-samples 1000
```

## Command-Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--enable-epoch-eval` | flag | `False` | Enable epoch-wise evaluation during training |
| `--eval-frequency` | int | `10` | Evaluate every N epochs |
| `--eval-samples` | int | `500` | Number of synthetic samples to generate per evaluation |

## Output

### Log Files

When epoch evaluation is enabled, two files are created in `logs/training_metrics/`:

1. **JSON Log**: `{dataset}_{table}_{run}_{timestamp}.json`
   - Contains all evaluation metrics
   - Structured data format

2. **CSV Log**: `{dataset}_{table}_{run}_{timestamp}.csv`
   - Same data in tabular format
   - Easy to import into Excel or analysis tools

### Example Log Location

```
logs/training_metrics/
└── WBCD_WBCD_factor_single_table_20250116_143022.json
└── WBCD_WBCD_factor_single_table_20250116_143022.csv
```

### Log File Structure

**JSON Format**:
```json
{
  "dataname": "WBCD/WBCD_factor",
  "run": "single_table",
  "eval_frequency": 10,
  "num_eval_samples": 500,
  "denoising_steps": 20,
  "metrics_history": [
    {
      "epoch": 10,
      "train_loss": 0.0234,
      "timestamp": "2025-01-16T14:30:45.123456",
      "marginal_error": 0.6234,
      "pairwise_error": 0.5891,
      "quality_score": 0.6012,
      "num_synthetic_samples": 500,
      "num_real_samples": 500,
      "num_columns": 30
    },
    {
      "epoch": 20,
      "train_loss": 0.0198,
      "timestamp": "2025-01-16T14:32:12.789012",
      "marginal_error": 0.7123,
      "pairwise_error": 0.6734,
      "quality_score": 0.6891,
      "num_synthetic_samples": 500,
      "num_real_samples": 500,
      "num_columns": 30
    }
  ]
}
```

**CSV Format**:
```csv
epoch,train_loss,timestamp,marginal_error,pairwise_error,quality_score,num_synthetic_samples,num_real_samples,num_columns
10,0.0234,2025-01-16T14:30:45.123456,0.6234,0.5891,0.6012,500,500,30
20,0.0198,2025-01-16T14:32:12.789012,0.7123,0.6734,0.6891,500,500,30
```

### Console Output

During training, you'll see output like this:

```
[EpochEvaluator] Initialized
  - Evaluation frequency: every 10 epochs
  - Sample size: 500
  - Denoising steps: 20
  - Log file: logs/training_metrics/WBCD_WBCD_factor_single_table_20250116_143022.json
[EpochEvaluator] Loaded real data: src/data/original/WBCD/WBCD.csv
  - Shape: (569, 31)

Epoch 10/1000:
[EpochEvaluator] Evaluating at epoch 10...
  - Saved temporary checkpoint
  - Generating 500 synthetic samples...
  - Computing SDMetrics...
  ✓ Epoch 10 evaluation complete:
    - Marginal Error (Column Shapes): 0.6234
    - Pairwise Error (Column Pair Trends): 0.5891

...

============================================================
EPOCH-WISE EVALUATION SUMMARY
============================================================
Total epochs evaluated: 100
Final epoch: 1000

Marginal Error (Column Shapes):
  - Final: 0.8542
  - Best:  0.8645
  - Mean:  0.7823

Pairwise Error (Column Pair Trends):
  - Final: 0.8123
  - Best:  0.8289
  - Mean:  0.7456

Metrics saved to: logs/training_metrics/WBCD_WBCD_factor_single_table_20250116_143022.json
============================================================
```

## Metrics Explained

### Marginal Error (Column Shapes)

**What it measures**: How well the synthetic data preserves the univariate distributions of individual columns.

- **Score Range**: 0.0 to 1.0
- **Higher is Better**: 1.0 means perfect match
- **Interpretation**:
  - `> 0.9`: Excellent distribution preservation
  - `0.7 - 0.9`: Good distribution match
  - `0.5 - 0.7`: Moderate similarity
  - `< 0.5`: Poor distribution match

### Pairwise Error (Column Pair Trends)

**What it measures**: How well the synthetic data preserves correlations and associations between pairs of columns.

- **Score Range**: 0.0 to 1.0
- **Higher is Better**: 1.0 means perfect correlation preservation
- **Interpretation**:
  - `> 0.9`: Excellent correlation preservation
  - `0.7 - 0.9`: Good correlation match
  - `0.5 - 0.7`: Moderate correlation similarity
  - `< 0.5`: Poor correlation preservation

### Quality Score

**What it measures**: Overall synthetic data quality (average of all SDMetrics scores).

- **Score Range**: 0.0 to 1.0
- **Higher is Better**: Combines all quality metrics
- **Use Case**: Quick overall assessment

## Performance Considerations

### Evaluation Overhead

Epoch-wise evaluation adds some overhead to training:

- **Evaluation Time**: ~10-30 seconds per evaluation (depends on dataset size)
- **Total Overhead**: `(epochs / eval_frequency) × evaluation_time`

**Example**:
- Training for 1000 epochs with `eval_frequency=10`
- Results in 100 evaluations
- At 20 seconds per evaluation = ~33 minutes total overhead

### Optimization Tips

1. **Use smaller sample sizes** for faster evaluation:
   ```bash
   --eval-samples 300  # Instead of default 500
   ```

2. **Increase evaluation frequency** to reduce number of evaluations:
   ```bash
   --eval-frequency 50  # Evaluate every 50 epochs instead of 10
   ```

3. **The evaluator already uses optimizations**:
   - Only 20 denoising steps (vs 50-100 for final sampling)
   - Samples only up to the size of real data
   - Cleans up temporary checkpoints

### Recommended Settings

**For Development/Testing** (fast feedback):
```bash
--enable-epoch-eval --eval-frequency 5 --eval-samples 300
```

**For Production Training** (comprehensive tracking):
```bash
--enable-epoch-eval --eval-frequency 10 --eval-samples 500
```

**For Long Training Runs** (minimal overhead):
```bash
--enable-epoch-eval --eval-frequency 50 --eval-samples 500
```

## Analyzing Results

### Using Python

```python
import json
import pandas as pd
import matplotlib.pyplot as plt

# Load the JSON log
with open('logs/training_metrics/WBCD_WBCD_factor_single_table_20250116_143022.json', 'r') as f:
    data = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(data['metrics_history'])

# Plot metrics over epochs
fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# Marginal Error
axes[0, 0].plot(df['epoch'], df['marginal_error'], marker='o')
axes[0, 0].set_title('Marginal Error (Column Shapes)')
axes[0, 0].set_xlabel('Epoch')
axes[0, 0].set_ylabel('Score')
axes[0, 0].grid(True)

# Pairwise Error
axes[0, 1].plot(df['epoch'], df['pairwise_error'], marker='o', color='orange')
axes[0, 1].set_title('Pairwise Error (Column Pair Trends)')
axes[0, 1].set_xlabel('Epoch')
axes[0, 1].set_ylabel('Score')
axes[0, 1].grid(True)

# Training Loss
axes[1, 0].plot(df['epoch'], df['train_loss'], marker='o', color='red')
axes[1, 0].set_title('Training Loss')
axes[1, 0].set_xlabel('Epoch')
axes[1, 0].set_ylabel('Loss')
axes[1, 0].grid(True)

# Quality Score
axes[1, 1].plot(df['epoch'], df['quality_score'], marker='o', color='green')
axes[1, 1].set_title('Overall Quality Score')
axes[1, 1].set_xlabel('Epoch')
axes[1, 1].set_ylabel('Score')
axes[1, 1].grid(True)

plt.tight_layout()
plt.savefig('epoch_evaluation_results.png', dpi=300)
plt.show()
```

### Using Excel or Google Sheets

1. Open the CSV file directly
2. Create line charts for each metric
3. Identify trends and convergence points

## Implementation Details

### Files Modified

1. **New File**: `src/relgdiff/generation/epoch_evaluator.py`
   - Contains the `EpochEvaluator` class
   - Handles all evaluation logic

2. **Modified**: `src/relgdiff/generation/diffusion.py`
   - Added `eval_callback` parameter to `train_diff()`
   - Added callback invocation in training loop

3. **Modified**: `src/scripts/single_table_gen.py`
   - Added CLI arguments
   - Added callback initialization
   - Passes callback to training function

### How It Works

1. **Initialization**: When enabled, creates an `EpochEvaluator` instance
2. **During Training**: At specified epochs:
   - Saves temporary checkpoint
   - Generates synthetic samples using current model
   - Loads real data
   - Computes SDMetrics
   - Logs results to JSON/CSV
   - Cleans up temporary files
3. **After Training**: Prints summary statistics

### Dependencies

The feature requires:
- `sdmetrics` (already in requirements)
- `sdv` (already in requirements)
- `pandas`, `numpy`, `torch` (already available)

No additional installations needed!

## Troubleshooting

### "Could not load real data"

**Problem**: Evaluator can't find the original dataset.

**Solution**: Ensure your data is in the correct location:
```
src/data/original/{dataset_name}/{table_name}.csv
```

### "Failed to generate synthetic data"

**Problem**: Sample generation failed during evaluation.

**Possible Causes**:
- Insufficient memory
- Model not converged yet (early epochs)

**Solution**:
- Reduce `--eval-samples` to use less memory
- Start evaluation later: `--eval-frequency 20` (skips very early epochs)

### "SDMetrics not available"

**Problem**: SDMetrics library not installed.

**Solution**:
```bash
pip install sdmetrics sdv
```

## Best Practices

1. **Start with default settings** to understand baseline behavior
2. **Monitor early epochs** (0-100) to see initial convergence
3. **Adjust frequency** based on training speed and total epochs
4. **Save logs** for later analysis and comparison
5. **Compare multiple runs** to validate improvements

## Example Workflows

### Quick Test Run

```bash
# Fast test with small dataset
python src/scripts/single_table_gen.py \
    --dataset-name WBCD \
    --target-table WBCD \
    --train \
    --epochs-diff 100 \
    --enable-epoch-eval \
    --eval-frequency 10 \
    --eval-samples 200
```

### Full Training Run

```bash
# Complete training with comprehensive tracking
python src/scripts/single_table_gen.py \
    --dataset-name rossmann_subsampled \
    --target-table store \
    --train \
    --epochs-diff 10000 \
    --enable-epoch-eval \
    --eval-frequency 50 \
    --eval-samples 1000 \
    --factor-missing \
    --positional-enc
```

### Hyperparameter Tuning

```bash
# Compare different model configurations
for model in mlp unet; do
  python src/scripts/single_table_gen.py \
      --dataset-name WBCD \
      --target-table WBCD \
      --train \
      --model-type $model \
      --epochs-diff 1000 \
      --enable-epoch-eval \
      --eval-frequency 20 \
      --run "experiment_${model}"
done
```

## Web Interface Visualization

### Automatic Chart Display

When you train with epoch evaluation enabled, the **result page automatically displays interactive charts**!

**What you'll see**:
1. **Training Progress Section** - New card in the results page
2. **Two Interactive Charts**:
   - **Marginal Distribution Error Chart** (Column Shapes over epochs)
   - **Pairwise Correlation Error Chart** (Column Pair Trends over epochs)
3. **Training Loss Overlay** - Shown on both charts for comparison
4. **Download Buttons** - Save charts as PNG images

**Features**:
- ✨ **Interactive tooltips** - Hover over points to see exact values
- 📊 **Dual metrics** - Error metrics and training loss on same chart
- 📱 **Responsive design** - Works on mobile and desktop
- 💾 **Downloadable** - Export charts as high-quality PNG images
- 🎨 **Beautiful styling** - Matches TabGraphSyn design system

**Chart Details**:
- **X-axis**: Epoch number
- **Y-axis**: Score (0.0 to 1.0 for error metrics)
- **Blue line**: Marginal Distribution Error (higher is better)
- **Purple line**: Pairwise Correlation Error (higher is better)
- **Orange dashed line**: Training Loss (lower is better)

### Accessing the Charts

1. Train your model with epoch evaluation:
   ```bash
   python src/scripts/single_table_gen.py \
       --dataset-name WBCD \
       --target-table WBCD \
       --train \
       --epochs-diff 1000 \
       --enable-epoch-eval
   ```

2. Navigate to the results page after training completes

3. Scroll down to the **"Training Progress"** section

4. View the interactive charts showing your training metrics

5. Click **"Download Marginal Chart"** or **"Download Pairwise Chart"** to save

**No additional setup required!** The charts appear automatically if epoch evaluation data is available.

## Summary

The epoch-wise evaluation feature provides:
- ✅ **Real-time monitoring** of synthetic data quality
- ✅ **Marginal and pairwise error tracking** throughout training
- ✅ **Comprehensive logging** for later analysis
- ✅ **Interactive web visualizations** with Chart.js
- ✅ **Downloadable charts** as PNG images
- ✅ **Minimal code changes** (completely optional)
- ✅ **No breaking changes** to existing pipeline

Happy training! 🚀
