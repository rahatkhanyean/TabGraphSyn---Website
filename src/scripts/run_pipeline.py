#!/usr/bin/env python
"""
Complete pipeline for relational graph conditioned diffusion.
This script automates the entire process from preprocessing to sampling for any dataset.
"""

import os
import argparse
import subprocess
import time
import sys
from pathlib import Path

def run_command(command, description, env=None):
    """Run a command and handle errors"""
    print(f"\n{'='*80}\n{description}\n{'='*80}")
    print(f"Running: {command}")
    
    # Create output log file name based on description
    if args.output_redirect:
        # Create a unique log file name
        os.makedirs("logs", exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        # Use custom prefix if provided
        if args.log_prefix:
            output_file = f"logs/{args.log_prefix}_{description.replace(' ', '_').lower()}_{timestamp}.txt"
        else:
            output_file = f"logs/{description.replace(' ', '_').lower()}_{timestamp}.txt"
        
        # Use standard redirection which works in all shells
        command_with_redirect = f"{command} > {output_file} 2>&1"
    else:
        command_with_redirect = command
    
    # For Windows compatibility, use shell=True
    result = subprocess.run(command_with_redirect, shell=True, env=env)
    
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(f"Return code: {result.returncode}")
        if args.output_redirect:
            print(f"See log file for details: {output_file}")
        choice = input("Command failed. Do you want to continue anyway? (y/n): ")
        if choice.lower() != 'y':
            sys.exit(1)
    return result

def main():
    global args
    
    parser = argparse.ArgumentParser(description="Run the complete pipeline for graph-conditioned diffusion")
    
    # Dataset parameters
    parser.add_argument("--dataset-name", type=str, required=True, help="Name of the dataset")
    parser.add_argument("--target-table", type=str, required=True, help="Target table to generate")
    
    # Mode parameters
    parser.add_argument("--preprocess-only", action="store_true", help="Only run preprocessing step")
    parser.add_argument("--train-only", action="store_true", help="Only run training step")
    parser.add_argument("--sample-only", action="store_true", help="Only run sampling step")
    parser.add_argument("--skip-preprocessing", action="store_true", help="Skip preprocessing step")
    
    # Training parameters
    parser.add_argument("--epochs-vae", type=int, default=4000, help="Number of epochs for VAE training")
    parser.add_argument("--epochs-gnn", type=int, default=1000, help="Number of epochs for GNN training")
    parser.add_argument("--epochs-diff", type=int, default=10000, help="Number of epochs for diffusion training")
    parser.add_argument("--retrain-vae", action="store_true", help="Retrain the VAE even if it exists")
    parser.add_argument("--model-type", type=str, default="mlp", choices=["mlp", "unet"], help="Type of diffusion model")
    parser.add_argument("--gnn-hidden", type=int, default=128, help="Hidden dimension for GNN")
    
    # Sampling parameters
    parser.add_argument("--num-samples", type=int, default=None, help="Number of samples to generate")
    parser.add_argument("--denoising-steps", type=int, default=100, help="Number of denoising steps")
    
    # Other parameters
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--factor-missing", action="store_true", help="Factor missing values")
    parser.add_argument("--positional-enc", action="store_true", help="Use positional encoding")
    parser.add_argument("--normalization", type=str, default="quantile", 
                       choices=["quantile", "standard", "cdf"], help="Normalization method")
    parser.add_argument("--run-name", type=str, default="single_table", help="Name for this run")
    parser.add_argument("--disable-progress", action="store_true", help="Disable progress bars to prevent PowerShell freezing")
    parser.add_argument("--output-redirect", action="store_true", help="Redirect output to files to prevent PowerShell freezing")
    parser.add_argument("--log-prefix", type=str, help="Custom prefix for log file names")
    parser.add_argument("--single-log", action="store_true", help="Use a single log file for all commands")

    # Epoch evaluation parameters
    parser.add_argument("--enable-epoch-eval", action="store_true", help="Enable epoch-wise evaluation during training")
    parser.add_argument("--eval-frequency", type=int, default=10, help="Evaluate every N epochs")
    parser.add_argument("--eval-samples", type=int, default=500, help="Number of synthetic samples to generate per evaluation")

    args = parser.parse_args()
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    
    # Use custom prefix if provided, otherwise use dataset and table names
    if args.log_prefix:
        log_prefix = args.log_prefix
    else:
        log_prefix = f"{args.dataset_name}_{args.target_table}"
    
    # When using single-log, only create one log file for everything
    if args.single_log:
        log_file = log_dir / f"{log_prefix}_pipeline_{timestamp}.log"
        print(f"Using single log file for all output: {log_file}")
    else:
        log_file = log_dir / f"{log_prefix}_{timestamp}.log"
    
    # Determine which steps to run
    run_all = not (args.preprocess_only or args.train_only or args.sample_only)
    run_preprocess = (run_all or args.preprocess_only) and not args.skip_preprocessing
    run_train = run_all or args.train_only
    run_sample = run_all or args.sample_only
    
    # Create necessary directories
    os.makedirs("src/data/processed", exist_ok=True)
    os.makedirs("src/ckpt", exist_ok=True)
    
    # Set environment variables based on options
    env = os.environ.copy()
    if args.disable_progress:
        env["TQDM_DISABLE"] = "1"
        print("Progress bars disabled")
    
    # Log parameters
    with open(log_file, "w") as f:
        f.write(f"Pipeline run for {args.dataset_name}/{args.target_table}\n")
        f.write(f"Started at: {timestamp}\n")
        f.write(f"Parameters: {vars(args)}\n\n")
        f.write(f"{'='*80}\n\n")
    
    try:
        # Step 1: Preprocess data
        if run_preprocess:
            cmd = f"python src/scripts/preprocess_data.py --dataset-name {args.dataset_name}"
            if args.factor_missing:
                cmd += " --factor-missing"
            if args.output_redirect:
                if args.single_log:
                    run_command_with_single_log(cmd, "PREPROCESSING DATA", log_file, env)
                else:
                    run_command(cmd, "PREPROCESSING DATA", env)
            else:
                run_command_no_redirect(cmd, "PREPROCESSING DATA", env)
            
        # Step 2: Train models
        if run_train:
            train_params = (
                f"--dataset-name {args.dataset_name} "
                f"--target-table {args.target_table} "
                f"--train "
                f"--epochs-vae {args.epochs_vae} "
                f"--epochs-gnn {args.epochs_gnn} "
                f"--epochs-diff {args.epochs_diff} "
                f"--gnn-hidden {args.gnn_hidden} "
                f"--model-type {args.model_type} "
                f"--normalization {args.normalization} "
                f"--seed {args.seed} "
                f"--run {args.run_name} "
            )
            
            if args.retrain_vae:
                train_params += "--retrain-vae "
            if args.factor_missing:
                train_params += "--factor-missing "
            if args.positional_enc:
                train_params += "--positional-enc "
            if args.enable_epoch_eval:
                train_params += "--enable-epoch-eval "
                train_params += f"--eval-frequency {args.eval_frequency} "
                train_params += f"--eval-samples {args.eval_samples} "

            cmd = f"python src/scripts/single_table_gen.py {train_params}"
            if args.output_redirect:
                if args.single_log:
                    run_command_with_single_log(cmd, "TRAINING MODELS", log_file, env)
                else:
                    run_command(cmd, "TRAINING MODELS", env)
            else:
                run_command_no_redirect(cmd, "TRAINING MODELS", env)
        
        # Step 3: Sample data
        if run_sample:
            sample_params = (
                f"--dataset-name {args.dataset_name} "
                f"--target-table {args.target_table} "
                f"--sample "
                f"--denoising-steps {args.denoising_steps} "
                f"--model-type {args.model_type} "
                f"--seed {args.seed} "
                f"--run {args.run_name} "
            )
            
            if args.num_samples:
                sample_params += f"--num-samples {args.num_samples} "
            if args.factor_missing:
                sample_params += "--factor-missing "
            if args.positional_enc:
                sample_params += "--positional-enc "
                
            cmd = f"python src/scripts/single_table_gen.py {sample_params}"
            if args.output_redirect:
                if args.single_log:
                    run_command_with_single_log(cmd, "SAMPLING DATA", log_file, env)
                else:
                    run_command(cmd, "SAMPLING DATA", env)
            else:
                run_command_no_redirect(cmd, "SAMPLING DATA", env)
        
        # Log completion
        with open(log_file, "a") as f:
            f.write(f"\n\n{'='*80}\n")
            f.write(f"PIPELINE COMPLETED SUCCESSFULLY!\n")
            f.write(f"Completed at: {time.strftime('%Y%m%d-%H%M%S')}\n")
            f.write(f"Generated samples: src/data/synthetic/{args.dataset_name}/SingleTable/{args.run_name}/{args.target_table}.csv\n")
            f.write(f"{'='*80}\n")
        
        print(f"\n{'='*80}")
        print(f"PIPELINE COMPLETED SUCCESSFULLY!")
        print(f"Log file: {log_file}")
        print(f"Generated samples: src/data/synthetic/{args.dataset_name}/SingleTable/{args.run_name}/{args.target_table}.csv")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"Error during pipeline execution: {e}")
        with open(log_file, "a") as f:
            f.write(f"ERROR: {e}\n")
        return 1
    
    return 0

