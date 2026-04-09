import inspect
import json
import os
import re
import shlex
import shutil
import subprocess
import textwrap
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from litxbench.core.extraction_utils import (
    balance_composition,
    composition_with_weight_additions,
)
from litxbench.core.utils import resolve_path
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import Experiment, Material
from scripts.paper.benchmarks.helpers.material_utils import (
    filter_materials_by_measurement_kinds,
)
from scripts.paper.benchmarks.helpers.prompts import (
    PromptConfig,
    available_names,
    composition_helpers,
    example_experiment_shape,
    field_instructions,
    normalize_function,
    scope_rules,
)
from scripts.paper.benchmarks.helpers.reporting import (
    ExtractionOutput,
    evaluate_all_and_summarize,
)

_SANDBOX_COPY_FILES: tuple[str, ...] = (
    "core/enums.py",
    "core/models.py",
    "core/units.py",
    "core/utils.py",
    "core/validators.py",
    "litxalloy/models.py",
)


def _build_sandbox_litxalloy_content() -> str:
    """Build sandbox litxalloy.py from the real function source code."""
    src = (
        "from pymatgen.core.composition import Composition\n\n\n"
        + textwrap.dedent(inspect.getsource(composition_with_weight_additions))
        + "\n\n"
        + textwrap.dedent(inspect.getsource(balance_composition))
    )
    return src


_SANDBOX_EXTRACTION_UTILS_CONTENT = (
    textwrap.dedent(
        """
    from typing import TypeVar

    T = TypeVar("T")


    def normalize(val: T, val_in_paper: str, source: str | None = None) -> T:
        return val
    """
    ).strip()
    + "\n"
)

_SANDBOX_PYPROJECT_CONTENT = (
    textwrap.dedent(
        """
    [project]
    name = "agentic-cli-sandbox"
    version = "0.0.1"
    requires-python = ">=3.12"
    dependencies = [
      "pint",
      "pydantic",
      "pymatgen",
    ]
    """
    ).strip()
    + "\n"
)

_RUN_COUNTER_SITECUSTOMIZE = textwrap.dedent("""\
    import os as _os
    import sys as _sys

    _target = _os.environ.get("_RUN_COUNTER_TARGET", "")
    if _target and _sys.argv and _os.path.basename(_sys.argv[0]) == _target:
        _counter_file = _os.path.join(_os.getcwd(), ".run_count")
        try:
            _count = int(open(_counter_file).read().strip())
        except (FileNotFoundError, ValueError, OSError):
            _count = 0
        with open(_counter_file, "w") as _f:
            _f.write(str(_count + 1))
""")


class AgenticCli(Enum):
    codex = "codex"
    claude_code = "claude_code"
    gemini_cli = "gemini_cli"


AGENTIC_CLI_COMMANDS: dict[AgenticCli, str] = {
    AgenticCli.codex: "codex exec --json --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --model gpt-5.2-codex -c reasoning_effort=high {prompt}",
    AgenticCli.claude_code: "claude --model claude-opus-4-6 -p {prompt} --output-format json --dangerously-skip-permissions",
    AgenticCli.gemini_cli: "gemini --model gemini-3.1-pro-preview -p {prompt} --output-format json --yolo",
}


def _default_output_python_filename() -> str:
    date_prefix = datetime.now().strftime("%Y%m%d")
    unix_seconds = int(datetime.now().timestamp())
    return f"{date_prefix}_{unix_seconds}.py"


