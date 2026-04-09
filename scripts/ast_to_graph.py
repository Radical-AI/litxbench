"""Build a JSON process graph from the LitXAlloy dataset, annotated with source code.

Walks the AST of each per-DOI extraction file in lockstep with the structural graph
produced by papers_to_graph() to attach raw source code snippets to each node and edge.

Usage:
    uv run python scripts/ast_to_graph.py
"""

from __future__ import annotations

import ast
import json
from collections.abc import Sequence
from enum import Enum
from pathlib import Path

from litxbench.core.models import CompMeasurement, DescriptionGroup, ProcessEvent, ProcessStep
from litxbench.core.utils import resolve_path
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import (
    Configuration,
    Experiment,
    GlobalLatticeParam,
    LatticeMeasurement,
    Material,
    Measurement,
)

EXTRACTIONS_DIR = Path(resolve_path("src/litxbench/litxalloy/extractions"))
OUTPUT_FILE = Path(resolve_path("ui/public/data/litxalloy_graph.json"))


def find_experiments_assignment(tree: ast.Module) -> ast.List:
    """Find the `experiments: list[...] = [...]` list node in a per-DOI module AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "experiments":
            assert isinstance(node.value, ast.List), f"Expected list, got {type(node.value)}"
            return node.value
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "experiments":
                    assert isinstance(node.value, ast.List), f"Expected list, got {type(node.value)}"
                    return node.value
    raise ValueError("Could not find 'experiments' assignment in AST")


def get_keyword_value(call: ast.Call, keyword_name: str) -> ast.expr | None:
    """Get the value of a keyword argument from an ast.Call node."""
    for kw in call.keywords:
        if kw.arg == keyword_name:
            return kw.value
    return None


def get_keyword_node(call: ast.Call, keyword_name: str) -> ast.keyword | None:
    """Get the full keyword node from an ast.Call node."""
    for kw in call.keywords:
        if kw.arg == keyword_name:
            return kw
    return None


def source_segment(source: str, node: ast.AST) -> str | None:
    """Extract source code for an AST node."""
    return ast.get_source_segment(source, node)


def build_synth_group_map(synth_ast: ast.expr) -> dict[str, ast.expr]:
    """Build a mapping from synthesis group base_name to its AST value node.

    For dict-style synthesis_groups: keys are group names like "annealing[Temp]",
    we parse them to get base_names. Values are lists of ProcessEvent calls.

    For list-style: returns a single entry under "default".
    """
    result: dict[str, ast.expr] = {}
    if isinstance(synth_ast, ast.Dict):
        for key_node, value_node in zip(synth_ast.keys, synth_ast.values):
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                parsed = ProcessStep.parse_event_name(key_node.value)
                result[parsed.base_name] = value_node
    elif isinstance(synth_ast, ast.List):
        result["default"] = synth_ast
    return result


def get_edge_source(source: str, synth_map: dict[str, ast.expr], process_steps: list[dict]) -> str | None:
    """Get source code for an edge by finding synthesis groups matching its process steps."""
    segments = []
    for step in process_steps:
        base_name = step["base_name"]
        if base_name in synth_map:
            seg = source_segment(source, synth_map[base_name])
            if seg:
                segments.append(seg)
        elif "default" in synth_map:
            # List-style: all steps use the default synthesis groups
            seg = source_segment(source, synth_map["default"])
            if seg and seg not in segments:
                segments.append(seg)
    return "\n".join(segments) if segments else None


def get_edge_lines(synth_map: dict[str, ast.expr], process_steps: list[dict]) -> tuple[int | None, int | None]:
    """Get start/end lines for an edge's synthesis group source."""
    start_line = None
    end_line = None
    for step in process_steps:
        base_name = step["base_name"]
        target = synth_map.get(base_name) or synth_map.get("default")
        if target:
            if start_line is None or target.lineno < start_line:
                start_line = target.lineno
            if end_line is None or (target.end_lineno and target.end_lineno > end_line):
                end_line = target.end_lineno
    return start_line, end_line


