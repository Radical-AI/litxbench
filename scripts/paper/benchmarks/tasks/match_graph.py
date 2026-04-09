"""Paper-matching benchmark using graph (anonymized topology) redaction.

Each paper is matched against 19 shuffled, topology-preserving experiment
summaries.  The LLM must identify which summary belongs to the paper.
"""

from scripts.paper.benchmarks.helpers.extraction_runner import configure_logfire
from scripts.paper.benchmarks.helpers.matching_helpers import (
    redact_experiments_graph,
    run_matching_benchmark,
)

configure_logfire()

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

    run_matching_benchmark(
        model_names=model_names,
        redact_fn=redact_experiments_graph,
        output_subdir="match_graph",
        benchmark_name="match_graph",
    )
