import os
from pathlib import Path

import bico

abspath = Path(os.path.abspath(__file__)).parent  # directory of start_bico.py
os.chdir(abspath)
wd = os.getcwd()
print(f"Working directory: {wd}")
bico.main()
