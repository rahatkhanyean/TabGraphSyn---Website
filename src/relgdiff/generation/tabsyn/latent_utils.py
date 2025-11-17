import json
import numpy as np
import pandas as pd
import torch
import os

from relgdiff.generation.utils_train import preprocess
from relgdiff.generation.vae.model import Decoder_model


def get_input_train(
    dataname,
    is_cond=False,
    ckpt_path="ckpt",
    run="mlp",
    normalization="quantile",
):
    data_dir = "src/data"
    batch_size = 256

    train_dir = os.path.join(data_dir, "processed", dataname)
    out_dir = os.path.join(ckpt_path, dataname, "gen", run)
    os.makedirs(out_dir, exist_ok=True)

    with open(f"{train_dir}/info.json", "r") as f:
        info = json.load(f)

    ckpt_dir = os.path.join(ckpt_path, dataname, run)
    embedding_save_path = os.path.join(ckpt_path, dataname, "vae", run, "latents.npy")
    
    # If latents don't exist in the specified run folder, check in 'single_table' folder
    if not os.path.exists(embedding_save_path):
        default_embedding_path = os.path.join(ckpt_path, dataname, "vae", "single_table", "latents.npy")
        if os.path.exists(default_embedding_path):
            print(f"Latents not found in '{run}' folder, using latents from 'single_table' instead")
            embedding_save_path = default_embedding_path
    
    if is_cond:
        cond_embedding_save_path = os.path.join(ckpt_path, dataname, "cond_train_z.npy")
        train_z_cond = torch.tensor(np.load(cond_embedding_save_path), dtype=torch.float32).float()
    else:
        train_z_cond = None
    train_z = torch.tensor(np.load(embedding_save_path), dtype=torch.float32).float()

    train_z = train_z[:, 1:, :]
    B, num_tokens, token_dim = train_z.size()
    in_dim = num_tokens * token_dim

    train_z = train_z.view(B, in_dim)

    return train_z, train_z_cond, train_dir, ckpt_dir, info


def get_input_generate(
    dataname,
    ckpt_path="ckpt",
    run="mlp",
    normalization="quantile",
):
    data_dir = "src/data"
    train_dir = os.path.join(data_dir, "processed", dataname)

    ckpt_dir = os.path.join(ckpt_path, dataname, run)
    embedding_save_path = os.path.join(ckpt_path, dataname, "vae", run, "latents.npy")
    
    # If latents don't exist in the specified run folder, check in 'single_table' folder
    if not os.path.exists(embedding_save_path):
        default_embedding_path = os.path.join(ckpt_path, dataname, "vae", "single_table", "latents.npy")
        if os.path.exists(default_embedding_path):
            print(f"Latents not found in '{run}' folder, using latents from 'single_table' instead")
            embedding_save_path = default_embedding_path
    
    with open(f"{train_dir}/info.json", "r") as f:
        info = json.load(f)

    _, _, categories, d_numerical, num_inverse, cat_inverse = preprocess(
        train_dir, inverse=True, normalization=normalization
    )

    train_z = torch.tensor(np.load(embedding_save_path), dtype=torch.float32).float()

    train_z = train_z[:, 1:, :]

    B, num_tokens, token_dim = train_z.size()
    in_dim = num_tokens * token_dim

    train_z = train_z.view(B, in_dim)
    pre_decoder = Decoder_model(2, d_numerical, categories, 4, n_head=1, factor=32)

    decoder_save_path = f"{ckpt_path}/{dataname}/vae/{run}/decoder.pt"
    
    # If decoder doesn't exist in the specified run folder, check in 'single_table' folder
    if not os.path.exists(decoder_save_path):
        default_decoder_path = f"{ckpt_path}/{dataname}/vae/single_table/decoder.pt"
        if os.path.exists(default_decoder_path):
            print(f"Decoder not found in '{run}' folder, using decoder from 'single_table' instead")
            decoder_save_path = default_decoder_path
    
    pre_decoder.load_state_dict(torch.load(decoder_save_path))

    info["pre_decoder"] = pre_decoder
    info["token_dim"] = token_dim

    return train_z, train_dir, ckpt_dir, info, num_inverse, cat_inverse


@torch.no_grad()
def split_num_cat(syn_data, info, num_inverse, cat_inverse):
    if torch.cuda.is_available():
        pre_decoder = info["pre_decoder"].cuda()
    else:
        pre_decoder = info["pre_decoder"].cpu()

    token_dim = info["token_dim"]

    syn_data = syn_data.reshape(syn_data.shape[0], -1, token_dim)
    if torch.cuda.is_available():
        norm_input = pre_decoder(torch.tensor(syn_data).cuda())
    else:
        norm_input = pre_decoder(torch.tensor(syn_data).cpu())
    x_hat_num, x_hat_cat = norm_input

    syn_cat = []
    for pred in x_hat_cat:
        syn_cat.append(pred.argmax(dim=-1))

    if x_hat_num.isnan().any():
        nan_rows = torch.unique(torch.where(x_hat_num.isnan())[0])
        x_hat_num[nan_rows] = x_hat_num.nanmean(axis=0)
        print("NaNs in numerical columns")  # FIXME

    syn_num = x_hat_num.cpu().numpy()
    syn_cat = torch.stack(syn_cat).t().cpu().numpy()

    syn_num = num_inverse(syn_num)
    syn_cat = cat_inverse(syn_cat)
    return syn_num, syn_cat


def recover_data(syn_num, syn_cat, info):
    num_col_idx = info["num_col_idx"]
    cat_col_idx = info["cat_col_idx"]

    idx_mapping = info["idx_mapping"]
    idx_mapping = {int(key): value for key, value in idx_mapping.items()}

    syn_df = pd.DataFrame()

    for i in range(len(num_col_idx) + len(cat_col_idx)):
        if i in set(num_col_idx):
            syn_df[i] = syn_num[:, idx_mapping[i]]
        elif i in set(cat_col_idx):
            syn_df[i] = syn_cat[:, idx_mapping[i] - len(num_col_idx)]

    return syn_df


def process_invalid_id(syn_cat, min_cat, max_cat):
    syn_cat = np.clip(syn_cat, min_cat, max_cat)

    return syn_cat