@dataclass(frozen=True)
class AgenticCliConfig:
    """Configuration for an agentic CLI extraction run."""

    cli: AgenticCli
    max_workers: int = 8
    output_python_filename: str = field(default_factory=_default_output_python_filename)
    prompt_config: PromptConfig = field(default_factory=PromptConfig)

    @property
    def command_template(self) -> str:
        return AGENTIC_CLI_COMMANDS[self.cli]

    def save(self, run_root: Path) -> None:
        """Write config as JSON to *run_root*/config.json."""
        data = {
            "cli": self.cli.value,
            "command_template": self.command_template,
            "max_workers": self.max_workers,
            "output_python_filename": self.output_python_filename,
            "include_composition_helpers": self.prompt_config.include_composition_helpers,
            "include_normalize_function": self.prompt_config.include_normalize_function,
            "include_source": self.prompt_config.include_source,
        }
        (run_root / "config.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class BenchmarkConfig:
    """Top-level config selecting which CLIs to run in parallel."""

    name: str
    cli_configs: list[AgenticCliConfig]


@dataclass(frozen=True)
class CliUsage:
    """Token and cost information extracted from CLI output."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0


def _parse_codex_usage(stdout: str) -> CliUsage:
    """Parse token usage from codex --json JSONL output."""
    input_tokens = 0
    output_tokens = 0
    cached_input_tokens = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
            input_tokens += usage.get("input_tokens", 0)
            output_tokens += usage.get("output_tokens", 0)
            cached_input_tokens += usage.get("cached_input_tokens", 0)
    return CliUsage(input_tokens=input_tokens, output_tokens=output_tokens, cache_read_tokens=cached_input_tokens)


def _parse_claude_code_usage(stdout: str) -> CliUsage:
    """Parse token usage and cost from claude --output-format json output."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return CliUsage()
    usage = data.get("usage", {})
    input_tokens = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    return CliUsage(
        input_tokens=input_tokens,
        output_tokens=usage.get("output_tokens", 0),
        cost_usd=data.get("total_cost_usd", 0.0),
    )


def _parse_gemini_cli_usage(stdout: str) -> CliUsage:
    """Parse token usage from gemini --output-format json output."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return CliUsage()
    models = data.get("stats", {}).get("models", {})
    input_tokens = 0
    output_tokens = 0
    cached_tokens = 0
    for model_stats in models.values():
        tokens = model_stats.get("tokens", {})
        input_tokens += tokens.get("prompt", 0)
        output_tokens += tokens.get("candidates", 0)
        cached_tokens += tokens.get("cached", 0)
    return CliUsage(input_tokens=input_tokens, output_tokens=output_tokens, cache_read_tokens=cached_tokens)


def _parse_cli_usage(cli: AgenticCli, stdout: str) -> CliUsage:
    """Dispatch to the appropriate CLI output parser."""
    parsers = {
        AgenticCli.codex: _parse_codex_usage,
        AgenticCli.claude_code: _parse_claude_code_usage,
        AgenticCli.gemini_cli: _parse_gemini_cli_usage,
    }
    parser = parsers.get(cli)
    if parser is None:
        return CliUsage()
    try:
        return parser(stdout)
    except Exception:
        return CliUsage()


_GENAI_PRICES_MODEL_MAP: dict[str, str] = {
    "gpt-5.2-codex": "gpt-5.2",
    "gemini-3.1-pro-preview": "gemini-3-pro-preview",
}


def _compute_cost_if_needed(cli: AgenticCli, usage: CliUsage, command_template: str) -> CliUsage:
    """If cost_usd is 0 but tokens are available, compute cost via genai_prices."""
    if usage.cost_usd > 0 or (usage.input_tokens == 0 and usage.output_tokens == 0):
        return usage
    model_match = re.search(r"--model\s+(\S+)", command_template)
    if model_match is None:
        return usage
    model_name = _GENAI_PRICES_MODEL_MAP.get(model_match.group(1), model_match.group(1))
    provider_map: dict[AgenticCli, str] = {
        AgenticCli.codex: "openai",
        AgenticCli.gemini_cli: "google",
    }
    provider_id = provider_map.get(cli)
    if provider_id is None:
        return usage
    try:
        from genai_prices import calc_price
        from pydantic_ai.usage import RunUsage

        run_usage = RunUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
        )
        price = calc_price(run_usage, model_name, provider_id=provider_id)
        return CliUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cost_usd=float(price.total_price),
        )
    except Exception:
        return usage


def _transcribed_dir_for_doi(doi: str) -> Path:
    return Path(resolve_path(f"src/litxbench/litxalloy/transcribed/{doi}"))


def _build_agentic_prompt(config: AgenticCliConfig, doi: str) -> str:
    pc = config.prompt_config
    import_lines = [
        "`from pymatgen.core import Composition`",
        "`from pymatgen.core.lattice import Lattice`",
        "`from litxbench.core.models import CompositionMeasurement, CompMeasurement, CoreMeasurementValue, GlobalLatticeParam, LatticeMeasurement, MeasurementStatistic, Configuration`",
        "`from litxbench.core.enums import ConfigTag, CrysStruct, MeasurementMethod`",
        "`from litxbench.core.units import Atm, Celsius, GigaPascal, HV, Kelvin, MegaPascal, Micrometer, Nanometer, dimensionless, gram_per_cm3, percent, ureg`",
    ]
    if pc.include_composition_helpers:
        import_lines.append("`from litxbench.litxalloy import balance_composition, composition_with_weight_additions`")
    if pc.include_normalize_function:
        import_lines.append("`from litxbench.core.extraction_utils import normalize`")
    import_lines.append(
        "`from litxbench.litxalloy.models import AlloyMeasurementKind, PhaseMeasurementKind, Experiment, Measurement, ProcessEvent, Quantity, RawMaterial, RawMaterialKind, Material, ValueQualifier`"
    )
    imports_block = "\n".join(f"   - {line}" for line in import_lines)

    sections = [
        "You are extracting alloy experiments from a transcribed paper directory.\n\n"
        "Ground rules:\n"
        "- Only use files in the current working directory.\n"
        "- Do not look outside this directory.\n"
        "- You only have access to the paper's markdown (.md) file in the `transcribed/` directory. There are no images available.\n"
        "- " + scope_rules().replace("\n", "\n- ") + "\n\n"
        f"Task:\n"
        f"1) Read the transcribed paper markdown file from the `transcribed/` directory.\n"
        f"2) Create a Python file named `{config.output_python_filename}` that defines:\n"
        f"   `extracted_experiments: list[Experiment]`\n"
        f"3) Use these imports in that file:\n"
        f"{imports_block}\n"
        f"4) Run `uv run python {config.output_python_filename}` after writing the file. If the command fails with a validation error, read the error message, fix the Python file accordingly, and re-run until it succeeds.\n\n"
        "Required output shape in Python:\n" + example_experiment_shape(include_source=pc.include_source),
        field_instructions(include_source=pc.include_source),
        available_names(
            include_composition_helpers=pc.include_composition_helpers,
            include_normalize_function=pc.include_normalize_function,
        ),
    ]
    if pc.include_composition_helpers:
        sections.append(composition_helpers())
    if pc.include_normalize_function:
        sections.append(normalize_function())
    sections.append(f"DOI: {doi}")

    return "\n\n".join(sections)


_STRIP_ENV_VARS = {
    "VIRTUAL_ENV",
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_OAUTH_TOKEN",
}


def _sandbox_env() -> dict[str, str]:
    """Return a copy of os.environ with problematic vars removed.

    Stripping VIRTUAL_ENV prevents uv from conflicting with the parent
    project's venv. Stripping CLAUDECODE / CLAUDE_CODE_ENTRYPOINT allows
    launching Claude Code as a subprocess without the nested-session guard.
    Stripping CLAUDE_CODE_OAUTH_TOKEN forces Claude Code to use
    ANTHROPIC_API_KEY instead of the (possibly exhausted) OAuth credits.
    """
    return {k: v for k, v in os.environ.items() if k not in _STRIP_ENV_VARS}


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(content, encoding="utf-8")


def _setup_sandbox_project(
    sandbox_dir: Path,
    *,
    prompt_config: PromptConfig | None = None,
) -> None:
    pc = prompt_config or PromptConfig()
    project_src_root = Path(resolve_path("src/litxbench"))
    sandbox_package_root = sandbox_dir / "litxbench"

    for relative_path in _SANDBOX_COPY_FILES:
        source_file = project_src_root / relative_path
        target_file = sandbox_package_root / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(source_file, target_file)

    # Create __init__.py files so the sandbox package hierarchy is importable.
    _init_dirs = [
        sandbox_package_root,
        sandbox_package_root / "core",
        sandbox_package_root / "litxalloy",
    ]
    for d in _init_dirs:
        d.mkdir(parents=True, exist_ok=True)
        init_file = d / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

    if pc.include_composition_helpers:
        # Write composition helpers so the prompted import path works:
        #   from litxbench.litxalloy import balance_composition, ...
        _write_file(
            sandbox_package_root / "litxalloy/__init__.py",
            _build_sandbox_litxalloy_content(),
        )
    if pc.include_normalize_function:
        _write_file(
            sandbox_package_root / "core/extraction_utils.py",
            _SANDBOX_EXTRACTION_UTILS_CONTENT,
        )
    _write_file(sandbox_dir / "pyproject.toml", _SANDBOX_PYPROJECT_CONTENT)

    # Pre-create the sandbox venv so that neither the agentic CLI nor the
    # verification step need uv to create one at runtime (avoids the
    # system-configuration NULL-object panic on macOS).
    _ = subprocess.run(
        ["uv", "sync"],
        cwd=sandbox_dir,
        check=True,
        env=_sandbox_env(),
    )

    # Install a sitecustomize.py that counts how many times the output
    # script is executed (controlled by _RUN_COUNTER_TARGET env var).
    site_packages_dirs = list((sandbox_dir / ".venv" / "lib").glob("python*/site-packages"))
    if site_packages_dirs:
        _write_file(site_packages_dirs[0] / "sitecustomize.py", _RUN_COUNTER_SITECUSTOMIZE)


def _create_run_root(config_name: str, cli_name: str) -> Path:
    date_epoch = datetime.now().strftime("%Y%m%d_%s")
    run_root = Path(resolve_path("outputs")) / "zero_shot_agentic_cli" / f"{config_name}_{date_epoch}" / cli_name
    run_root.mkdir(parents=True, exist_ok=True)
    return run_root


def _create_doi_sandbox(
    run_root: Path,
    doi: str,
    *,
    prompt_config: PromptConfig | None = None,
) -> Path:
    safe_doi = doi.replace("/", "_").replace("@", "_")
    doi_dir = run_root / "environment" / safe_doi
    doi_dir.mkdir(parents=True, exist_ok=False)
    _setup_sandbox_project(
        doi_dir,
        prompt_config=prompt_config,
    )
    source_transcribed_dir = _transcribed_dir_for_doi(doi)
    if not source_transcribed_dir.is_dir():
        raise FileNotFoundError(f"Transcribed directory does not exist for DOI {doi}: {source_transcribed_dir}")
    transcribed_dest = doi_dir / "transcribed"
    transcribed_dest.mkdir(parents=True, exist_ok=False)
    for item in source_transcribed_dir.iterdir():
        if item.is_file() and item.suffix == ".md":
            shutil.copy2(item, transcribed_dest / item.name)
    return doi_dir


def _read_run_count(sandbox_dir: Path) -> int:
    """Read the run counter file written by sitecustomize.py."""
    counter_file = sandbox_dir / ".run_count"
    try:
        return int(counter_file.read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        return 1


def _extract_and_format_single_doi_agentic_cli(
    doi: str, config: AgenticCliConfig, run_root: Path
) -> tuple[str, str, CliUsage, int, float]:
    start = time.monotonic()
    doi_sandbox_dir = _create_doi_sandbox(
        run_root,
        doi,
        prompt_config=config.prompt_config,
    )

    prompt_text = _build_agentic_prompt(config, doi)

    # Build command as a list to avoid shell quoting issues with the
    # (potentially very large) prompt text.
    _placeholder = "__PROMPT_PLACEHOLDER__"
    template_with_placeholder = config.command_template.replace("{prompt}", _placeholder)
    cmd_parts = shlex.split(template_with_placeholder)
    cmd = [prompt_text if part == _placeholder else part for part in cmd_parts]

    # Set _RUN_COUNTER_TARGET so the sandbox's sitecustomize.py counts
    # how many times the agentic CLI runs the output script.
    cli_env = _sandbox_env()
    cli_env["_RUN_COUNTER_TARGET"] = config.output_python_filename
    result = subprocess.run(
        cmd,
        cwd=doi_sandbox_dir,
        capture_output=True,
        text=True,
        env=cli_env,
        timeout=1800,  # 30 minutes
    )

    # Save raw CLI output for debugging (always, even on failure)
    _write_file(doi_sandbox_dir / "cli_stdout.txt", result.stdout)
    _write_file(doi_sandbox_dir / "cli_stderr.txt", result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"CLI exited with code {result.returncode}. "
            f"stdout: {result.stdout[:500]!r} | stderr: {result.stderr[:500]!r}"
        )

    # Parse token usage and compute cost
    usage = _parse_cli_usage(config.cli, result.stdout)
    usage = _compute_cost_if_needed(config.cli, usage, config.command_template)

    # Read how many times the CLI ran the output script
    attempts = _read_run_count(doi_sandbox_dir)

    generated_python_path = doi_sandbox_dir / config.output_python_filename
    if not generated_python_path.is_file():
        raise FileNotFoundError(
            f"Agentic CLI did not create expected file: {generated_python_path}. "
            + "Update the prompt/command template to produce this output."
        )

    # Verification run — uses plain _sandbox_env() (no _RUN_COUNTER_TARGET)
    # so it doesn't inflate the attempt count.
    _ = subprocess.run(
        ["uv", "run", "python", str(generated_python_path)],
        cwd=doi_sandbox_dir,
        check=True,
        env=_sandbox_env(),
    )

    python_file_content = generated_python_path.read_text(encoding="utf-8")
    elapsed = time.monotonic() - start
    return doi, python_file_content, usage, attempts, elapsed


def _extract_and_format_worker_agentic_cli(
    doi: str, config: AgenticCliConfig, run_root: Path
) -> tuple[str, str, CliUsage, int, float]:
    return _extract_and_format_single_doi_agentic_cli(doi, config, run_root)


def _execute_python_file_content(content: str) -> list[Experiment]:
    """Execute a generated Python file's content and extract the `extracted_experiments` variable."""
    namespace: dict[str, object] = {}
    exec(compile(content, "<generated>", "exec"), namespace)
    result = namespace.get("extracted_experiments")
    if not isinstance(result, list):
        raise ValueError("Generated file must define 'extracted_experiments' as a list")
    return result


def extract_and_format_materials_zero_shot_agentic_cli(
    selected_materials: dict[str, list[Material]],
    config: AgenticCliConfig,
    config_name: str,
) -> tuple[dict[str, ExtractionOutput], Path]:
    """Run agentic CLI extraction for all DOIs.

    Returns a tuple of (extraction_outputs, run_root) so callers can save
    eval metrics into the run directory.
    """
    run_root = _create_run_root(config_name, config.cli.name)
    config.save(run_root)
    extraction_outputs: dict[str, ExtractionOutput] = {}
    with ProcessPoolExecutor(max_workers=config.max_workers) as executor:
        futures = {
            executor.submit(_extract_and_format_worker_agentic_cli, doi, config, run_root): doi
            for doi in selected_materials
        }
        for future in as_completed(futures):
            doi = futures[future]
            try:
                doi, python_content, usage, attempts, paper_elapsed = future.result()
                extraction_outputs[doi] = ExtractionOutput(
                    experiments=_execute_python_file_content(python_content),
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cost_usd=usage.cost_usd,
                    attempts=attempts,
                    elapsed_seconds=paper_elapsed,
                )
            except Exception as exc:
                print(f"  [ERROR] DOI {doi} failed: {exc}")
    return extraction_outputs, run_root


def run_benchmark(
    benchmark: BenchmarkConfig,
    selected_materials: dict[str, list[Material]],
    ground_truth: dict[str, list[Experiment]],
    dois: list[str],
) -> Path | None:
    """Run all CLI configs in parallel, evaluate each, and save results."""
    all_extraction_outputs: dict[str, dict[str, ExtractionOutput]] = {}
    model_elapsed: dict[str, float] = {}
    run_roots: dict[str, Path] = {}

    def _run_single(cli_config: AgenticCliConfig) -> tuple[str, dict[str, ExtractionOutput], float, Path]:
        start = time.monotonic()
        extraction_outputs, run_root = extract_and_format_materials_zero_shot_agentic_cli(
            selected_materials=selected_materials,
            config=cli_config,
            config_name=benchmark.name,
        )
        elapsed = time.monotonic() - start
        print(f"  [{cli_config.cli.value}] extraction complete ({elapsed:.1f}s)")
        return cli_config.cli.value, extraction_outputs, elapsed, run_root

    with ThreadPoolExecutor(max_workers=len(benchmark.cli_configs)) as executor:
        futures = {executor.submit(_run_single, cfg): cfg for cfg in benchmark.cli_configs}
        for future in as_completed(futures):
            cfg = futures[future]
            try:
                cli_name, outputs, elapsed, run_root = future.result()
                all_extraction_outputs[cli_name] = outputs
                model_elapsed[cli_name] = elapsed
                run_roots[cli_name] = run_root
            except Exception as exc:
                print(f"  [ERROR] {cfg.cli.value} failed: {exc}")

    if not run_roots:
        return None

    cli_names = [cfg.cli.value for cfg in benchmark.cli_configs if cfg.cli.value in all_extraction_outputs]
    outputs_root = next(iter(run_roots.values())).parent

    evaluate_all_and_summarize(
        model_names=cli_names,
        dois=dois,
        ground_truth=ground_truth,
        all_extraction_outputs=all_extraction_outputs,
        model_output_dirs=run_roots,
        model_elapsed=model_elapsed,
        results_csv_path=outputs_root / "results.csv",
    )

    return outputs_root


if __name__ == "__main__":
    # dois = list(papers.keys())
    dois = list(papers.keys())[:1]
    selected_papers = {doi: papers[doi] for doi in dois}

    all_materials: dict[str, list[Material]] = {}
    for doi in selected_papers:
        all_materials[doi] = []
        for experiment in selected_papers[doi]:
            all_materials[doi].extend(experiment.output_materials)

    measurement_kinds_to_eval = None
    selected_materials = filter_materials_by_measurement_kinds(all_materials, measurement_kinds_to_eval)

    benchmark = BenchmarkConfig(
        name="default",
        cli_configs=[
            # AgenticCliConfig(cli=AgenticCli.claude_code),
            # AgenticCliConfig(cli=AgenticCli.codex),
            AgenticCliConfig(cli=AgenticCli.gemini_cli),
        ],
    )

    run_benchmark(
        benchmark=benchmark,
        selected_materials=selected_materials,
        ground_truth=selected_papers,
        dois=dois,
    )
