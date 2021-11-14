import argparse
from pathlib import Path


def validate_args(args):
    """Check validity of optional args"""
    pass
    # if args.limitnumfiles < 0:
    #     raise argparse.ArgumentTypeError("LIMITNUMFILES must be 0 or a positive integer.")
    # if args.lsnumiter < 1:
    #     raise argparse.ArgumentTypeError("LSNUMITER must be > 1.")
    # if (args.lspercthres < 0.1) | (args.lspercthres > 1):
    #     raise argparse.ArgumentTypeError("LSPERCTHRES must be between 0.1 and 1.")
    # if args.lssegmentduration > args.fileduration:
    #     raise argparse.ArgumentTypeError("LSSEGMENTDURATION must be shorter or equal to FILEDURATION.")
    # if not args.lssegmentduration:
    #     # If not specified, then lag times are determined using all of the file data
    #     args.lssegmentduration = args.fileduration
    # if args.lsnumiter <= 0:
    #     raise argparse.ArgumentTypeError("LSNUMITER must be a positive integer.")
    # args.lsremovefringebins = True if args.lsremovefringebins == 1 else False  # Translate settings to bool
    # args.delprevresults = True if args.delprevresults == 1 else False  # Translate settings to bool
    return args


def get_args():
    """Get args from CLI input"""
    parser = argparse.ArgumentParser(description="BICO - Conversion of ETH binary files to ASCII",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # # Positional args
    # parser.add_argument('settings_file', type=str,
    #                     help="soon")

    # # Optional args
    # parser.add_argument('-i', '--indir', type=Path,
    #                     help="Path to the source folder that contains the data files, e.g. 'C:/bico/input'")

    args = parser.parse_args()
    return args
