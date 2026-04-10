Dataset
=======

LitXBench ships with the **LitXAlloy** dataset: 19 papers on high-entropy alloys with
expert-annotated ground-truth extractions, comprising **1426 total measurements** and
**101 target materials** with **68 unique compositions**.

Benchmark Quality
-----------------

A single annotator performed the extraction for all papers to ensure consistency. The
extracted values were compared with the MPEA dataset as a safeguard against missing values.
LLMs were also employed to double-check and catch extraction mistakes -- an estimated
1.1 billion tokens were spent using Claude to catch errors. All LLM-suggested corrections
were heavily scrutinized by humans before LitXAlloy was updated.

Compared to the MPEA dataset for the 18 overlapping papers, LitXAlloy has significantly
higher data density: an average of 74.8 extracted measurements per paper versus 33.4 in MPEA,
with an additional 745 values total.

Loading the Dataset
-------------------

.. code-block:: python

   from litxbench.litxalloy import papers

   # papers is a dict mapping DOI strings to list[Experiment]
   print(f"Number of papers: {len(papers)}")

   for doi, experiments in papers.items():
       n_materials = sum(len(e.output_materials) for e in experiments)
       print(f"  {doi}: {len(experiments)} experiment(s), {n_materials} material(s)")

Included Papers
---------------

Eighteen papers are sourced from the MPEA dataset, with an additional open-access paper on
Ni-based superalloys selected for its complex synthesis process and unique experimental
measurements.

**Papers from MPEA**

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - DOI Key
     - DOI Link
   * - ``doi_10_1016__j_proeng_2012_03_043``
     - `10.1016/j.proeng.2012.03.043 <https://doi.org/10.1016/j.proeng.2012.03.043>`_
   * - ``doi_10_1038__ncomms10602``
     - `10.1038/ncomms10602 <https://doi.org/10.1038/ncomms10602>`_
   * - ``doi_10_1038__s41467_019_08460_2``
     - `10.1038/s41467-019-08460-2 <https://doi.org/10.1038/s41467-019-08460-2>`_
   * - ``doi_10_1038__s41467_019_10533_1``
     - `10.1038/s41467-019-10533-1 <https://doi.org/10.1038/s41467-019-10533-1>`_
   * - ``doi_10_1038__s41598_017_16509_9``
     - `10.1038/s41598-017-16509-9 <https://doi.org/10.1038/s41598-017-16509-9>`_
   * - ``doi_10_1038__s41598_019_43329_w``
     - `10.1038/s41598-019-43329-w <https://doi.org/10.1038/s41598-019-43329-w>`_
   * - ``doi_10_1155__2019__2157592``
     - `10.1155/2019/2157592 <https://doi.org/10.1155/2019/2157592>`_
   * - ``doi_10_3390__coatings9010016``
     - `10.3390/coatings9010016 <https://doi.org/10.3390/coatings9010016>`_
   * - ``doi_10_3390__e16020870``
     - `10.3390/e16020870 <https://doi.org/10.3390/e16020870>`_
   * - ``doi_10_3390__e18050189``
     - `10.3390/e18050189 <https://doi.org/10.3390/e18050189>`_
   * - ``doi_10_3390__e21010015``
     - `10.3390/e21010015 <https://doi.org/10.3390/e21010015>`_
   * - ``doi_10_3390__e21020114``
     - `10.3390/e21020114 <https://doi.org/10.3390/e21020114>`_
   * - ``doi_10_3390__e21020122``
     - `10.3390/e21020122 <https://doi.org/10.3390/e21020122>`_
   * - ``doi_10_3390__e21020169``
     - `10.3390/e21020169 <https://doi.org/10.3390/e21020169>`_
   * - ``doi_10_3390__e21030288``
     - `10.3390/e21030288 <https://doi.org/10.3390/e21030288>`_
   * - ``doi_10_3390__e21050448``
     - `10.3390/e21050448 <https://doi.org/10.3390/e21050448>`_
   * - ``doi_10_3390__ma12071136``
     - `10.3390/ma12071136 <https://doi.org/10.3390/ma12071136>`_
   * - ``doi_10_3390__met9030351``
     - `10.3390/met9030351 <https://doi.org/10.3390/met9030351>`_

**Non-MPEA Papers**

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - DOI Key
     - DOI Link
   * - ``doi_10_3390__met10111466``
     - `10.3390/met10111466 <https://doi.org/10.3390/met10111466>`_

Key Statistics
--------------

- **101** target materials across 19 papers
- **68** unique compositions (8 papers contain duplicate compositions)
- **26** materials derived from other materials in the dataset (across 6 papers)
- **1426** total measurements
- Only experimental and experimentally-derived measurements are included; computational
  measurements (e.g. Thermo-Calc predictions) are excluded

Data Structure
--------------

Each paper maps to a list of ``Experiment`` objects. A typical paper has 1-3 experiments,
each containing multiple output materials with their measurements.

.. code-block:: python

   from litxbench.litxalloy import papers

   doi = "doi_10_3390__e21020122"
   for exp in papers[doi]:
       print(f"Raw materials: {list(exp.raw_materials.keys())}")
       print(f"Synthesis groups: {list(exp.synthesis_group_map.keys())}")
       for mat in exp.output_materials:
           print(f"  Material: {mat.process}")
           print(f"    Measurements: {len(mat.measurements)}")
