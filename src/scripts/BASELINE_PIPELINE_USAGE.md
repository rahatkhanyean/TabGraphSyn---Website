# Baseline Pipeline Usage Guide

This document provides instructions for using the automated baseline pipeline script `run_baseline_pipeline.py` to train and sample with the unconditional diffusion model.

## What is the Baseline Model?

The baseline model is an unconditional version of the diffusion model, which means:
- It uses VAE latents directly without graph embeddings
- There is no graph neural network (GNN) training step
- The diffusion model learns to generate data without conditioning on relational structure

This is useful for comparing performance with the conditional (graph-based) approach.

## Basic Usage

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name DATASET_NAME --table-name TABLE_NAME
```

This will run the entire pipeline: preprocessing, training, and sampling.

## Examples

### Running the complete pipeline for AIDS dataset:

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS
```

### Reusing existing VAE latents:

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --skip-vae
```

This reuses the VAE latents that were already trained (e.g., from the conditional version).

### Train only (skip preprocessing):

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --train-only
```

### Sample only (after training is complete):

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --sample-only --num-samples 1000
```

### Using different model parameters:

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --model-type unet --epochs-diff 5000
```

## Handling PowerShell Stuck Issues

When running scripts with progress bars (tqdm) in PowerShell, the console can sometimes freeze. The pipeline provides several options to handle this:

### Option 1: Disable Progress Bars

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --disable-progress
```

This sets the TQDM_DISABLE environment variable to prevent progress bars from being displayed.

### Option 2: Redirect Output to Files

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --output-redirect
```

This redirects all command output to log files in the `logs` directory, which prevents console buffer overflow issues.

### Option 3: Use a Single Log File

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --output-redirect --single-log
```

This redirects all command output to a single log file with sections for each step.

### Option 4: Custom Log File Naming

```bash
python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --log-prefix "unconditional_experiment" --output-redirect
```

When using output redirection, you can specify a custom prefix for your log files.

## Comparing with Conditional Model

To compare the unconditional baseline with the conditional model:

1. Run the conditional pipeline:
   ```bash
   python src/scripts/run_pipeline.py --dataset-name AIDS --target-table AIDS
   ```

2. Run the baseline pipeline:
   ```bash
   python src/scripts/run_baseline_pipeline.py --dataset-name AIDS --table-name AIDS --skip-vae
   ```

3. Compare the synthetic data in:
   - Conditional: `src/data/synthetic/AIDS/SingleTable/single_table/AIDS.csv`
   - Unconditional: `src/data/synthetic/AIDS/Baseline/unconditional/AIDS.csv`

The `--skip-vae` flag ensures you use the same VAE latents for a fair comparison. 