from pathlib import Path

from single_source import get_version

__version__ = get_version(__name__, Path(__file__).parent.parent.parent)  # Single source of truth for version
# __version__ = "1.1.0"

__date__ = "14 Nov 2021"
__link_changelog__ = "https://gitlab.ethz.ch/holukas/bico/-/blob/master/CHANGELOG.md"
__link_source_code__ = "https://gitlab.ethz.ch/holukas/bico"
__link_releases__ = "https://gitlab.ethz.ch/holukas/bico/-/releases"
__link_wiki__ = "https://gitlab.ethz.ch/holukas/bico/-/wikis/home"
__license__ = "https://gitlab.ethz.ch/holukas/bico/-/blob/master/LICENSE"
__link_datablocks__ = "https://gitlab.ethz.ch/holukas/bico/-/tree/master/bico/settings/data_blocks"
