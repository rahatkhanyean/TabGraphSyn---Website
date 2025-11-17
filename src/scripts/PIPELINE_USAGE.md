# Pipeline Usage Guide

This document provides instructions for using the automated pipeline script `run_pipeline.py` to preprocess, train, and sample data with a single command.

## Basic Usage

```bash
python src/scripts/run_pipeline.py --dataset-name DATASET_NAME --target-table TABLE_NAME
```

This will run the entire pipeline: preprocessing, training, and sampling.

## Examples

### Running the complete pipeline for WBCD dataset:

```bash
python src/scripts/run_pipeline.py --dataset-name WBCD --target-table WBCD --epochs-vae 500 --epochs-gnn 1000 --epochs-diff 1000
```

### Train only (skip preprocessing):

```bash
python src/scripts/run_pipeline.py --dataset-name WBCD --target-table WBCD --train-only
```

### Sample only (after training is complete):

```bash
python src/scripts/run_pipeline.py --dataset-name WBCD --target-table WBCD --sample-only --num-samples 1000
```

### Using different model parameters:

```bash
python src/scripts/run_pipeline.py --dataset-name WBCD --target-table WBCD --model-type unet --gnn-hidden 256 --positional-enc
```

## Handling PowerShell Stuck Issues

When running scripts with progress bars (tqdm) in PowerShell, the console can sometimes freeze. The pipeline provides several options to handle this:

### Option 1: Disable Progress Bars

```bash
python src/scripts/run_pipeline.py --dataset-name WBCD --target-table WBCD --disable-progress
```

This sets the TQDM_DISABLE environment variable to prevent progress bars from being displayed.

### Option 2: Redirect Output to Files

```bash
python src/scripts/run_pipeline.py --dataset-name WBCD --target-table WBCD --output-redirect
```

This redirects all command output to log files in the `logs` directory, which prevents console buffer overflow issues. The output is saved to separate log files for each step of the pipeline, making it easy to review afterward.

### Option 3: Use a Single Log File

```bash
python src/scripts/run_pipeline.py --dataset-name WBCD --target-table WBCD --output-redirect --single-log
```

This redirects all command output to a single log file with sections for each step. This makes it easier to review the entire pipeline run in one file.

### Option 4: Custom Log File Naming

```bash
python src/scripts/run_pipeline.py --dataset-name WBCD --target-table WBCD --log-prefix "experiment1" --output-redirect
```

When using output redirection, you can specify a custom prefix for your log files. This will save logs with names like `experiment1_20230415-123045.log` instead of the default `WBCD_WBCD_20230415-123045.log`, making it easier to organize output from different runs.

### Alternative: Use Command Prompt

If you continue to experience issues, try running the pipeline from Command Prompt (cmd.exe) instead of PowerShell.

## Available Options

### Mode Options
- `--preprocess-only`: Only run the preprocessing step
- `--train-only`: Only run the training step  
- `--sample-only`: Only run the sampling step
- `--skip-preprocessing`: Skip the preprocessing step

### Training Parameters
- `--epochs-vae INT`: Number of epochs for VAE training (default: 4000)
- `--epochs-gnn INT`: Number of epochs for GNN training (default: 1000)
- `--epochs-diff INT`: Number of epochs for diffusion training (default: 10000)
- `--retrain-vae`: Retrain the VAE even if it exists
- `--model-type {mlp,unet}`: Type of diffusion model (default: mlp)
- `--gnn-hidden INT`: Hidden dimension for GNN (default: 128)

### Sampling Parameters
- `--num-samples INT`: Number of samples to generate (default: same as original data)
- `--denoising-steps INT`: Number of denoising steps (default: 100)

### Other Parameters
- `--seed INT`: Random seed (default: 42)
- `--factor-missing`: Factor missing values
- `--positional-enc`: Use positional encoding
- `--normalization {quantile,standard,cdf}`: Normalization method (default: quantile)
- `--run-name STR`: Name for this run (default: single_table)
- `--disable-progress`: Disable progress bars to prevent PowerShell freezing
- `--output-redirect`: Redirect output to files to prevent PowerShell freezing
- `--log-prefix STR`: Custom prefix for log file names

## Logs

Logs for each pipeline run are saved in the `logs` directory with filename format:
`DATASET_NAME_TABLE_NAME_TIMESTAMP.log`

Command outputs are also saved in the `logs` directory when using `--output-redirect`.

## Generated Data

After successful pipeline execution, synthetic data can be found at:
`src/data/synthetic/DATASET_NAME/SingleTable/RUN_NAME/TABLE_NAME.csv` 