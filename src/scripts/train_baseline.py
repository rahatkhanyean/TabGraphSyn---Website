import os
import argparse

import torch
import numpy as np
from syntherela.metadata import Metadata
from syntherela.data import load_tables, remove_sdv_columns

from relgdiff.generation.diffusion import train_diff
from relgdiff.generation.autoencoder import train_vae
from relgdiff.generation.utils_train import preprocess
from relgdiff.generation.tabsyn.latent_utils import get_input_train
from relgdiff.data.utils import get_table_order

DATA_PATH = "src/data"


############################################################################################


def train_pipline(
    dataset_name,
    table_name=None,
    retrain_vae=False,
    skip_vae=False,
    factor_missing=True,
    model_type="mlp",
    normalization="quantile",
    epochs_vae=4000,
    epochs_diff=4000,
    seed=42,
    run=None,
):
    torch.manual_seed(seed)
    np.random.seed(seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # read data
    metadata = Metadata().load_from_json(
        f"{DATA_PATH}/original/{dataset_name}/metadata.json"
    )
    tables = load_tables(f"{DATA_PATH}/original/{dataset_name}/", metadata)
    tables, metadata = remove_sdv_columns(tables, metadata)

    # If table_name is provided, only train for that table
    target_tables = [table_name] if table_name else metadata.get_tables()
    run_name = run or "baseline"

    # train variational autoencoders
    for table in target_tables:
        # skip foreign key only tables
        if metadata.get_column_names(table) == metadata.get_column_names(
            table, sdtype="id"
        ):
            continue
        table_save_path = f"{dataset_name}/{table}{'_factor' if factor_missing else ''}"
        if (retrain_vae or not os.path.exists(
            f"src/ckpt/{table_save_path}/vae/{run_name}/decoder.pt"
        )) and not skip_vae:
            print(f"Training VAE for table {table}")
            X_num, X_cat, idx, categories, d_numerical = preprocess(
                dataset_path=f"{DATA_PATH}/processed/{table_save_path}",
                normalization=normalization,
            )
            train_vae(
                X_num,
                X_cat,
                idx,
                categories,
                d_numerical,
                ckpt_dir=f"src/ckpt/{table_save_path}/vae/{run_name}",
                epochs=epochs_vae,
                device=device,
                seed=seed,
            )
        else:
            if skip_vae:
                print(f"Skipping VAE training for table {table} as requested")
            else:
                print(f"Reusing VAE for table {table}")

    # train generative model for each table (latent conditional diffusion)
    for table in get_table_order(metadata):
        # Skip tables not in target_tables
        if table_name and table != table_name:
            continue
            
        # skip foreign key only tables
        if metadata.get_column_names(table) == metadata.get_column_names(
            table, sdtype="id"
        ):
            continue
        table_save_path = f"{dataset_name}/{table}{'_factor' if factor_missing else ''}"

        os.makedirs(f"src/ckpt/{table_save_path}/", exist_ok=True)

        # train conditional diffusion
        train_z, _, _, ckpt_path, _ = get_input_train(
            table_save_path, is_cond=False, run=run_name, ckpt_path="src/ckpt"
        )
        print(f"Training unconditional diffusion for table {table}")
        train_diff(
            train_z,
            None,
            ckpt_path,
            epochs=epochs_diff,
            is_cond=False,
            model_type=model_type,
            device=device,
            seed=seed,
        )


############################################################################################


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-name", type=str, default="rossmann_subsampled")
    parser.add_argument("--table-name", type=str, default=None, help="Specific table to train on")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--retrain_vae", action="store_true")
    parser.add_argument("--skip-vae", action="store_true", help="Skip VAE training and reuse existing latents")
    parser.add_argument("--epochs-vae", type=int, default=4000)
    parser.add_argument("--epochs-diff", type=int, default=10000)
    parser.add_argument("--factor-missing", action="store_true")
    parser.add_argument("--run", type=str, default="baseline")
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
    retrain_vae = args.retrain_vae
    skip_vae = args.skip_vae
    epochs_vae = args.epochs_vae
    epochs_diff = args.epochs_diff
    factor_missing = args.factor_missing
    model_type = args.model_type
    normalization = args.normalization
    run = args.run
    train_pipline(
        dataset_name=dataset_name,
        table_name=table_name,
        retrain_vae=retrain_vae,
        skip_vae=skip_vae,
        factor_missing=factor_missing,
        epochs_vae=epochs_vae,
        epochs_diff=epochs_diff,
        model_type=model_type,
        normalization=normalization,
        run=run,
    )


if __name__ == "__main__":
    main()
