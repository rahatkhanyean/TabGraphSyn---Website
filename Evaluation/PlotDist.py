
'''
Purpose of file: 

Output evaluation metrics using datasets produced from different methods: Casc-TGAN, CTGAN, cWGAN, MedGAN, VeeGAN, CTAB-GAN

Clear prints and neat output
'''

import pandas as pd
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MinMaxScaler, StandardScaler, LabelEncoder, OneHotEncoder, OrdinalEncoder
from sklearn.ensemble import AdaBoostClassifier, AdaBoostRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn import svm
from sklearn.neighbors import KNeighborsRegressor, NearestNeighbors
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, average_precision_score, mean_squared_error, r2_score
from scipy.stats import pearsonr, wasserstein_distance, ks_2samp
import matplotlib.pyplot as plt
import seaborn as sns
from dython.nominal import associations


class models_evaluator:

    def __init__(self,
                train_set = None,
                test_set = None,
                dataset_name = "",
                categorical_cols = [],
                response_var = "",
                positive_val = None,
                pred_task = "binary_classification",
                syn_output = {},
                random_seed = None):
        super(models_evaluator, self).__init__()

        self.train_set = train_set
        self.test_set = test_set
        self.dataset_name = dataset_name
        self.categorical_cols = categorical_cols
        self.response_var = response_var
        self.positive_val = positive_val
        self.pred_task = pred_task
        self.syn_output = syn_output
        self.random_seed = random_seed
        self.dp = "{:.4f}"

        np.random.seed(self.random_seed)


#########################################################################################################################


