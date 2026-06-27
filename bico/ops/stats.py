import warnings

import numpy as np
import pandas as pd


def calc(stats_df, stats_coll_df, bin_filedate, counter_bin_files, logger):
    """Calculate stats for raw data"""
    logger.info("    Calculating stats ...")

    had_no_rows = stats_df.empty
    if had_no_rows:
        # In case there are no data, create df with one row of NaNs
        stats_df = pd.DataFrame(index=[0], columns=stats_df.columns)

    # Replace missing values -9999 with NaNs for correct stats calcs
    stats_df.replace(-9999, np.nan, inplace=True)

    # A variable that has data rows but no valid values at all (everything
    # missing) is usually a sign of a misconfiguration — e.g. an instrument /
    # data block defined in the settings that isn't actually present in the
    # binary. Numpy used to surface this as a raw "Mean of empty slice"
    # RuntimeWarning, but that goes to stderr and corrupts the live TUI display.
    # Report it through the logger instead (shown in the TUI, saved to the run
    # log), so the useful signal is kept but routed through the proper channel.
    if not had_no_rows:
        empty_vars = [c for c in stats_df.columns if stats_df[c].isna().all()]
        if empty_vars:
            names = ', '.join(_var_label(c) for c in empty_vars)
            logger.warning(f"    No valid data for {len(empty_vars)} variable(s) "
                           f"(all values missing) - check instrument settings: {names}")

    stats_df['index'] = bin_filedate
    stats_df.sort_index(axis=1, inplace=True)  # lexsort for better performance
    aggs = ['count', 'min', 'max', 'mean', 'std', 'median', q01, q05, q95, q99]
    # All-missing variables leave all-NaN slices, so numpy still emits "Mean of
    # empty slice"/"Degrees of freedom <= 0" RuntimeWarnings here. NaN is the
    # intended result, and the warning above already reported the cause in a
    # readable way, so silence the raw stderr noise (which corrupts the TUI).
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
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
        # DataFrame.append was removed in pandas 2.0, use pd.concat instead
        stats_coll_df = pd.concat([stats_coll_df, stats_df])

    return stats_coll_df


def _var_label(col):
    """Readable label for a column key (a ``(name, units, instr)`` tuple or str)."""
    if isinstance(col, tuple):
        parts = [str(p) for p in col if p is not None and str(p) != '']
        return ' '.join(parts) if parts else str(col)
    return str(col)


def q01(x):
    return x.quantile(0.01)


def q05(x):
    return x.quantile(0.05)


def q95(x):
    return x.quantile(0.95)


def q99(x):
    return x.quantile(0.99)