def annotate_experiments(
    exp_graphs: list[dict],
    source: str,
    exp_list_ast: ast.List,
    doi: str,
) -> None:
    """Annotate experiment graphs for a single DOI with source code from its AST."""
    for exp_idx, exp_call_ast in enumerate(exp_list_ast.elts):
        if not isinstance(exp_call_ast, ast.Call):
            continue
        if exp_idx >= len(exp_graphs):
            break
        exp_graph = exp_graphs[exp_idx]
        node_map = {n["id"]: n for n in exp_graph["nodes"]}

        # --- Annotate material nodes ---
        materials_ast = get_keyword_value(exp_call_ast, "output_materials")
        if isinstance(materials_ast, ast.List):
            prefix = f"{doi}/exp:{exp_idx}"
            for material_idx, material_call_ast in enumerate(materials_ast.elts):
                node_id = f"{prefix}/material:{material_idx}"
                if node_id in node_map:
                    seg = source_segment(source, material_call_ast)
                    node_map[node_id]["source_code"] = seg
                    node_map[node_id]["start_line"] = material_call_ast.lineno
                    node_map[node_id]["end_line"] = material_call_ast.end_lineno

        # --- Annotate individual raw_materials nodes ---
        prefix = f"{doi}/exp:{exp_idx}"
        rm_kw = get_keyword_node(exp_call_ast, "raw_materials")
        if rm_kw and isinstance(rm_kw.value, ast.Dict):
            for key_node, value_node in zip(rm_kw.value.keys, rm_kw.value.values):
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    rm_node_id = f"{prefix}/raw:{key_node.value}"
                    if rm_node_id in node_map:
                        seg = source_segment(source, value_node)
                        node_map[rm_node_id]["source_code"] = seg
                        node_map[rm_node_id]["start_line"] = value_node.lineno
                        node_map[rm_node_id]["end_line"] = value_node.end_lineno

        # --- Annotate edges with synthesis group source ---
        synth_ast = get_keyword_value(exp_call_ast, "synthesis_groups")
        if synth_ast:
            synth_map = build_synth_group_map(synth_ast)

            for edge in exp_graph["edges"]:
                edge_source = get_edge_source(source, synth_map, edge["process_steps"])
                if edge_source:
                    edge["source_code"] = edge_source
                start_line, end_line = get_edge_lines(synth_map, edge["process_steps"])
                if start_line:
                    edge["start_line"] = start_line
                if end_line:
                    edge["end_line"] = end_line


def annotate_graph(graph: dict[str, list[dict]]) -> None:
    """Annotate all experiment graphs with source code from per-DOI extraction files."""
    for doi, exp_graphs in graph.items():
        source_file = EXTRACTIONS_DIR / f"{doi}.py"
        if not source_file.exists():
            print(f"  Warning: No extraction file for {doi}, skipping source annotation")
            continue

        source = source_file.read_text()
        tree = ast.parse(source)

        try:
            exp_list_ast = find_experiments_assignment(tree)
        except ValueError:
            print(f"  Warning: Could not find experiments in {source_file.name}, skipping")
            continue

        annotate_experiments(exp_graphs, source, exp_list_ast, doi)


# =============================================================================
# Graph Generation
# =============================================================================


def experiment_to_graph(experiment: Experiment, paper_doi: str, exp_idx: int) -> dict[str, list[dict[str, object]]]:
    """Convert an experiment to a graph representation.

    Each raw material gets its own node. Edges are created from:
    1. The process string's primary inputs (e.g., "Q235 steel substrate->prepare_steel")
    2. ProcessEvent.inputs within synthesis groups (e.g., Mixing(inputs=["elements", "wc_additions"]))

    Args:
        experiment: The experiment to convert
        paper_doi: DOI of the paper containing this experiment
        exp_idx: Index of this experiment within the paper

    Returns:
        Dictionary with 'nodes' and 'edges' lists representing the experiment graph
    """
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    prefix = f"{paper_doi}/exp:{exp_idx}"

    named_materials: dict[str, str] = {}
    for i, material in enumerate(experiment.output_materials):
        material_id = f"{prefix}/material:{i}"
        if material.name:
            named_materials[material.name] = material_id

    referenced_raw_materials: set[str] = set()

    def resolve_input(name: str) -> str:
        """Resolve an input name to a graph node ID."""
        if name in named_materials:
            return named_materials[name]
        elif name in experiment.raw_materials:
            referenced_raw_materials.add(name)
            return f"{prefix}/raw:{name}"
        else:
            return f"{prefix}/ref:{name}"

    for i, material in enumerate(experiment.output_materials):
        material_id = f"{prefix}/material:{i}"
        nodes.append(
            {
                "id": material_id,
                "type": "material",
                "label": _get_material_label(material),
                "name": material.name,
                "measurements": _serialize_measurements(material.measurements),
            }
        )

        if material.process_steps:
            first_step = material.process_steps[0]
            connected_inputs: set[str] = set()

            # Create edges from primary inputs (from process string)
            process_label = " -> ".join(step.to_string() for step in material.process_steps)
            for input_name in first_step.inputs:
                source_id = resolve_input(input_name)
                connected_inputs.add(input_name)
                edges.append(
                    {
                        "source": source_id,
                        "target": material_id,
                        "label": process_label,
                        "process_steps": [
                            {
                                "base_name": step.base_name,
                                "variables": dict(step.variables),
                                "events": _get_process_events_for_step(experiment, step),
                            }
                            for step in material.process_steps
                        ],
                    }
                )

            # Create edges from additional inputs referenced by ProcessEvents in synthesis groups
            for step in material.process_steps:
                if step.base_name in experiment.synthesis_group_map:
                    group = experiment.synthesis_group_map[step.base_name]
                    if step.variables and any(v != "" for v in step.variables.values()):
                        resolved_events = group.substitute_variables(step.variables)
                    else:
                        resolved_events = group.process_events
                    for event in resolved_events:
                        for input_name in event.inputs:
                            if input_name in connected_inputs:
                                continue
                            connected_inputs.add(input_name)
                            source_id = resolve_input(input_name)
                            edges.append(
                                {
                                    "source": source_id,
                                    "target": material_id,
                                    "label": step.base_name,
                                    "process_steps": [
                                        {
                                            "base_name": step.base_name,
                                            "variables": dict(step.variables),
                                            "events": _get_process_events_for_step(experiment, step),
                                        }
                                    ],
                                }
                            )

    # Create individual raw material nodes
    for rm_name in referenced_raw_materials:
        raw = experiment.raw_materials[rm_name]
        nodes.insert(
            0,
            {
                "id": f"{prefix}/raw:{rm_name}",
                "type": "raw_material",
                "label": rm_name,
                "name": rm_name,
                "materials": {rm_name: {"kind": str(raw.kind), "description": raw.description}},
            },
        )

    descriptions = [_serialize_description_group(d) for d in experiment.descriptions]

    return {"nodes": nodes, "edges": edges, "descriptions": descriptions}