#########################################################################################################################

    '''
    Univariate Distributions:

    Plot and calculate the difference in univariate dists between synth and training -- also compute wasserstein distace
    '''

    def univariate_stats(self, train_set = None, categorical_cols = [], syn_output = {}):

        uni_metrics = {}
        #disp_plots = ["Dimension-wise Stats", "Categorical Distributions", "Numerical Distributions"]
        disp_plots = ["Categorical Distributions", "Numerical Distributions"]
        make_fig = None
        ax = None
        measure = "mean"
        wasserstein_method = "ordinal" # One from ["ordinal", "scaled"]
        show = False
        show_rmse = True
        show_corr = True

        numeric_transformer = MinMaxScaler()
        categorical_transformer = OneHotEncoder(handle_unknown="ignore")
        numeric_cols = [col for col in train_set.columns if col not in categorical_cols]

        n_num_cols = len(numeric_cols)
        n_cat_cols = len(categorical_cols)

        pre_prc = ColumnTransformer(
            transformers=[
                ("num", numeric_transformer, numeric_cols),
                ("cat", categorical_transformer, categorical_cols),
            ]
        )

        pre_prc.fit(train_set)
        X_real = pre_prc.transform(train_set)

        if wasserstein_method == "ordinal":

            lbe_transformer = OrdinalEncoder()
            lbe_clt = ColumnTransformer(
                transformers=[
                    ("num", "passthrough", numeric_cols),
                    ("cat", lbe_transformer, categorical_cols)
                ]
            )
            lbe_clt.fit(train_set)
            X_real_lbe = lbe_clt.transform(train_set)

        prc_dim = X_real.shape[1]

        for name, syn in syn_output.items():

            wass_array = []
            ks_array = []

            X_fake = pre_prc.transform(syn)

            if measure in ['mean', 'avg']:
                real = np.ravel(X_real.mean(axis=0))
                fake = np.ravel(X_fake.mean(axis=0))
                plot_upper_bound = 1
            elif measure == 'std':
                real = np.ravel(X_real.std(axis=0))
                fake = np.ravel(X_fake.std(axis=0))
                plot_upper_bound = 0.6
            else:
                raise ValueError(f'"measure" must be "mean" or "std" but "{measure}" was specified.')
            

            corr_value = pearsonr(real, fake)[0]
            rmse_value = np.sqrt(mean_squared_error(real, fake))

            ### Below unused for now

            # if n_num_cols > 0:
            #     num_corr_value = pearsonr(real[:n_num_cols], fake[:n_num_cols])[0]
            #     num_rmse_value = np.sqrt(mean_squared_error(real[:n_num_cols], fake[:n_num_cols]))
            # else:
            #     num_rmse_value, num_corr_value = -1, -1

            # if X_real.shape[1] - n_num_cols > 0:
            #     cat_corr_value = pearsonr(real[n_num_cols:], fake[n_num_cols:])[0]
            #     cat_rmse_value = np.sqrt(mean_squared_error(real[n_num_cols:], fake[n_num_cols:]))
            # else:
            #     cat_rmse_value, cat_corr_value = -1, -1

            if wasserstein_method == "ordinal":
                X_fake_lbe = lbe_clt.transform(syn)
                for col_idx in range(n_num_cols + n_cat_cols):
                    real_vec = X_real_lbe[:,col_idx].copy()
                    fake_vec = X_fake_lbe[:,col_idx].copy()

                    wass_col = wasserstein_distance(real_vec, fake_vec)
                    wass_array.append(wass_col)
                    ks_col = ks_2samp(real_vec, fake_vec)[0]
                    ks_array.append(ks_col)

            elif wasserstein_method == "scaled":
                for col_idx in range(prc_dim):
                    real_vec = np.ravel(X_real[:,col_idx].toarray())
                    fake_vec = np.ravel(X_fake[:,col_idx].toarray())

                    wass_col = wasserstein_distance(real_vec, fake_vec)
                    wass_array.append(wass_col)
                    ks_col = ks_2samp(real_vec, fake_vec)[0]
                    ks_array.append(ks_col)
                    

            wass_dist = np.mean(wass_array)
            ks_metric = np.mean(ks_array)


            uni_metrics[name] = {"RMSE": float(self.dp.format(rmse_value)) , "Wasserstein": float(self.dp.format(wass_dist)), "Kolmogorov-Smirnov statistic": float(self.dp.format(ks_metric))}

            if name == "CasTGAN":

                if "Dimension-wise Stats" in disp_plots:

                    ### Dimension-wise Probability plot

                    fig, ax = plt.subplots(1)
                    fig.set_size_inches((6, 6))

                    ax.scatter(x=real, y=fake)
                    ax.plot([0, 1, 2], linestyle='--', c='black')
                    ax.set_xlabel('Real')
                    ax.set_ylabel('Fake')
                    ax.set_xlim(left=0, right=plot_upper_bound)
                    ax.set_ylim(bottom=0, top=plot_upper_bound)

                    s = ""
                    if show_rmse:
                        s += f'RMSE: {rmse_value:.4f}\n'
                    if show_corr:
                        s += f'CORR: {corr_value:.4f}\n'
                    if s != "":
                        ax.text(x=plot_upper_bound * 0.98, y=0,
                                s=s,
                                fontsize=12,
                                horizontalalignment='right',
                                verticalalignment='bottom')

                    if show:
                        plt.show()
                    else:
                        plt.close(fig)

                if "Categorical Distributions" in disp_plots and len(categorical_cols) > 0:

                    shape = None
                    log_counts = False

                    sbplt_divider = int(np.ceil(len(categorical_cols)/2))

                    if shape is None:
                        if len(categorical_cols) == 1:
                            shape = (1, 1)
                        elif len(categorical_cols) == 2:
                            shape = (1, 2)
                        elif len(categorical_cols) == 3:
                            shape = (1, 3)
                        else:
                            shape = (2, sbplt_divider)

                    #end_idx = sum([len(c) for c in ohe.categories_]) + len(num_cols)
                    X_fake_cat_df = syn[categorical_cols].copy()
                    X_fake_cat_df["type"] = "fake"
                    X_real_cat_df = train_set[categorical_cols].copy()
                    X_real_cat_df['type'] = 'real'
                    X_real_fake_cat = pd.concat([X_real_cat_df, X_fake_cat_df])
                    X_real_fake_cat.columns = categorical_cols + ['type']

                    fig, axes = plt.subplots(shape[0], shape[1])
                    fig.set_size_inches((9 * shape[0], 2 * shape[1]))
                    #fig.set_size_inches((6, 6))

                    for idx, ax in enumerate(axes.flatten()):
                        if idx < len(categorical_cols):
                            _plot = sns.countplot(x=categorical_cols[idx], hue='type',
                                                data=X_real_fake_cat, ax=ax,
                                                order=X_real_cat_df.iloc[:, idx].value_counts().index)
                            if idx > 0:
                                ax.get_legend().remove()
                            else:
                                ax.get_legend().remove()
                                ax.legend(loc=1)
                                #ax.legend(loc=1, fontsize = 16)
                                ax.get_legend().set_title(None)
                            if log_counts:
                                _plot.set_yscale("log")
                            ax.set_xticks([])
                            ax.set_yticks([])
                            ax.minorticks_off()
                            #ax.xlabel(fontsize = 16)
                            ax.set_ylabel(None)
                            #ax.xaxis.label.set_size(16)
                        else:
                            ax.set_visible(False)
                    plt.tight_layout()
                    plt.savefig("Someplots/{}_cat_dist.pdf".format(self.dataset_name))
                    
                    if show:
                        plt.show()
                    else:
                        plt.close(fig)

                if "Numerical Distributions" in disp_plots and len(numeric_cols) > 0:

                    shape = None
                    subsample = False

                    X_real_num_df = train_set[numeric_cols].copy()
                    X_fake_num_df = syn[numeric_cols].copy()

                    # for col in X_real_num_df.columns:
                    #     X_fake_num_df[col] = X_fake_num_df[col].where(X_fake_num_df[col] > 0, 0)
                    #     X_real_num_df[col] = np.log(X_real_num_df[col].values + 1)
                    #     X_fake_num_df[col] = np.log(X_fake_num_df[col].values + 1)

                    # scaler = MinMaxScaler()

                    # scaler.fit(X_real_num_df)

                    # X_real_num_df = scaler.transform(X_real_num_df)
                    # X_fake_num_df = scaler.transform(X_fake_num_df)

                    sbplt_divider = int(np.ceil(len(numeric_cols)/2))

                    if shape is None:
                    # by default, we plot 3 columns with up to 2 rows
                        # if numeric_cols is not None:
                        #     rows = np.minimum(len(numeric_cols) // 3, 2)
                        # else:
                        #     rows = np.minimum(X_real_num_df.shape[1] // 3, 2)

                        # if rows == 0:
                        #     shape = (1, 1)
                        # else:
                        #     shape = (rows, 3)
                        if len(numeric_cols) == 1:
                            shape = (1, 1)
                        elif len(numeric_cols) == 2:
                            shape = (1, 2)
                        elif len(numeric_cols) == 3:
                            shape = (1, 3)
                        else:
                            shape = (2, sbplt_divider)

                    if subsample:
                        real_size = int(np.minimum(X_real_num_df.shape[0], 5e4))
                        fake_size = int(np.minimum(X_fake_num_df.shape[0], 5e4))
                    else:
                        real_size = X_real_num_df.shape[0]
                        fake_size = X_fake_num_df.shape[0]

                    fig, axes = plt.subplots(nrows=shape[0], ncols=shape[1])
                    fig.set_size_inches((9 * shape[0], 3 * shape[1]))
                    # print(fig.get_figwidth(),'< width || height >', fig.get_figheight())

                    for idx, ax in enumerate(axes.flatten()):
                        if idx < len(numeric_cols):
                            sns.kdeplot(X_real_num_df.iloc[:real_size, idx].values, label='real', ax=ax, shade=True, legend=False, bw_adjust=1)
                            sns.kdeplot(X_fake_num_df.iloc[:fake_size, idx].values, label='fake', ax=ax, shade=True, legend=False, bw_adjust=1)

                            # sns.kdeplot(X_real_num_df[:real_size, idx], label='real', ax=ax, shade=True, legend=False, bw_adjust=0.02)
                            # sns.kdeplot(X_fake_num_df[:fake_size, idx], label='fake', ax=ax, shade=True, legend=False, bw_adjust=0.02)


                            min_val = np.min((X_real_num_df.iloc[:real_size, idx].values.min(), X_fake_num_df.iloc[:fake_size, idx].values.min()))
                            max_val = np.max((X_real_num_df.iloc[:real_size, idx].values.max(), X_fake_num_df.iloc[:fake_size, idx].values.max()))
                            ax.set_yticks([])
                            ax.set_xticks([min_val, max_val])
                            if numeric_cols is not None:
                                ax.set_xlabel(numeric_cols[idx], labelpad=-10)
                        else:
                            ax.set_visible(False)
                    axes.flatten()[0].legend()
                    plt.tight_layout()

                    plt.savefig("Someplots/{}_num_dist.pdf".format(self.dataset_name))

                    if show:
                        plt.show()
                    else:
                        plt.close(fig)


        
        return uni_metrics

        
        #return rmse_value, corr_value, num_rmse_value, num_corr_value, cat_rmse_value, cat_corr_value

            # upper_bound = np.maximum(np.max(real) * 1.1, np.max(fake) * 1.1)
            # upper_bound = np.minimum(1, upper_bound)

            # if measure in ['mean', 'avg']:
            #     upper_bound = 1
            # else:
            #     upper_bound = 0.6

            # ax.scatter(x=real, y=fake)
            # ax.plot([0, 1, 2], linestyle='--', c='black')
            # ax.set_xlabel('Real')
            # ax.set_ylabel('Fake')
            # ax.set_xlim(left=0, right=upper_bound)
            # ax.set_ylim(bottom=0, top=upper_bound)

            # corr_value = pearsonr(real, fake)[0]
            # rmse_value = np.sqrt(mean_squared_error(real, fake))

            # s = ""
            # if show_rmse:
            #     s += f'RMSE: {rmse_value:.4f}\n'
            # if show_corr:
            #     s += f'CORR: {corr_value:.4f}\n'
            # if s != "":
            #     ax.text(x=upper_bound * 0.98, y=0,
            #             s=s,
            #             fontsize=12,
            #             horizontalalignment='right',
            #             verticalalignment='bottom')

            # if show:
            #     plt.show()

        #return rmse_value, corr_value

#########################################################################################################################




#########################################################################################################################


