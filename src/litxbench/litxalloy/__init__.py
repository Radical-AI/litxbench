# hardcode version as it's separate from litxbench
__version__ = "0.1.0"

from litxbench.core.extraction_utils import (  # noqa: F401
    balance_composition,
    composition_with_weight_additions,
)
from litxbench.litxalloy.extractions import (
    doi_10_1016__j_proeng_2012_03_043,
    doi_10_1038__ncomms10602,
    doi_10_1038__s41467_019_08460_2,
    doi_10_1038__s41467_019_10533_1,
    doi_10_1038__s41598_017_16509_9,
    doi_10_1038__s41598_019_43329_w,
    doi_10_1155__2019__2157592,
    doi_10_3390__coatings9010016,
    doi_10_3390__e16020870,
    doi_10_3390__e18050189,
    # doi_10_3390__e18080289,
    doi_10_3390__e21010015,
    doi_10_3390__e21020114,
    doi_10_3390__e21020122,
    doi_10_3390__e21020169,
    doi_10_3390__e21030288,
    doi_10_3390__e21050448,
    doi_10_3390__ma12071136,
    doi_10_3390__met9030351,
    doi_10_3390__met10111466,
)
from litxbench.litxalloy.models import (
    AlloyExperiment as Experiment,
)

papers: dict[str, list[Experiment]] = {
    "doi_10_1016__j_proeng_2012_03_043": doi_10_1016__j_proeng_2012_03_043.experiments,
    "doi_10_1038__ncomms10602": doi_10_1038__ncomms10602.experiments,
    "doi_10_1038__s41467_019_08460_2": doi_10_1038__s41467_019_08460_2.experiments,
    "doi_10_1038__s41467_019_10533_1": doi_10_1038__s41467_019_10533_1.experiments,
    "doi_10_1038__s41598_017_16509_9": doi_10_1038__s41598_017_16509_9.experiments,
    "doi_10_1038__s41598_019_43329_w": doi_10_1038__s41598_019_43329_w.experiments,
    "doi_10_1155__2019__2157592": doi_10_1155__2019__2157592.experiments,
    "doi_10_3390__coatings9010016": doi_10_3390__coatings9010016.experiments,
    "doi_10_3390__e16020870": doi_10_3390__e16020870.experiments,
    "doi_10_3390__e18050189": doi_10_3390__e18050189.experiments,
    # "doi_10_3390__e18080289": doi_10_3390__e18080289.experiments, # this is a correction to 10.3390@e18050189. I added this here to show that correction dois can appear in datasets
    "doi_10_3390__e21010015": doi_10_3390__e21010015.experiments,
    "doi_10_3390__e21020114": doi_10_3390__e21020114.experiments,
    "doi_10_3390__e21020122": doi_10_3390__e21020122.experiments,
    "doi_10_3390__e21020169": doi_10_3390__e21020169.experiments,
    "doi_10_3390__e21030288": doi_10_3390__e21030288.experiments,
    "doi_10_3390__e21050448": doi_10_3390__e21050448.experiments,
    "doi_10_3390__ma12071136": doi_10_3390__ma12071136.experiments,
    "doi_10_3390__met9030351": doi_10_3390__met9030351.experiments,
    "doi_10_3390__met10111466": doi_10_3390__met10111466.experiments,
}