def papers_to_graph(papers_dict: dict[str, list[Experiment]]) -> dict[str, list[dict[str, list[dict[str, object]]]]]:
    """Convert all papers to per-experiment graphs, keyed by DOI."""
    result: dict[str, list[dict[str, list[dict[str, object]]]]] = {}
    for doi, experiments in papers_dict.items():
        result[doi] = [experiment_to_graph(exp, doi, i) for i, exp in enumerate(experiments)]
    return result


def _serialize_description_group(group: DescriptionGroup) -> dict[str, object]:
    """Serialize a DescriptionGroup to a JSON-compatible dictionary."""
    kinds: list[str] = []
    for k in group.kinds:
        if isinstance(k, Enum):
            kinds.append(k.value)
        elif isinstance(k, type):
            kinds.append(k.__name__)
        else:
            kinds.append(str(k))
    result: dict[str, object] = {"kinds": kinds}
    if group.method is not None:
        result["method"] = group.method.value if isinstance(group.method, Enum) else str(group.method)
    if group.group_name is not None:
        result["group_name"] = group.group_name
    if group.desc is not None:
        result["desc"] = group.desc
    if group.source is not None:
        result["source"] = group.source
    return result


def _serialize_process_event(event: ProcessEvent) -> dict[str, object]:
    """Serialize a ProcessEvent to a JSON-compatible dictionary."""
    result: dict[str, object] = {
        "kind": event.kind.value if isinstance(event.kind, Enum) else str(event.kind),
    }
    if event.description is not None:
        result["description"] = event.description
    if event.temperature is not None:
        result["temperature"] = f"{event.temperature.value} {event.temperature.unit}"
    if event.duration is not None:
        result["duration"] = f"{event.duration.value} {event.duration.unit}"
    if event.equipment is not None:
        result["equipment"] = event.equipment
    if event.source is not None:
        result["source"] = event.source
    if event.inputs:
        result["inputs"] = event.inputs
    return result


def _get_process_events_for_step(
    experiment: Experiment,
    step: ProcessStep,
) -> list[dict[str, object]]:
    """Get serialized process events for a process step, with variable substitution."""
    if step.base_name not in experiment.synthesis_group_map:
        return []
    group = experiment.synthesis_group_map[step.base_name]
    if step.variables and any(v != "" for v in step.variables.values()):
        events = group.substitute_variables(step.variables)
    else:
        events = group.process_events
    return [_serialize_process_event(e) for e in events]


def _get_material_label(material: Material) -> str:
    """Extract a display label for a material (typically its composition formula)."""
    for measurement in material.measurements:
        if isinstance(measurement, CompMeasurement):
            return _format_composition_label(measurement.composition)
    return "unknown"


def _format_composition_label(comp: object) -> str:
    """Format a composition with amounts truncated to 3 significant figures for display."""
    parts = []
    for el, amt in comp.as_dict().items():
        if amt == int(amt):
            parts.append(f"{el}{int(amt)}")
        else:
            parts.append(f"{el}{amt:.3g}")
    return " ".join(parts)


