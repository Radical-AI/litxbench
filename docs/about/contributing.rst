Contributing to the Leaderboard
-------------------------------

We welcome community contributions to the :doc:`/leaderboard`. To add your method:

1. Run your extraction method on the LitXAlloy benchmark dataset by calling ``compare_experiments`` and ``compute_multi_level_metrics``. An example is in the `usage script <https://github.com/Radical-AI/litxbench/blob/main/examples/usage.py>`_.
2. Open a `pull request <https://github.com/Radical-AI/litxbench/pulls>`_ that adds your results as a new row to the leaderboard table in `docs/index.rst <https://github.com/Radical-AI/litxbench/blob/main/docs/index.rst>`_.

When updating `docs/index.rst <https://github.com/Radical-AI/litxbench/blob/main/docs/index.rst>`_, please include:

1. A link to the code that generated the results
2. The file containing the output experiment objects from your run
3. Any publication you'd like linked
4. A link to the PR that submitted your result
5. The version of LitXAlloy it was evaluated on (this version is bumped when the dataset or evaluation methods change, so scores across different versions may not be directly comparable). You can get this with:

   .. code-block:: python

      from litxbench.litxalloy import __version__
      print(__version__)  # e.g. "0.1.0"

Uncertainties are not required -- if your method was only run once, simply report the score without a confidence interval.

Contributing to LitXBench
-------------------------

Contributions to LitXBench are welcome! Please open an issue or pull request on the
`GitHub repository <https://github.com/Radical-AI/litxbench>`_.

Development Setup
=================

.. code-block:: bash

   git clone https://github.com/Radical-AI/litxbench.git
   cd litxbench
   uv sync --extra dev

If you want to replicate results from the paper you'll need to add ``--group paper`` to install the required dependencies.
