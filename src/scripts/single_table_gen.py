import os
import argparse

import torch
import numpy as np
import pandas as pd
from syntherela.metadata import Metadata
from syntherela.data import load_tables, remove_sdv_columns, save_tables

from relgdiff.generation.diffusion import train_diff, sample_diff
from relgdiff.generation.autoencoder import train_vae
from relgdiff.generation.utils_train import preprocess
from relgdiff.generation.tabsyn.latent_utils import get_input_train
from relgdiff.embedding_generation.embeddings import (
    train_hetero_gnn,
    compute_hetero_gnn_embeddings,
)
from relgdiff.data.utils import get_positional_encoding
from relgdiff.embedding_generation.hetero_gnns import GraphConditioning

DATA_PATH = "src/data"
CKPT_PATH = "src/ckpt"  # Updated checkpoint path


def train_single_table(
    dataset_name,
    target_table,
    run="single_table",
    retrain_vae=False,
    factor_missing=True,
    model_type="mlp",
    normalization="quantile",
    gnn_hidden=128,
    mlp_layers=3,
    positional_enc=True,
    epochs_gnn=250,
    epochs_vae=500,
    epochs_diff=500,
    seed=42,
    enable_epoch_eval=False,
    eval_frequency=10,
    eval_samples=500,
):
    """
    Train a model for single table generation using graph embeddings as conditions.
    
    Args:
        dataset_name: Name of the dataset
        target_table: Name of the table to generate
        run: Identifier for the run
        retrain_vae: Whether to retrain the VAE
        factor_missing: Whether to factor missing values
        model_type: Type of model (mlp or unet)
        normalization: Type of normalization
        gnn_hidden: Hidden channels for GNN
        mlp_layers: Number of MLP layers
        positional_enc: Whether to use positional encoding
        epochs_gnn: Number of epochs for GNN training
        epochs_vae: Number of epochs for VAE training
        epochs_diff: Number of epochs for diffusion training
        seed: Random seed
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # read data
    metadata = Metadata().load_from_json(
        f"{DATA_PATH}/original/{dataset_name}/metadata.json"
    )
    tables = load_tables(f"{DATA_PATH}/original/{dataset_name}/", metadata)
    tables, metadata = remove_sdv_columns(tables, metadata)
    
    # Fixed number of GNN layers for single table generation
    gnn_layers = 3
    
    if positional_enc:
        pos_enc, _ = get_positional_encoding(dataset_name)
    else:
        pos_enc = None

    # Verify that the target table exists
    if target_table not in metadata.get_tables():
        raise ValueError(f"Target table {target_table} not found in dataset {dataset_name}")
    
    # Verify that the target table is not a foreign key only table
    if metadata.get_column_names(target_table) == metadata.get_column_names(
        target_table, sdtype="id"
    ):
        raise ValueError(f"Target table {target_table} contains only foreign keys, cannot generate meaningful data")

    # Train VAE for the target table
    latents = {}
    embedding_dims = {}
    
    table_save_path = f"{dataset_name}/{target_table}{'_factor' if factor_missing else ''}"
    if retrain_vae or not os.path.exists(
        f"{CKPT_PATH}/{table_save_path}/vae/{run}/decoder.pt"
    ):
        print(f"Training VAE latents for table {target_table}")
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
            ckpt_dir=f"{CKPT_PATH}/{table_save_path}/vae/{run}",
            epochs=epochs_vae,
            device=device,
            seed=seed,
        )
    else:
        print(f"Reusing VAE latents for table {target_table}")
    
    table_latents = np.load(f"{CKPT_PATH}/{table_save_path}/vae/{run}/latents.npy")
    latents[target_table] = table_latents
    _, T, C = table_latents.shape
    embedding_dims[target_table] = (T - 1) * C

    # We need to run the graph embedding process for all tables
    # but will only generate data for the target table
    masked_tables = metadata.get_tables()

    # Create HeteroData object to preview model structure
    from relgdiff.data.tables_to_heterodata import tables_to_heterodata
    preview_hetero_data = tables_to_heterodata(
        tables.copy(),
        metadata,
        masked_tables,
        embedding_table=target_table,
        latents=latents,
        pos_enc=pos_enc,
    )
    
    # Print GIN model structure before training
    print("\n=== GIN Network Structure ===")
    preview_model = GraphConditioning(
        hidden_channels=gnn_hidden,
        out_channels=embedding_dims,
        types=list(preview_hetero_data.x_dict.keys()),
        data=preview_hetero_data,
        num_layers=gnn_layers,
        mlp_layers=mlp_layers,
        model_type="GIN",
        pos_enc=pos_enc,
    )
    
    # Initialize the model by performing a dummy forward pass
    try:
        with torch.no_grad():
            if pos_enc is not None:
                pos_enc_dict = preview_hetero_data.pe_dict if hasattr(preview_hetero_data, 'pe_dict') else pos_enc
            else:
                pos_enc_dict = None
            _ = preview_model(preview_hetero_data.x_dict, preview_hetero_data.edge_index_dict, pos_enc=pos_enc_dict)
        print(preview_model)
        print(f"Number of parameters: {sum(p.numel() for p in preview_model.parameters())}")
    except Exception as e:
        print(f"Model preview only - detailed parameter count unavailable: {str(e)}")
        print(preview_model)
    
    print(f"GNN layers: {gnn_layers}, MLP layers: {mlp_layers}, Hidden channels: {gnn_hidden}")
    print(f"Node types: {list(preview_hetero_data.x_dict.keys())}")
    if hasattr(preview_hetero_data, 'metadata') and preview_hetero_data.metadata() is not None:
        print(f"Edge types: {preview_hetero_data.metadata()[1]}")
    print("=============================\n")

    # Train GNN embeddings for the target table
    gnn_save_dir = f"{CKPT_PATH}/{dataset_name}/single_table_gnn"
    print(f"Training GNN embeddings for table {target_table}")
    _, hetero_data = train_hetero_gnn(
        tables,
        metadata,
        embedding_table=target_table,
        masked_tables=masked_tables,
        latents=latents,
        pos_enc=pos_enc,
        model_save_dir=gnn_save_dir,
        hidden_channels=gnn_hidden,
        num_layers=gnn_layers,
        mlp_layers=mlp_layers,
        embedding_dim=embedding_dims,
        epochs=epochs_gnn,
        seed=seed,
    )
    
    # Compute graph embeddings for the target table
    conditional_embeddings = compute_hetero_gnn_embeddings(
        hetero_data,
        embedding_table=target_table,
        model_save_dir=gnn_save_dir,
        embedding_dim=embedding_dims,
        hidden_channels=gnn_hidden,
        num_layers=gnn_layers,
        mlp_layers=mlp_layers,
        pos_enc=pos_enc,
    )

    print(f"Saving conditional embeddings for table {target_table}")
    
    # Save the conditional embeddings
    os.makedirs(f"{CKPT_PATH}/{table_save_path}/", exist_ok=True)
    np.save(f"{CKPT_PATH}/{table_save_path}/cond_train_z.npy", conditional_embeddings)

    # Train conditional diffusion for the target table
    train_z, train_z_cond, _, ckpt_path, _ = get_input_train(
        table_save_path, is_cond=True, run=run, ckpt_path=CKPT_PATH  # Pass the updated checkpoint path
    )
    print(f"Training conditional diffusion for table {target_table}")

    # Initialize epoch evaluation callback if enabled
    eval_callback = None
    if enable_epoch_eval:
        from relgdiff.generation.epoch_evaluator import EpochEvaluator
        print(f"Epoch evaluation enabled (frequency: {eval_frequency}, samples: {eval_samples})")
        eval_callback = EpochEvaluator(
            dataname=table_save_path,
            run=run,
            ckpt_path=ckpt_path,
            eval_frequency=eval_frequency,
            num_eval_samples=eval_samples,
            denoising_steps=20,  # Use fewer steps for faster evaluation
            normalization=normalization,
            device=device,
            model_type=model_type,
            is_cond=True
        )

    train_diff(
        train_z,
        train_z_cond,
        ckpt_path,
        epochs=epochs_diff,
        is_cond=True,
        model_type=model_type,
        device=device,
        seed=seed,
        eval_callback=eval_callback,
    )

    # Print evaluation summary if callback was used
    if eval_callback is not None:
        eval_callback.print_summary()

    print(f"Successfully trained conditional diffusion models for single table generation of {target_table}")


def sample_single_table(
    dataset_name,
    target_table,
    run="single_table",
    factor_missing=True,
    model_type="mlp",
    seed=None,
    denoising_steps=50,
    gnn_hidden=128,
    mlp_layers=3,
    positional_enc=True,
    normalization="quantile",
    sample_idx=None,
    num_samples=None,
):
    """
    Sample single table data using graph embeddings as conditions.
    
    Args:
        dataset_name: Name of the dataset
        target_table: Name of the table to generate
        run: Identifier for the run
        factor_missing: Whether to factor missing values
        model_type: Type of model (mlp or unet)
        seed: Random seed
        denoising_steps: Number of denoising steps
        gnn_hidden: Hidden channels for GNN
        mlp_layers: Number of MLP layers
        positional_enc: Whether to use positional encoding
        normalization: Type of normalization
        sample_idx: Sample index
        num_samples: Number of samples to generate
    """
    if seed is not None:
        torch.manual_seed(seed)
        np.random.seed(seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # read data
    metadata = Metadata().load_from_json(
        f"{DATA_PATH}/original/{dataset_name}/metadata.json"
    )
    tables = load_tables(f"{DATA_PATH}/original/{dataset_name}/", metadata)
    tables, metadata = remove_sdv_columns(tables, metadata)
    
    # Fixed number of GNN layers for single table generation
    gnn_layers = 3
    
    if positional_enc:
        pos_enc, _ = get_positional_encoding(dataset_name)
    else:
        pos_enc = None
    
    # Verify that the target table exists
    if target_table not in metadata.get_tables():
        raise ValueError(f"Target table {target_table} not found in dataset {dataset_name}")

    # Read latent embeddings dimensions to obtain GNN dimensions
    table_save_path = f"{dataset_name}/{target_table}{'_factor' if factor_missing else ''}"
    table_latents = np.load(f"{CKPT_PATH}/{table_save_path}/vae/{run}/latents.npy")
    _, T, C = table_latents.shape
    embedding_dims = {target_table: (T - 1) * C}

    # We'll use the original data to build the graph, but we'll only
    # compute embeddings and generate data for the target table
    masked_tables = metadata.get_tables().copy()
    
    # Compute GNN embeddings for the target table
    gnn_save_dir = f"{CKPT_PATH}/{dataset_name}/single_table_gnn"
    
    # Convert the tables dict to a data object to compute embeddings
    from relgdiff.data.tables_to_heterodata import tables_to_heterodata
    
    # Load the VAE latents for the target table
    latents = {target_table: table_latents}
    
    hetero_data = tables_to_heterodata(
        tables,
        metadata,
        masked_tables,
        embedding_table=target_table,
        latents=latents,
        pos_enc=pos_enc,
    )
    
    conditional_embeddings = compute_hetero_gnn_embeddings(
        hetero_data,
        embedding_table=target_table,
        model_save_dir=gnn_save_dir,
        embedding_dim=embedding_dims,
        hidden_channels=gnn_hidden,
        num_layers=gnn_layers,
        mlp_layers=mlp_layers,
        pos_enc=pos_enc,
    )

    # Define how many samples to generate
    if num_samples is None:
        num_samples = len(tables[target_table])
        
    # If we want to generate a specific number of samples, we need to adjust the
    # conditional embeddings
    if num_samples != len(conditional_embeddings):
        # Randomly sample from the conditional embeddings
        indices = np.random.choice(len(conditional_embeddings), num_samples, replace=num_samples>len(conditional_embeddings))
        conditional_embeddings = conditional_embeddings[indices]

    # Save the conditional embeddings
    os.makedirs(f"{CKPT_PATH}/{table_save_path}/{run}/gen", exist_ok=True)
    np.save(f"{CKPT_PATH}/{table_save_path}/{run}/gen/cond_z.npy", conditional_embeddings)

    # Sample diffusion
    df = sample_diff(
        table_save_path,
        run,
        is_cond=True,
        model_type=model_type,
        device=device,
        denoising_steps=denoising_steps,
        normalization=normalization,
        ckpt_path=CKPT_PATH,  # Pass the custom ckpt_path
    )

    # Postprocess the data
    table_metadata = metadata.get_table_meta(target_table, to_dict=False)

    # Handle missing values
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
    pk = metadata.get_primary_key(target_table)
    if pk is not None:
        df[pk] = np.arange(len(df))

    # For single table generation, we don't need to add foreign keys
    # as we're not generating a relational structure

    print(f"Successfully sampled data for table {target_table}")
    print(df.head())

    # Save the generated table
    save_path = f"{DATA_PATH}/synthetic/{dataset_name}/SingleTable/{run}"
    if sample_idx is not None:
        save_path = f"{save_path}/sample{sample_idx}"
    
    os.makedirs(save_path, exist_ok=True)
    df.to_csv(os.path.join(save_path, f"{target_table}.csv"), index=False)
    
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-name", type=str, default="rossmann_subsampled")
    parser.add_argument("--target-table", type=str, required=True, 
                        help="Name of the table to generate")
    parser.add_argument("--train", action="store_true", 
                        help="Train the model for single table generation")
    parser.add_argument("--sample", action="store_true", 
                        help="Sample from the trained model")
    parser.add_argument("--num-samples", default=None, type=int,
                       help="Number of samples to generate (default: same as original table)")
    parser.add_argument("--gnn-hidden", type=int, default=128)
    parser.add_argument("--denoising-steps", type=int, default=100)
    parser.add_argument("--epochs-vae", type=int, default=4000) # 4000
    parser.add_argument("--epochs-diff", type=int, default=10000) # 10000
    parser.add_argument("--epochs-gnn", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--retrain-vae", action="store_true")
    parser.add_argument("--factor-missing", action="store_true")
    parser.add_argument("--positional-enc", action="store_true")
    parser.add_argument("--run", type=str, default="single_table")
    parser.add_argument(
        "--model-type", type=str, default="mlp", choices=["mlp", "unet"]
    )
    parser.add_argument(
        "--normalization",
        type=str,
        default="quantile",
        choices=["quantile", "standard", "cdf"],
    )
    parser.add_argument("--enable-epoch-eval", action="store_true",
                       help="Enable epoch-wise evaluation during diffusion training")
    parser.add_argument("--eval-frequency", type=int, default=10,
                       help="Evaluate every N epochs (default: 10)")
    parser.add_argument("--eval-samples", type=int, default=500,
                       help="Number of samples to generate for evaluation (default: 500)")
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_name = args.dataset_name
    target_table = args.target_table
    run = args.run
    retrain_vae = args.retrain_vae
    factor_missing = args.factor_missing
    positional_enc = args.positional_enc
    seed = args.seed
    model_type = args.model_type
    gnn_hidden = args.gnn_hidden
    normalization = args.normalization
    
    if args.train:
        train_single_table(
            dataset_name=dataset_name,
            target_table=target_table,
            run=run,
            retrain_vae=retrain_vae,
            factor_missing=factor_missing,
            positional_enc=positional_enc,
            epochs_vae=args.epochs_vae,
            epochs_diff=args.epochs_diff,
            epochs_gnn=args.epochs_gnn,
            model_type=model_type,
            gnn_hidden=gnn_hidden,
            normalization=normalization,
            seed=seed,
            enable_epoch_eval=args.enable_epoch_eval,
            eval_frequency=args.eval_frequency,
            eval_samples=args.eval_samples,
        )
    
    if args.sample:
        sample_single_table(
            dataset_name=dataset_name,
            target_table=target_table,
            run=run,
            factor_missing=factor_missing,
            positional_enc=positional_enc,
            model_type=model_type,
            denoising_steps=args.denoising_steps,
            gnn_hidden=gnn_hidden,
            normalization=normalization,
            seed=seed,
            num_samples=args.num_samples,
        )


if __name__ == "__main__":
    main() 