"""Create run_meta.json files for KnowMat2 std runs.

For each std_1, std_2, std_3:
- Read cost_summary.json for totals
- List doi_* subdirs with extraction files
- Distribute cost/tokens evenly across DOIs
- Write run_meta.json into the std dir
"""

import json
from pathlib import Path

KNOWMAT2_DIR = Path("/Users/cchong/Documents/dev/KnowMat2")

STD_RUNS = ["std_1", "std_2", "std_3"]


def main():
    for run_name in STD_RUNS:
        run_dir = KNOWMAT2_DIR / run_name
        cost_file = run_dir / "cost_summary.json"

        # Read cost summary
        with open(cost_file) as f:
            cost_summary = json.load(f)

        total_cost = cost_summary["total_cost_usd"]
        total_prompt = cost_summary["total_prompt_tokens"]
        total_completion = cost_summary["total_completion_tokens"]

        # Find doi dirs that have extraction files
        doi_dirs = sorted(
            d
            for d in run_dir.iterdir()
            if d.is_dir() and d.name.startswith("doi_") and any(d.glob("*extraction*"))
        )

        num_dois = len(doi_dirs)
        print(f"{run_name}: {num_dois} DOIs with extractions, total_cost=${total_cost:.4f}")

        # Distribute evenly
        cost_per_doi = round(total_cost / num_dois, 4)
        prompt_per_doi = total_prompt // num_dois
        completion_per_doi = total_completion // num_dois

        # Build run_meta
        run_meta = {}
        for doi_dir in doi_dirs:
            doi_name = doi_dir.name
            run_meta[doi_name] = {
                "input_tokens": prompt_per_doi,
                "output_tokens": completion_per_doi,
                "cost_usd": cost_per_doi,
                "attempts": 1,
            }

        # Write run_meta.json
        out_path = run_dir / "run_meta.json"
        with open(out_path, "w") as f:
            json.dump(run_meta, f, indent=2)
        print(f"  Wrote {out_path} ({len(run_meta)} entries)")


if __name__ == "__main__":
    main()
