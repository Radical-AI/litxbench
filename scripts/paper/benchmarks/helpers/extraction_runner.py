"""Shared runner infrastructure for benchmark scripts."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, TypeVar

import logfire
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded

from litxbench.core.utils import resolve_path
from scripts.paper.benchmarks.helpers.model_provider import (
    ModelProvider,
    get_model_from_name,
)
from scripts.paper.benchmarks.helpers.pricing import compute_cost
from scripts.paper.benchmarks.helpers.prompts import PromptConfig

T = TypeVar("T")
ConfigT = TypeVar("ConfigT")
OutputT = TypeVar("OutputT")


@dataclass
class BaseBenchmarkConfig:
    """Fields shared by all benchmark config dataclasses."""

    dois: list[str] | None = None
    max_workers: int | None = None
    model_name: str = ""

    def __post_init__(self) -> None:
        if self.max_workers is None:
            self.max_workers = 5 if self.model_name.startswith("gemini-3.1-pro") else 25


@dataclass
class ExperimentBenchmarkConfig(BaseBenchmarkConfig):
    """Configuration for experiment extraction benchmarks."""

    name: str = ""
    prompt_config: PromptConfig = field(default_factory=PromptConfig)


def finalize_output(output: Any, model_name: str, start_time: float) -> None:
    """Set ``elapsed_seconds`` and ``cost_usd`` on an extraction output in-place."""
    output.elapsed_seconds = time.monotonic() - start_time
    output.cost_usd = compute_cost(model_name, output.input_tokens, output.output_tokens)


def run_standard_benchmark(
    *,
    model_names: list[str],
    config: BaseBenchmarkConfig,
    output_subdir: str,
    extract_fn: Callable[..., Any],
) -> Path:
    """Shared ``__main__`` boilerplate for experiment extraction benchmarks.

    Runs extraction in parallel, evaluates against ground truth, and writes
    outputs to ``<project_root>/outputs/<output_subdir>/<run_name>_<epoch>/``.
    """
    from datetime import datetime

    from litxbench.litxalloy import papers
    from scripts.paper.benchmarks.helpers.reporting import (
        evaluate_all_and_summarize,
    )

    dois = config.dois or list(papers.keys())
    configs = {mn: replace(config, model_name=mn, dois=dois) for mn in model_names}

    run_name = getattr(config, "name", "") or "default"
    date_epoch = datetime.now().strftime("%Y%m%d_%s")
    outputs_root = Path(resolve_path("outputs")) / output_subdir / f"{run_name}_{date_epoch}"

    all_extraction_outputs, model_elapsed = asyncio.run(run_models_parallel(configs, extract_fn))

    selected_papers = {doi: papers[doi] for doi in dois}

    evaluate_all_and_summarize(
        model_names=model_names,
        dois=dois,
        ground_truth=selected_papers,
        all_extraction_outputs=all_extraction_outputs,
        model_output_dirs={name: outputs_root / name for name in model_names},
        model_elapsed=model_elapsed,
        results_csv_path=outputs_root / "results.csv",
    )

    print(f"\n{config}")
    return outputs_root


def create_default_agent(model_name: str, retries: int = 20, max_tokens: int = (2**15) - 1) -> Agent:
    """Create a pydantic-ai Agent with standard settings."""
    model_provider = ModelProvider()
    model = get_model_from_name(model_provider, model_name)
    return Agent(
        model=model,
        retries=retries,
        model_settings={"max_tokens": max_tokens},
    )


def make_extract_worker(
    extract_fn: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[tuple[str, Any]]]:
    """Create a standard worker from an extraction function.

    The returned async worker: creates an agent, times the run, computes cost,
    and returns ``(doi, output)``.

    ``extract_fn`` must have signature ``(doi, agent, config, ...) -> output``.
    Use ``functools.partial`` to bind extra keyword arguments.
    """

    async def _worker(doi: str, config: BaseBenchmarkConfig) -> tuple[str, Any]:
        from scripts.paper.benchmarks.helpers.reporting import ExtractionOutput

        agent = create_default_agent(config.model_name)
        start = time.monotonic()
        try:
            output = await extract_fn(doi, agent, config)
        except (UsageLimitExceeded, RuntimeError) as exc:
            logfire.error(
                "extraction failed for {doi}, skipping: {error}",
                doi=doi,
                error=str(exc),
            )
            output = ExtractionOutput(experiments=[])
        finalize_output(output, config.model_name, start)
        return doi, output

    return _worker


async def run_parallel(
    dois: list[str],
    max_workers: int | None,
    worker_fn: Callable[..., Awaitable[tuple[str, Any]]],
    *extra_args: Any,
) -> dict[str, Any]:
    """Run *worker_fn(doi, *extra_args)* concurrently with a semaphore.

    Uses asyncio.gather instead of ThreadPoolExecutor to avoid
    "Event loop is closed" errors from nested asyncio.run() calls.

    ``worker_fn`` must be an async function returning ``(doi, result)``.
    """
    # Limit concurrency to max_workers (like ThreadPoolExecutor but without
    # separate event loops that cause "Event loop is closed" errors).
    semaphore = asyncio.Semaphore(max_workers or 25)

    async def _bounded(doi: str) -> tuple[str, Any]:
        async with semaphore:
            return await worker_fn(doi, *extra_args)

    results_list = await asyncio.gather(*[_bounded(doi) for doi in dois])
    return {doi: output for doi, output in results_list}


async def run_models_parallel(
    configs: Mapping[str, ConfigT],
    extract_fn: Callable[[ConfigT], Awaitable[OutputT]],
) -> tuple[dict[str, OutputT], dict[str, float]]:
    """Run extract_fn for each model config in parallel, returning outputs and elapsed times."""

    async def _timed(name: str, cfg: ConfigT) -> tuple[str, OutputT, float]:
        start = time.monotonic()
        result = await extract_fn(cfg)
        elapsed = time.monotonic() - start
        return name, result, elapsed

    results = await asyncio.gather(*[_timed(name, cfg) for name, cfg in configs.items()])

    all_outputs: dict[str, OutputT] = {}
    elapsed_times: dict[str, float] = {}
    for name, output, elapsed in results:
        all_outputs[name] = output
        elapsed_times[name] = elapsed
        print(f"  [{name}] extraction complete ({elapsed:.1f}s)")

    return all_outputs, elapsed_times


def configure_logfire() -> None:
    """One-time logfire + pydantic-ai instrumentation."""
    logfire.configure(service_name="cchong/experiment-extraction", console=logfire.ConsoleOptions(min_log_level="info"))
    logfire.instrument_pydantic_ai()
