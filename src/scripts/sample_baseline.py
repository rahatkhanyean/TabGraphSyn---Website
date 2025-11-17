#!/usr/bin/env python
import os
import torch
import numpy as np
import pandas as pd
import argparse
import warnings

from syntherela.metadata import Metadata
from syntherela.data import load_tables, remove_sdv_columns

import sys

from relgdiff.generation.diffusion import sample_diff
from relgdiff.data.utils import encode_datetime


def sample_pipline(
    dataset_name,
    table_name=None,
    run="baseline",
    factor_missing=False,
    model_type="mlp",
    normalization="quantile",
    seed=None,
    denoising_steps=50,
    device="cuda",
    num_samples=None,
):
    """Sample data from a trained model."""
    if seed:
        torch.manual_seed(seed)
        np.random.seed(seed)

    # read data
    metadata = Metadata().load_from_json(
        f"src/data/original/{dataset_name}/metadata.json"
    )
    tables = load_tables(f"src/data/original/{dataset_name}/", metadata)
    tables, metadata = remove_sdv_columns(tables, metadata)

    # If table_name is provided, only sample for that table
    target_tables = [table_name] if table_name else metadata.get_tables()

    for table in target_tables:
        # skip foreign key only tables
        if metadata.get_column_names(table) == metadata.get_column_names(
            table, sdtype="id"
        ):
            print(f"Skipping foreign key only table {table}")
            continue

        table_save_path = f"{dataset_name}/{table}{'_factor' if factor_missing else ''}"
        table_metadata = metadata.get_table_meta(table, to_dict=False)

        # Get the number of rows to generate
        if num_samples is None:
            num_samples = tables[table].shape[0]
        print(f"Generating {num_samples} rows for table {table}")

        os.makedirs(
            f"src/data/synthetic/{dataset_name}/Baseline/{run}", exist_ok=True
        )

        df = sample_diff(
            table_save_path,
            run=run,
            is_cond=False,
            model_type=model_type,
            device=device,
            num_samples=num_samples,
            denoising_steps=denoising_steps,
            normalization=normalization,
            ckpt_path="src/ckpt",
        )

        # Add the columns back to the dataframe
        column_mapping = {i: col for i, col in enumerate(table_metadata.columns)}
        df = df.rename(columns=column_mapping, inplace=False)

        # handle missing values
        cat_columns = df.select_dtypes(include=["object"]).columns.to_list()
        for col in cat_columns:
            if col not in table_metadata.columns and factor_missing:
                imputed_column = col.split("_missing")[0]
                missing_mask = df[col].astype(int).astype(bool)
                df[imputed_column] = df[imputed_column].astype("float64")
                df.loc[missing_mask, imputed_column] = np.nan
                df = df.drop(columns=[col])
                continue
            elif "?" in df[col].unique():
                df[col] = df[col].replace("?", np.nan)

        # Convert dates to datetime
        datetime_columns = table_metadata.get_column_names(sdtype="datetime")
        for col in datetime_columns:
            date_columns = [f"{col}_Year", f"{col}_Month", f"{col}_Day"]
            date_df = pd.DataFrame(
                df[date_columns].values, columns=["year", "month", "day"]
            ).round(0)
            fmt = "%Y%m%d"
            if f"{col}_Hour" in df.columns:
                date_df["hour"] = df[f"{col}_Hour"].values.round(0)
                date_df["minute"] = df[f"{col}_Minute"].values.round(0)
                date_df["second"] = df[f"{col}_Second"].values.round(0)
                date_columns.extend([f"{col}_Hour", f"{col}_Minute", f"{col}_Second"])
                fmt += "%H%M%S"
            df[col] = pd.to_datetime(dict(date_df), format=fmt, errors="coerce")
            df = df.drop(columns=date_columns)

        # Add primary key if needed
        pk = metadata.get_primary_key(table)
        if pk is not None:
            df[pk] = np.arange(len(df))

        # Save the generated table
        df.to_csv(f"src/data/synthetic/{dataset_name}/Baseline/{run}/{table}.csv", index=False)
        print(f"Generated table saved to src/data/synthetic/{dataset_name}/Baseline/{run}/{table}.csv")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-name", type=str, default="rossmann_subsampled")
    parser.add_argument("--table-name", type=str, default=None, help="Specific table to sample")
    parser.add_argument("--run", type=str, default="baseline")
    parser.add_argument("--factor-missing", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--denoising-steps", type=int, default=50)
    parser.add_argument("--num-samples", type=int, default=None)
    parser.add_argument(
        "--model-type", type=str, default="mlp", choices=["mlp", "unet"]
    )
    parser.add_argument(
        "--normalization",
        type=str,
        default="quantile",
        choices=["quantile", "standard", "cdf"],
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_name = args.dataset_name
    table_name = args.table_name
    run = args.run
    factor_missing = args.factor_missing
    seed = args.seed
    model_type = args.model_type
    normalization = args.normalization
    denoising_steps = args.denoising_steps
    num_samples = args.num_samples
    sample_pipline(
        dataset_name=dataset_name,
        table_name=table_name,
        run=run,
        factor_missing=factor_missing,
        model_type=model_type,
        seed=seed,
        denoising_steps=denoising_steps,
        normalization=normalization,
        num_samples=num_samples,
    )


if __name__ == "__main__":
    main()
