"""Full experiment extraction benchmark (zero-shot, linear).

Like zero_shot.py but each material independently describes its full process
chain from raw materials — no inter-material dependencies.
"""

from functools import partial

from litxbench.litxalloy import papers
from scripts.paper.benchmarks.helpers.extraction_runner import (
    ExperimentBenchmarkConfig,
    configure_logfire,
    make_extract_worker,
    run_parallel,
    run_standard_benchmark,
)
from scripts.paper.benchmarks.helpers.reporting import (
    ExtractionOutput,
)
from scripts.paper.benchmarks.tasks.zero_shot import _extract_zero_shot

configure_logfire()

_extract_worker = make_extract_worker(partial(_extract_zero_shot, linear=True))


async def extract_experiments_zero_shot_linear(
    config: ExperimentBenchmarkConfig,
) -> dict[str, ExtractionOutput]:
    dois = config.dois if config.dois is not None else list(papers.keys())
    return await run_parallel(dois, config.max_workers, _extract_worker, config)


if __name__ == "__main__":
    model_names = [
        # "claude-haiku-4-5",
        # "gpt-5-mini-medium",
        # "gemini-3-flash",
        # "claude-opus-4-6",
        # "gpt-5-2-high",
        # "gemini-3.1-pro",
        "gemini-3.1-flash-lite",
    ]
    # dois = list(papers.keys())
    # dois = list(papers.keys())[:3]
    dois = ["doi_10_1016__j_proeng_2012_03_043"]

    run_standard_benchmark(
        model_names=model_names,
        config=ExperimentBenchmarkConfig(name="extract_all_linear", dois=dois),
        output_subdir="zero_shot_linear",
        extract_fn=extract_experiments_zero_shot_linear,
    )
