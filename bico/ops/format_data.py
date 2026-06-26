import pandas as pd


def make_df(data_lines, header, logger):
    """Make dataframe from list of record rows"""
    logger.info("    Converting to dataframe ...")
    df = pd.DataFrame(data_lines, columns=pd.MultiIndex.from_tuples(header))
    return df


def sort_dict_by_list(dict, by_list: list):
    """
    Sort keys in *dict* based on elements in *by_list*

    Kudos:
    * https://stackoverflow.com/questions/21773866/how-to-sort-a-dictionary-based-on-a-list-in-python
    """
    index_map = {v: i for i, v in enumerate(by_list)}
    return sorted(dict.items(), key=lambda pair: index_map[pair[0]])
