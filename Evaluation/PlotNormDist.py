import numpy as np
import pandas as pd

class models_evaluator:
    def __init__(self, train_set, test_set, dataset_name, categorical_cols, response_var, pred_task, syn_output, random_seed=0, positive_val=None):
        self.train_set = train_set
        self.test_set = test_set
        self.dataset_name = dataset_name
        self.categorical_cols = list(categorical_cols or [])
        self.response_var = response_var
        self.pred_task = pred_task
        self.syn_output = syn_output
        self.random_seed = random_seed
        self.positive_val = positive_val

    def univariate_stats(self, train_set, categorical_cols, syn_output):
        cat_cols = list(categorical_cols or [])
        num_cols = train_set.select_dtypes(include=[np.number]).columns.tolist()
        results = {}
        for name, syn_df in syn_output.items():
            metrics = {}
            # Align columns to avoid missing keys
            shared_cols = [col for col in num_cols if col in syn_df.columns]
            if shared_cols:
                real_numeric = train_set[shared_cols].apply(pd.to_numeric, errors='coerce')
                syn_numeric = syn_df[shared_cols].apply(pd.to_numeric, errors='coerce')
                metrics['numeric_mean_mae'] = float(np.nanmean(np.abs(real_numeric.mean() - syn_numeric.mean())))
                metrics['numeric_std_mae'] = float(np.nanmean(np.abs(real_numeric.std(ddof=0) - syn_numeric.std(ddof=0))))
            if cat_cols:
                overlaps = []
                for col in cat_cols:
                    if col not in syn_df.columns:
                        continue
                    real_counts = train_set[col].astype(str).value_counts(normalize=True)
                    syn_counts = syn_df[col].astype(str).value_counts(normalize=True)
                    categories = real_counts.index.union(syn_counts.index)
                    diff = np.abs(real_counts.reindex(categories, fill_value=0) - syn_counts.reindex(categories, fill_value=0))
                    overlaps.append(float(1 - 0.5 * diff.sum()))
                if overlaps:
                    metrics['categorical_avg_overlap'] = float(np.mean(overlaps))
            results[name] = metrics
        return results
