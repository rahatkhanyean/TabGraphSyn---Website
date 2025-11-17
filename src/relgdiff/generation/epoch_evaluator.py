"""
Epoch-wise Evaluator for Diffusion Model Training

This module provides functionality to track marginal distribution error
and pairwise correlation error during diffusion model training epochs.
"""

import os
import json
import numpy as np
import pandas as pd
import torch
from datetime import datetime
from pathlib import Path

# Import sampling and data recovery functions
from .diffusion import sample_diff
from .tabsyn.latent_utils import recover_data
from .utils_train import preprocess


class EpochEvaluator:
    """
    Handles epoch-wise evaluation during diffusion training.

    Tracks marginal distribution error (Column Shapes) and
    pairwise correlation error (Column Pair Trends) from SDMetrics.
    """

    def __init__(
        self,
        dataname,
        run,
        ckpt_path,
        eval_frequency=10,
        num_eval_samples=500,
        denoising_steps=20,
        normalization="quantile",
        device="cuda:0",
        log_dir=None,
        model_type="mlp",
        is_cond=True
    ):
        """
        Initialize the epoch evaluator.

        Args:
            dataname: Table path (e.g., "dataset_name/table_name_factor")
            run: Run identifier (e.g., "single_table")
            ckpt_path: Path to checkpoint directory
            eval_frequency: Evaluate every N epochs
            num_eval_samples: Number of synthetic samples to generate for evaluation
            denoising_steps: Number of denoising steps for sampling (lower = faster)
            normalization: Normalization method ("quantile", "standard", or "cdf")
            device: Device to use ("cuda:0" or "cpu")
            log_dir: Directory to save metrics logs (default: logs/training_metrics)
            model_type: Model type ("mlp" or "unet")
            is_cond: Whether to use conditional generation
        """
        self.dataname = dataname
        self.run = run
        self.ckpt_path = ckpt_path
        self.eval_frequency = eval_frequency
        self.num_eval_samples = num_eval_samples
        self.denoising_steps = denoising_steps
        self.normalization = normalization
        self.device = device
        self.model_type = model_type
        self.is_cond = is_cond

        # Set up logging directory
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), "logs", "training_metrics")
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        # Initialize metrics storage
        self.metrics_history = []

        # Create log filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset_table = self.dataname.replace("/", "_")
        self.log_filename = f"{dataset_table}_{self.run}_{timestamp}.json"
        self.log_filepath = os.path.join(self.log_dir, self.log_filename)

        # Load real data for evaluation
        self.real_data = None
        self.metadata = None
        self._load_real_data()

        print(f"[EpochEvaluator] Initialized")
        print(f"  - Evaluation frequency: every {eval_frequency} epochs")
        print(f"  - Sample size: {num_eval_samples}")
        print(f"  - Denoising steps: {denoising_steps}")
        print(f"  - Log file: {self.log_filepath}")

    def _load_real_data(self):
        """Load real data for evaluation."""
        try:
            # Extract dataset and table from dataname
            parts = self.dataname.split("/")
            if len(parts) >= 2:
                dataset_name = parts[0]
                table_name = parts[1].replace("_factor", "")
            else:
                dataset_name = self.dataname
                table_name = self.dataname

            # Try to load from original data directory
            original_data_path = os.path.join("src", "data", "original", dataset_name, f"{table_name}.csv")

            if os.path.exists(original_data_path):
                self.real_data = pd.read_csv(original_data_path)
                print(f"[EpochEvaluator] Loaded real data: {original_data_path}")
                print(f"  - Shape: {self.real_data.shape}")
            else:
                # Try preprocessed data
                processed_data_path = os.path.join("src", "data", "processed", self.dataname, "train.csv")
                if os.path.exists(processed_data_path):
                    self.real_data = pd.read_csv(processed_data_path)
                    print(f"[EpochEvaluator] Loaded preprocessed data: {processed_data_path}")
                    print(f"  - Shape: {self.real_data.shape}")
                else:
                    print(f"[EpochEvaluator] Warning: Could not load real data from {original_data_path} or {processed_data_path}")

            # Load metadata if available
            metadata_path = os.path.join("src", "data", "original", dataset_name, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)

        except Exception as e:
            print(f"[EpochEvaluator] Error loading real data: {e}")
            self.real_data = None

    def should_evaluate(self, epoch):
        """
        Check if evaluation should run at this epoch.

        Args:
            epoch: Current epoch number

        Returns:
            bool: True if evaluation should run
        """
        return epoch % self.eval_frequency == 0 and epoch > 0

    def evaluate_epoch(self, model, epoch, train_loss):
        """
        Perform evaluation at current epoch.

        Args:
            model: Current diffusion model
            epoch: Current epoch number
            train_loss: Current training loss

        Returns:
            dict: Metrics for this epoch
        """
        if self.real_data is None:
            print(f"[EpochEvaluator] Skipping evaluation at epoch {epoch}: No real data loaded")
            return None

        print(f"\n[EpochEvaluator] Evaluating at epoch {epoch}...")

        try:
            # Save temporary checkpoint
            temp_ckpt_path = os.path.join(self.ckpt_path, f"temp_epoch_{epoch}.pt")
            torch.save(model.state_dict(), temp_ckpt_path)
            print(f"  - Saved temporary checkpoint: {temp_ckpt_path}")

            # Generate synthetic samples
            print(f"  - Generating {self.num_eval_samples} synthetic samples...")
            synthetic_data = self._generate_samples(temp_ckpt_path)

            # Clean up temporary checkpoint
            if os.path.exists(temp_ckpt_path):
                os.remove(temp_ckpt_path)

            if synthetic_data is None:
                print(f"[EpochEvaluator] Failed to generate synthetic data at epoch {epoch}")
                return None

            # Compute metrics
            print(f"  - Computing SDMetrics...")
            metrics = self._compute_metrics(synthetic_data)

            # Add epoch and loss info
            metrics_record = {
                "epoch": epoch,
                "train_loss": float(train_loss),
                "timestamp": datetime.now().isoformat(),
                **metrics
            }

            # Store in history
            self.metrics_history.append(metrics_record)

            # Save to file
            self._save_metrics()

            print(f"  ✓ Epoch {epoch} evaluation complete:")
            print(f"    - Marginal Error (Column Shapes): {metrics.get('marginal_error', 'N/A'):.4f}")
            print(f"    - Pairwise Error (Column Pair Trends): {metrics.get('pairwise_error', 'N/A'):.4f}")

            return metrics_record

        except Exception as e:
            print(f"[EpochEvaluator] Error during evaluation at epoch {epoch}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_samples(self, temp_ckpt_path):
        """
        Generate synthetic samples using the temporary checkpoint.

        Args:
            temp_ckpt_path: Path to temporary model checkpoint

        Returns:
            pd.DataFrame: Synthetic data samples
        """
        try:
            # Use the sample_diff function from diffusion.py
            # This requires setting up the checkpoint directory structure

            # Get the directory containing the temporary checkpoint
            ckpt_dir = os.path.dirname(temp_ckpt_path)

            # Sample from the model
            synthetic_data = sample_diff(
                dataname=self.dataname,
                run=self.run,
                is_cond=self.is_cond,
                model_type=self.model_type,
                device=self.device,
                num_samples=min(self.num_eval_samples, len(self.real_data)),
                denoising_steps=self.denoising_steps,
                normalization=self.normalization,
                ckpt_path=ckpt_dir,
                seed=None
            )

            return synthetic_data

        except Exception as e:
            print(f"[EpochEvaluator] Error generating samples: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _compute_metrics(self, synthetic_data):
        """
        Compute marginal and pairwise error metrics using SDMetrics.

        Args:
            synthetic_data: Generated synthetic data

        Returns:
            dict: Computed metrics
        """
        metrics = {}

        try:
            # Import SDMetrics
            from sdmetrics.reports.single_table import QualityReport
            from sdv.metadata import SingleTableMetadata

            # Align columns between real and synthetic data
            common_columns = list(set(self.real_data.columns) & set(synthetic_data.columns))

            if len(common_columns) == 0:
                print("[EpochEvaluator] Warning: No common columns between real and synthetic data")
                return metrics

            real_subset = self.real_data[common_columns].copy()
            syn_subset = synthetic_data[common_columns].copy()

            # Sample the same number of rows from real data if needed
            if len(real_subset) > len(syn_subset):
                real_subset = real_subset.sample(n=len(syn_subset), random_state=42)

            # Create metadata
            metadata = SingleTableMetadata()
            metadata.detect_from_dataframe(real_subset)

            # Generate quality report
            quality_report = QualityReport()
            quality_report.generate(real_subset, syn_subset, metadata)

            # Extract scores
            scores = quality_report.get_properties()

            # Get Column Shapes (Marginal Distribution Error)
            if 'Column Shapes' in scores.index:
                metrics['marginal_error'] = float(scores.loc['Column Shapes', 'Score'])

            # Get Column Pair Trends (Pairwise Correlation Error)
            if 'Column Pair Trends' in scores.index:
                metrics['pairwise_error'] = float(scores.loc['Column Pair Trends', 'Score'])

            # Overall quality score
            overall_score = quality_report.get_score()
            metrics['quality_score'] = float(overall_score)

            # Additional info
            metrics['num_synthetic_samples'] = len(syn_subset)
            metrics['num_real_samples'] = len(real_subset)
            metrics['num_columns'] = len(common_columns)

        except ImportError as e:
            print(f"[EpochEvaluator] SDMetrics not available: {e}")
            print("[EpochEvaluator] Install with: pip install sdmetrics sdv")
        except Exception as e:
            print(f"[EpochEvaluator] Error computing metrics: {e}")
            import traceback
            traceback.print_exc()

        return metrics

    def _save_metrics(self):
        """Save metrics history to JSON file."""
        try:
            with open(self.log_filepath, 'w') as f:
                json.dump({
                    "dataname": self.dataname,
                    "run": self.run,
                    "eval_frequency": self.eval_frequency,
                    "num_eval_samples": self.num_eval_samples,
                    "denoising_steps": self.denoising_steps,
                    "metrics_history": self.metrics_history
                }, f, indent=2)

            # Also save as CSV for easy viewing
            if self.metrics_history:
                csv_filepath = self.log_filepath.replace('.json', '.csv')
                df = pd.DataFrame(self.metrics_history)
                df.to_csv(csv_filepath, index=False)

        except Exception as e:
            print(f"[EpochEvaluator] Error saving metrics: {e}")

    def get_metrics_summary(self):
        """
        Get a summary of metrics across all epochs.

        Returns:
            dict: Summary statistics
        """
        if not self.metrics_history:
            return {}

        df = pd.DataFrame(self.metrics_history)

        summary = {
            "total_epochs_evaluated": len(self.metrics_history),
            "final_epoch": df['epoch'].max() if 'epoch' in df.columns else None,
        }

        if 'marginal_error' in df.columns:
            summary['marginal_error_final'] = float(df['marginal_error'].iloc[-1])
            summary['marginal_error_best'] = float(df['marginal_error'].max())
            summary['marginal_error_mean'] = float(df['marginal_error'].mean())

        if 'pairwise_error' in df.columns:
            summary['pairwise_error_final'] = float(df['pairwise_error'].iloc[-1])
            summary['pairwise_error_best'] = float(df['pairwise_error'].max())
            summary['pairwise_error_mean'] = float(df['pairwise_error'].mean())

        return summary

    def print_summary(self):
        """Print a summary of evaluation results."""
        summary = self.get_metrics_summary()

        print("\n" + "="*60)
        print("EPOCH-WISE EVALUATION SUMMARY")
        print("="*60)
        print(f"Total epochs evaluated: {summary.get('total_epochs_evaluated', 0)}")
        print(f"Final epoch: {summary.get('final_epoch', 'N/A')}")
        print(f"\nMarginal Error (Column Shapes):")
        print(f"  - Final: {summary.get('marginal_error_final', 'N/A'):.4f}")
        print(f"  - Best:  {summary.get('marginal_error_best', 'N/A'):.4f}")
        print(f"  - Mean:  {summary.get('marginal_error_mean', 'N/A'):.4f}")
        print(f"\nPairwise Error (Column Pair Trends):")
        print(f"  - Final: {summary.get('pairwise_error_final', 'N/A'):.4f}")
        print(f"  - Best:  {summary.get('pairwise_error_best', 'N/A'):.4f}")
        print(f"  - Mean:  {summary.get('pairwise_error_mean', 'N/A'):.4f}")
        print(f"\nMetrics saved to: {self.log_filepath}")
        print("="*60 + "\n")
