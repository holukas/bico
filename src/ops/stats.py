import numpy as np
import pandas as pd


def calc(stats_df, stats_coll_df, bin_filedate, counter_bin_files, logger):
    """Calculate stats for raw data"""
    logger.info("    Calculating stats ...")

    if stats_df.empty:
        # In case there are no data, create df with one row of NaNs
        stats_df = pd.DataFrame(index=[0], columns=stats_df.columns)

    # Replace missing values -9999 with NaNs for correct stats calcs
    stats_df.replace(-9999, np.nan, inplace=True)

    stats_df['index'] = bin_filedate
    stats_df.sort_index(axis=1, inplace=True)  # lexsort for better performance
    aggs = ['count', 'min', 'max', 'mean', 'std', 'median', q01, q05, q95, q99]
    stats_df = stats_df.groupby('index').agg(aggs)

    # else:
    #     # In case there are no data in the file, create a dataframe containing only missing
    #     # values and add it to the stats collection.
    #     else:
    #         num_cols = stats_coll_df.columns.size  # Count number of columns
    #     nan_list = []
    #     [nan_list.append(-9999) for x in range(0, num_cols, 1)]  # Create missing values for each column
    #     stats_df = pd.DataFrame(index=[bin_filedate], data=[nan_list],
    #                             columns=pd.MultiIndex.from_tuples(stats_coll_df.columns))

    # First file inits stats collection
    if counter_bin_files == 1:
        stats_coll_df = stats_df.copy()
    else:
        stats_coll_df = stats_coll_df.append(stats_df)

    return stats_coll_df


def q01(x):
    return x.quantile(0.01)


def q05(x):
    return x.quantile(0.05)


def q95(x):
    return x.quantile(0.95)


def q99(x):
    return x.quantile(0.99)