def _serialize_measurement(measurement: object) -> dict[str, object]:
    """Serialize a measurement object to a JSON-compatible dictionary."""
    if isinstance(measurement, CompMeasurement):
        result: dict[str, object] = {
            "type": "composition",
            "formula": measurement.composition.formula,
        }
        if measurement.method is not None:
            result["method"] = (
                measurement.method.value if isinstance(measurement.method, Enum) else str(measurement.method)
            )
        if measurement.description is not None:
            result["description"] = measurement.description
        if measurement.source is not None:
            result["source"] = measurement.source
        return result
    if isinstance(measurement, Measurement):
        result: dict[str, object] = {
            "type": "measurement",
            "kind": (measurement.kind.value if isinstance(measurement.kind, Enum) else str(measurement.kind)),
            "value": measurement.value,
            "unit": str(measurement.unit),
        }
        if measurement.uncertainty is not None:
            result["uncertainty"] = measurement.uncertainty
        if measurement.measurement_method is not None:
            result["measurement_method"] = (
                measurement.measurement_method.value
                if isinstance(measurement.measurement_method, Enum)
                else str(measurement.measurement_method)
            )
        if measurement.measurement_statistic is not None:
            result["measurement_statistic"] = measurement.measurement_statistic.value
        if measurement.description is not None:
            result["description"] = measurement.description
        if measurement.source is not None:
            result["source"] = measurement.source
        if measurement.temperature is not None:
            result["temperature"] = f"{measurement.temperature.value} {measurement.temperature.unit}"
        if measurement.pressure is not None:
            result["pressure"] = f"{measurement.pressure.value} {measurement.pressure.unit}"
        return result
    if isinstance(measurement, Configuration):
        result: dict[str, object] = {"type": "phase"}
        if measurement.name:
            result["name"] = measurement.name
        if measurement.struct:
            result["struct"] = (
                measurement.struct.value if isinstance(measurement.struct, Enum) else str(measurement.struct)
            )
        if measurement.tags:
            result["tags"] = [tag.value if isinstance(tag, Enum) else str(tag) for tag in measurement.tags]
        if measurement.within:
            result["within"] = measurement.within
        if measurement.description:
            result["description"] = measurement.description
        if measurement.source:
            result["source"] = measurement.source
        if measurement.measurements:
            result["measurements"] = [
                _serialize_measurement(phase_measurement) for phase_measurement in measurement.measurements
            ]
        return result
    if isinstance(measurement, GlobalLatticeParam):
        result: dict[str, object] = {"type": "global_lattice_param"}
        if measurement.struct:
            result["struct"] = (
                measurement.struct.value if isinstance(measurement.struct, Enum) else str(measurement.struct)
            )
        if measurement.name:
            result["name"] = measurement.name
        if measurement.lattice:
            result["lattice_description"] = measurement.lattice.description
        if measurement.phase_fraction:
            result["phase_fraction"] = f"{measurement.phase_fraction.value} {measurement.phase_fraction.unit}"
        if measurement.description:
            result["description"] = measurement.description
        if measurement.source:
            result["source"] = measurement.source
        return result
    if isinstance(measurement, LatticeMeasurement):
        result: dict[str, object] = {"type": "lattice"}
        if measurement.lattice:
            result["a"] = measurement.lattice.a
            result["b"] = measurement.lattice.b
            result["c"] = measurement.lattice.c
        if measurement.description:
            result["description"] = measurement.description
        if measurement.source:
            result["source"] = measurement.source
        return result
    return {"type": type(measurement).__name__, "repr": repr(measurement)}


def _serialize_measurements(measurements: Sequence[object]) -> list[dict[str, object]]:
    """Serialize a sequence of measurement objects."""
    return [_serialize_measurement(measurement) for measurement in measurements]


# =============================================================================
# AST Annotation
# =============================================================================


def main():
    # Build the structural graph
    graph = papers_to_graph(papers)

    # Annotate with source code from per-DOI extraction files
    annotate_graph(graph)

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(graph, f, indent=2, default=str)

    # Print summary
    total_nodes = sum(len(eg["nodes"]) for exps in graph.values() for eg in exps)
    total_edges = sum(len(eg["edges"]) for exps in graph.values() for eg in exps)
    nodes_with_source = sum(1 for exps in graph.values() for eg in exps for n in eg["nodes"] if "source_code" in n)
    edges_with_source = sum(1 for exps in graph.values() for eg in exps for e in eg["edges"] if "source_code" in e)
    total_experiments = sum(len(exps) for exps in graph.values())
    print(f"Wrote {OUTPUT_FILE}")
    print(f"  Papers: {len(graph)}")
    print(f"  Experiments: {total_experiments}")
    print(f"  Nodes: {total_nodes}")
    print(f"  Edges: {total_edges}")
    print(f"  Nodes with source_code: {nodes_with_source}")
    print(f"  Edges with source_code: {edges_with_source}")


if __name__ == "__main__":
    main()
