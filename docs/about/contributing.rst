Contributing
============

Contributions to LitXBench are welcome! Please open an issue or pull request on the
`GitHub repository <https://github.com/Radical-AI/litxbench>`_.

Development Setup
-----------------

.. code-block:: bash

   git clone https://github.com/Radical-AI/litxbench.git
   cd litxbench
   uv sync --extra dev

If you want to replicate results from the paper you'll need to add `--group paper` to install the required dependencies.


Contributing to the Leaderboard
-------------------------------

We welcome community contributions to the :doc:`/leaderboard`. To add your method:

1. Run your extraction method on the LitXAlloy benchmark dataset.
2. Evaluate your results using the LitXBench evaluation pipeline (see :doc:`/user/evaluation`).
3. Open a `pull request <https://github.com/Radical-AI/litxbench/pulls>`_ that adds your results as a new row to the leaderboard table in ``docs/leaderboard.rst``.

Uncertainties are not required -- if your method was only run once, simply report the score without a confidence interval.