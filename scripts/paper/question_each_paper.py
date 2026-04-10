"""Run a custom question across all transcribed papers."""

import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import logfire
from pydantic_ai import Agent, BinaryContent

from litxbench.core.utils import resolve_path
from litxbench.litxalloy import papers
from scripts.paper.benchmarks.helpers.model_provider import ModelProvider
from scripts.paper.benchmarks.helpers.paper_loading import load_transcribed_paper

_ = logfire.configure(service_name="cchong/paperscraper", console=logfire.ConsoleOptions(min_log_level="notice"))
logfire.instrument_pydantic_ai()


def get_all_dois() -> list[str]:
    """Get all DOIs from the dataset in declared order."""
    return list(papers.keys())


@dataclass(frozen=True)
class PaperQuestionResult:
    index: int
    doi: str
    answer: str


@dataclass(frozen=True)
class PromptInputs:
    question: str
    include_manual_extraction_code: bool


def build_agent() -> Agent:
    model_provider = ModelProvider()
    return Agent(model=model_provider.GPT52Model(reasoning_effort="medium"), output_type=str)


def get_manual_extraction_code_for_doi(doi: str) -> str:
    extraction_file = Path(resolve_path(f"src/litxbench/litxalloy/extractions/{doi}.py"))
    return extraction_file.read_text()


def build_question_prompt(doi: str, prompt_inputs: PromptInputs) -> str:
    if not prompt_inputs.include_manual_extraction_code:
        return prompt_inputs.question

    extraction_code = get_manual_extraction_code_for_doi(doi)
    if extraction_code == "":
        return prompt_inputs.question

    return textwrap.dedent(
        f"""
        {prompt_inputs.question}

        Below is the raw manually extracted code for this same DOI from `litxalloy.py`.
        Use it as additional context when answering, and call out likely missing extracted values if you see them.

        ```python
        {extraction_code}
        ```
        """
    ).strip()


def ask_question_for_paper(doi: str, prompt_inputs: PromptInputs, agent: Agent) -> str:
    """Ask a custom question for a single paper."""
    prompt: list[str | BinaryContent] = []
    prompt.extend(load_transcribed_paper(doi))
    prompt.append(build_question_prompt(doi, prompt_inputs))
    res = agent.run_sync(prompt)
    return res.output


def normalize_output_title(title: str) -> str:
    normalized_title = title.strip().replace(" ", "_")
    return normalized_title or "paper_question_results"


def write_results(output_dir: Path, title: str, question: str, results: list[PaperQuestionResult]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{normalize_output_title(title)}.txt"
    with output_path.open("w") as handle:
        _ = handle.write("=" * 80 + "\n")
        _ = handle.write(f"QUESTION: {question}\n")
        _ = handle.write("=" * 80 + "\n")
        for result in results:
            _ = handle.write(f"\nDOI: {result.doi}\n")
            _ = handle.write("-" * 40 + "\n")
            _ = handle.write(result.answer + "\n")
    return output_path


def process_paper(index: int, doi: str, prompt_inputs: PromptInputs) -> PaperQuestionResult:
    agent = build_agent()
    answer = ask_question_for_paper(doi, prompt_inputs, agent)
    return PaperQuestionResult(index=index, doi=doi, answer=answer)


def run_parallel_questions(dois: list[str], prompt_inputs: PromptInputs, max_workers: int) -> list[PaperQuestionResult]:
    ordered_results: list[PaperQuestionResult | None] = [None] * len(dois)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_paper, index, doi, prompt_inputs) for index, doi in enumerate(dois)]
        for future in as_completed(futures):
            result = future.result()
            print(f"Done: {result.doi}")
            ordered_results[result.index] = result

    return [result for result in ordered_results if result is not None]


