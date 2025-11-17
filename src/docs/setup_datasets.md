# Setting Up Your Datasets

This guide will help you set up your datasets for use with the relational graph-conditioned diffusion model for single table generation.

## Directory Structure

The model expects datasets to be organized in the following structure:
```
src/data/
  original/
    DATASET_NAME/
      metadata.json
      DATASET_NAME.csv
```

## Step 1: Place CSV Files

We've already created the necessary directories for your datasets:
- `src/data/original/AIDS/`
- `src/data/original/MIMIC/`
- `src/data/original/TCGA/`
- `src/data/original/WBCD/`

Copy your CSV files into these directories with matching filenames:
- `src/data/original/AIDS/AIDS.csv`
- `src/data/original/MIMIC/MIMIC.csv`
- `src/data/original/TCGA/TCGA.csv`
- `src/data/original/WBCD/WBCD.csv`

## Step 2: Update Metadata Files

We've created basic metadata JSON files for each dataset, but they need to be updated with the actual columns from your CSV files.

Run the provided script to update the metadata files:

```bash
python src/scripts/update_metadata.py
```

This will scan each CSV file and update the corresponding metadata.json with the correct column information.

If you want to update just one dataset:

```bash
python src/scripts/update_metadata.py --dataset DATASET_NAME
```

Replace `DATASET_NAME` with one of: `AIDS`, `MIMIC`, `TCGA`, `WBCD`.

## Step 3: Preprocess the Data

After setting up your datasets, you need to preprocess them:

```bash
python src/preprocess_data.py --dataset-name DATASET_NAME
```

## Step 4: Apply Graph Structure

Run the fix script to ensure proper graph relationships:

```bash
python src/scripts/fix_single_table_graph.py
```

## Step 5: Train and Sample

Now you can train and sample using the single table generation script:

To train:
```bash
python src/scripts/single_table_gen.py --dataset-name DATASET_NAME --target-table DATASET_NAME --train
```

To sample:
```bash
python src/scripts/single_table_gen.py --dataset-name DATASET_NAME --target-table DATASET_NAME --sample --num-samples 1000
```

## Example (WBCD dataset)

1. Place WBCD.csv in src/data/original/WBCD/
2. Update metadata: `python src/scripts/update_metadata.py --dataset WBCD`
3. Preprocess: `python src/preprocess_data.py --dataset-name WBCD`
4. Fix graph structure: `python src/scripts/fix_single_table_graph.py`
5. Train: `python src/scripts/single_table_gen.py --dataset-name WBCD --target-table WBCD --train`
6. Sample: `python src/scripts/single_table_gen.py --dataset-name WBCD --target-table WBCD --sample --num-samples 1000` 