def run_command_with_single_log(command, description, log_file, env=None):
    """Run a command and append output to a single log file"""
    print(f"\n{'='*80}\n{description}\n{'='*80}")
    print(f"Running: {command}")
    
    # Create header for this section in the log file
    with open(log_file, "a") as f:
        f.write(f"\n\n{'='*80}\n{description}\n{'='*80}\n")
        f.write(f"Command: {command}\n\n")
    
    # Run the command and append output to the log file
    command_with_redirect = f"{command} >> {log_file} 2>&1"
    
    # For Windows compatibility, use shell=True
    result = subprocess.run(command_with_redirect, shell=True, env=env)
    
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(f"Return code: {result.returncode}")
        print(f"See log file for details: {log_file}")
        choice = input("Command failed. Do you want to continue anyway? (y/n): ")
        if choice.lower() != 'y':
            sys.exit(1)
    
    return result

def run_command_no_redirect(command, description, env=None):
    """Run a command without redirection"""
    print(f"\n{'='*80}\n{description}\n{'='*80}")
    print(f"Running: {command}")
    
    # For Windows compatibility, use shell=True
    result = subprocess.run(command, shell=True, env=env)
    
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(f"Return code: {result.returncode}")
        choice = input("Command failed. Do you want to continue anyway? (y/n): ")
        if choice.lower() != 'y':
            sys.exit(1)
    return result

if __name__ == "__main__":
    sys.exit(main()) 
