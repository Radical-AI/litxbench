"""Statistics on the LitXAlloy dataset."""

from collections import defaultdict

from litxbench.core.models import CompMeasurement, Measurement
from litxbench.litxalloy import papers


def get_compositions(material):
    """Get all composition strings from a material."""
    comps = []
    for m in material.measurements:
        if isinstance(m, CompMeasurement):
            comps.append(m.composition.reduced_formula)
    return comps


def get_process_string(material):
    """Reconstruct process string from process_steps."""
    if material.process_steps is None:
        return "<no process>"
    parts = []
    for i, step in enumerate(material.process_steps):
        if i == 0 and step.inputs:
            parts.append(",".join(step.inputs))
        parts.append(step.to_string())
    return "->".join(parts)


def main():
    total_papers = len(papers)
    total_materials = 0
    total_experiments = 0

    # --- Stat 1: Papers with duplicate compositions (same comp, different processing) ---
    papers_with_dup_comps = {}

    # --- Stat 2: Papers with derived materials (materials built on other named materials) ---
    papers_with_derived = {}

    # --- Stat 3: Measurements with groups (e.g. ranges of values) ---
    total_measurements = 0
    total_grouped_measurements = 0
    total_groups = 0
    papers_with_grouped: dict[str, list[tuple[str, str, int]]] = {}  # doi -> [(material_label, group_name, group_size)]

    for doi, experiments in papers.items():
        total_experiments += len(experiments)

        for exp_idx, exp in enumerate(experiments):
            # Collect all material names defined in this experiment
            material_names = {m.name for m in exp.output_materials if m.name is not None}
            # raw_material_names = set(exp.raw_materials.keys())

            # Track compositions -> list of (material_name_or_idx, process_string)
            comp_to_materials: dict[str, list[tuple[str, str]]] = defaultdict(list)
            derived_materials = []

            for s_idx, material in enumerate(exp.output_materials):
                total_materials += 1
                label = material.name or f"material_{s_idx}"
                process_str = get_process_string(material)

                # Check compositions
                for comp in get_compositions(material):
                    comp_to_materials[comp].append((label, process_str))

                # Check for grouped measurements (ranges, etc.)
                material_groups: dict[str, list] = defaultdict(list)
                for m in material.measurements:
                    if isinstance(m, Measurement):
                        total_measurements += 1
                        if m.group_id is not None:
                            total_grouped_measurements += 1
                            material_groups[str(m.group_id)].append(m)
                for gid, members in material_groups.items():
                    total_groups += 1
                    group_kind = members[0].kind
                    stats = ", ".join(
                        f"{m.measurement_statistic.value}={m.value}" for m in members if m.measurement_statistic
                    )
                    group_desc = f"{group_kind} ({stats})"
                    if doi not in papers_with_grouped:
                        papers_with_grouped[doi] = []
                    papers_with_grouped[doi].append((label, group_desc, len(members)))

                # Check if this material derives from another named material
                if material.process_steps:
                    first_step = material.process_steps[0]
                    for inp in first_step.inputs:
                        if inp in material_names and inp != material.name:
                            derived_materials.append((label, inp, process_str))

            # Check for duplicate compositions with different processing
            for comp, material_list in comp_to_materials.items():
                if len(material_list) > 1:
                    # Check that at least 2 have different process strings
                    unique_processes = {p for _, p in material_list}
                    if len(unique_processes) > 1:
                        if doi not in papers_with_dup_comps:
                            papers_with_dup_comps[doi] = []
                        papers_with_dup_comps[doi].append(
                            (comp, len(material_list), len(unique_processes), material_list)
                        )

            if derived_materials:
                if doi not in papers_with_derived:
                    papers_with_derived[doi] = []
                papers_with_derived[doi].extend(derived_materials)

    # --- Print results ---
    print("=" * 70)
    print("LitXAlloy Dataset Statistics")
    print("=" * 70)
    print(f"Total papers: {total_papers}")
    print(f"Total experiments: {total_experiments}")
    print(f"Total materials: {total_materials}")
    print()

    # Stat 1
    print("-" * 70)
    print("DUPLICATE COMPOSITIONS (same composition, different processing)")
    print("-" * 70)
    print(f"Papers with duplicate compositions: {len(papers_with_dup_comps)} / {total_papers}")
    print()
    for doi, dup_list in papers_with_dup_comps.items():
        print(f"  {doi}:")
        for comp, n_materials, n_processes, material_list in dup_list:
            print(f"    Composition: {comp}")
            print(f"      {n_materials} materials, {n_processes} unique processes")
            for label, proc in material_list:
                print(f"        - {label}: {proc}")
        print()

    # Stat 2
    print("-" * 70)
    print("DERIVED MATERIALS (materials built from other named materials)")
    print("-" * 70)
    print(f"Papers with derived materials: {len(papers_with_derived)} / {total_papers}")
    print()
    for doi, derived_list in papers_with_derived.items():
        print(f"  {doi}:")
        for label, base, process_str in derived_list:
            print(f"    {label} <- derived from '{base}'")
            print(f"      process: {process_str}")
        print()

    # Stat 3
    print("-" * 70)
    print("GROUPED MEASUREMENTS (ranges of values)")
    print("-" * 70)
    print(f"Total measurements (non-comp, non-lattice): {total_measurements}")
    print(f"Measurements in groups: {total_grouped_measurements}")
    print(f"Total groups: {total_groups}")
    print(f"Papers with grouped measurements: {len(papers_with_grouped)} / {total_papers}")
    print()
    for doi, group_list in papers_with_grouped.items():
        print(f"  {doi}:")
        for label, group_desc, group_size in group_list:
            print(f"    {label}: {group_desc} ({group_size} values)")
        print()

    # --- Summary table ---
    print("=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)

    # Build per-paper row data
    rows = []
    for doi, experiments in papers.items():
        n_materials = sum(len(exp.output_materials) for exp in experiments)
        n_unique_comps = len(
            {comp for exp in experiments for material in exp.output_materials for comp in get_compositions(material)}
        )
        has_dup = doi in papers_with_dup_comps
        n_dup_comps = len(papers_with_dup_comps.get(doi, []))
        has_derived = doi in papers_with_derived
        n_derived = len(papers_with_derived.get(doi, []))
        rows.append((doi, n_materials, n_unique_comps, has_dup, n_dup_comps, has_derived, n_derived))

    # Column headers
    headers = ["DOI", "Materials", "Unique Comps", "Dup Comps?", "# Dup Groups", "Derived?", "# Derived"]
    # Compute column widths
    col_widths = [len(h) for h in headers]
    str_rows = []
    for doi, n_s, n_uc, hd, ndc, hdr, ndr in rows:
        r = [
            doi,
            str(n_s),
            str(n_uc),
            "Yes" if hd else "",
            str(ndc) if ndc else "",
            "Yes" if hdr else "",
            str(ndr) if ndr else "",
        ]
        str_rows.append(r)
        for i, cell in enumerate(r):
            col_widths[i] = max(col_widths[i], len(cell))

    def fmt_row(cells):
        return " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(cells))

    header_line = fmt_row(headers)
    sep_line = "-+-".join("-" * w for w in col_widths)
    print(header_line)
    print(sep_line)
    for r in str_rows:
        print(fmt_row(r))
    print(sep_line)

    # Totals row
    total_s = sum(r[1] for r in rows)
    total_uc = sum(r[2] for r in rows)
    total_dup_papers = sum(1 for r in rows if r[3])
    total_dup_groups = sum(r[4] for r in rows)
    total_derived_papers = sum(1 for r in rows if r[5])
    total_derived_materials = sum(r[6] for r in rows)
    totals = [
        f"TOTAL ({total_papers} papers)",
        str(total_s),
        str(total_uc),
        f"{total_dup_papers} papers",
        str(total_dup_groups),
        f"{total_derived_papers} papers",
        str(total_derived_materials),
    ]
    print(fmt_row(totals))
    print()


if __name__ == "__main__":
    main()