def main(question: str, title: str, max_workers: int = 21, include_manual_extraction_code: bool = False) -> None:
    """Run one question across all papers and save responses."""
    dois = get_all_dois()
    print(f"Found {len(dois)} papers to process\n")
    print(f"Using {max_workers} workers\n")
    print(f"Include manual extraction code: {include_manual_extraction_code}\n")

    for doi in dois:
        print(f"Queued: {doi}")
    print()

    prompt_inputs = PromptInputs(question=question, include_manual_extraction_code=include_manual_extraction_code)
    results = run_parallel_questions(dois, prompt_inputs, max_workers=max_workers)

    output_dir = Path(resolve_path("outputs/question_each_paper"))
    output_file = write_results(output_dir, title, question, results)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    # main(
    #     title="processing_results",
    #     question=textwrap.dedent("""
    #     Based on the paper above, describe how the authors processed/synthesized the materials they made.

    #     Please include details about:
    #     - The synthesis/fabrication method (e.g., arc melting, casting, powder metallurgy, additive manufacturing)
    #     - Heat treatment conditions (temperatures, times, cooling methods)
    #     - Any mechanical processing (rolling, forging, etc.)
    #     - Atmosphere/environment used during processing
    #     - Any other relevant processing parameters

    #     Be concise but comprehensive. Focus only on what the authors actually did in their experimental work.
    #     """).strip(),
    # )

    # main(
    #     title="composition_measurement_kinds",
    #     question=textwrap.dedent("""
    #     Based on the paper above, describe the methods the authors used to measure composition.
    #     What are the compositions they measured for each sample? What machine did they use to measure that composition?

    #     Only focus on the compositions of the samples the authors actually made in their lab (not compositions made by other papers).

    #     Be very explicit and clear when giving your final answer.

    #     For each composition they measured (for a sample they made), tell me which one of these machines did they use.
    #     Balance = "balance"
    #     EDS = "energy_dispersive_xray_spectroscopy"
    #     LIBS = "laser_induced_breakdown_spectroscopy"
    #     ED_XRF = "energy_dispersive_xray_fluorescence"
    #     WD_XRF = "wavelength_dispersive_xray_fluorescence"
    #     Spark_OES = "spark_optical_emission_spectroscopy"
    #     ICP_OES = "inductively_coupled_plasma_optical_emission_spectroscopy"
    #     ICP_MS = "inductively_coupled_plasma_mass_spectroscopy"
    #     """).strip(),
    #     include_manual_extraction_code=False,
    # )

    # main(
    #     title="hardness_tests",
    #     question=textwrap.dedent("""
    #     Based on the paper above, describe the methods the authors used to test the hardness of the materials they made.
    #     What are the hardness values they measured for each sample? What machine did they use to test that hardness?
    #     What kind of hardness did they measure? (e.g. Vickers hardness, Rockwell hardness, Brinell hardness, etc.)

    #     Only focus on the hardness values of the samples the authors actually made in their lab (not hardness values made by other papers).
    #     """).strip(),
    # )

    # main(
    #     title="approximate_values",
    #     question=textwrap.dedent("""
    #     Based on the paper above, we have extracted experiments. For each numeric measurement we've extracted,
    #     in the paper, did they say it was an approximate value or an exact value or a value within a range? (e.g. "about 50HV", "~50HV", "below 50HV", ">50HV", etc.)

    #     for the measurements we've extractd, let us know if there are measurements we've specified as exact, but in reality, it should be
    #     more approximate (e.g. instead of value=50.0, it should be value="~50")
    #     """).strip(),
    #     include_manual_extraction_code=True,
    # )

    # main(
    #     title="touchup",
    #     question=textwrap.dedent("""
    #     Based on the paper above, we have extracted experiments. Are there any corrections to the extracted experiments?

    #     For each correction, please be very specific and include a code example of how we can correct the extracted experiments.

    #     We only care about information from text, not visible in figures.
    #     """).strip(),
    #     include_manual_extraction_code=True,
    # )

    main(
        title="machines",
        question=textwrap.dedent("""
        Based on the paper above, what machines did they mention used in their experiments. For which properties were they used for?

        Please list all machines used.

        """).strip(),
        include_manual_extraction_code=False,
    )
