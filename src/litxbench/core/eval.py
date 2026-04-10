from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import pint
from pymatgen.core.lattice import Lattice as PymatgenLattice
from scipy.optimize import linear_sum_assignment

from litxbench.core.enums import ConfigTag, MeasurementMethod, ProcessKind, ValueQualifier
from litxbench.core.extraction_utils import ROOM_TEMPERATURE
from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    Experiment,
    GlobalLatticeParam,
    LatticeMeasurement,
    Material,
    Measurement,
    ProcessEvent,
    Quantity,
    SynthesisGroup,
)
from litxbench.core.units import ureg


@dataclass
class MaterialWithContext:
    """A material paired with the synthesis context from its parent experiment."""

    material: Material
    synthesis_group_map: dict[str, SynthesisGroup]


@dataclass
class ComparableItem:
    """Wrapper that normalizes different measurement types for unified matching."""

    type: str
    """One of "measurement", "composition", "lattice", "struct", "phase_fraction"."""
    item: Any
    """The underlying object (Measurement, CompMeasurement, LatticeMeasurement, CrysStruct, or Quantity)."""
    context: str | None = None
    """Optional scope tag (e.g. Configuration name or GlobalLatticeParam name) so that items from different scopes are never matched together."""


@dataclass
class MeasurementMatchResult:
    """Result of matching comparable items between two materials."""

    matched_pairs: list[tuple[ComparableItem, ComparableItem, float]]
    unmatched_target: list[ComparableItem]
    unmatched_extracted: list[ComparableItem]

    @property
    def match_score(self) -> float:
        return sum(score for _, _, score in self.matched_pairs)

    @property
    def total(self) -> int:
        return max(
            len(self.matched_pairs) + len(self.unmatched_target),
            len(self.matched_pairs) + len(self.unmatched_extracted),
        )


@dataclass
class ConfigScoreBreakdown:
    """Per-attribute similarity scores for a configuration match."""

    tags: float
    struct: float
    name: float
    measurement: float
    within: float


@dataclass
class ConfigurationMatchResult:
    """Result of matching configurations between two materials via Hungarian assignment."""

    matched_pairs: list[tuple[Configuration, Configuration, float]]  # (target, extracted, score)
    unmatched_target: list[Configuration]
    unmatched_extracted: list[Configuration]
    nested_measurement_results: list[MeasurementMatchResult]  # parallel to matched_pairs
    breakdowns: list[ConfigScoreBreakdown]  # parallel to matched_pairs


@dataclass
class MaterialMatchResult:
    """Result of matching a target material to an extracted material."""

    target: Material
    extracted: Material
    cost: float
    process_edit_distance: int
    measurement_result: MeasurementMatchResult
    process_alignment: ProcessEventAlignmentResult | None = None
    config_match: ConfigurationMatchResult | None = None


@dataclass
class ExperimentComparisonResult:
    """Result of comparing two sets of experiments."""

    matched_materials: list[MaterialMatchResult]
    unmatched_target_materials: list[Material]
    unmatched_extracted_materials: list[Material]
    total_cost: float

    # --- Material-level counts (for context reporting) ---

    @property
    def num_target_materials(self) -> int:
        return len(self.matched_materials) + len(self.unmatched_target_materials)

    @property
    def num_extracted_materials(self) -> int:
        return len(self.matched_materials) + len(self.unmatched_extracted_materials)

    @property
    def num_matched_materials(self) -> int:
        return len(self.matched_materials)

    # --- Measurement-level (comparable-item) counts ---

    @property
    def num_matched_items(self) -> float:
        """TP: sum of match scores across matched material pairs (including config nested)."""
        total = sum(m.measurement_result.match_score for m in self.matched_materials)
        for m in self.matched_materials:
            if m.config_match is not None:
                for nested in m.config_match.nested_measurement_results:
                    total += nested.match_score
        return total

    @property
    def num_total_target_items(self) -> int:
        """TP + FN: all target comparable items (including config nested)."""
        matched_target = sum(
            len(m.measurement_result.matched_pairs) + len(m.measurement_result.unmatched_target)
            for m in self.matched_materials
        )
        # Config nested measurements from matched material pairs
        for m in self.matched_materials:
            if m.config_match is not None:
                for nested in m.config_match.nested_measurement_results:
                    matched_target += len(nested.matched_pairs) + len(nested.unmatched_target)
                for cfg in m.config_match.unmatched_target:
                    matched_target += len(_extract_config_comparable_items(cfg))
        unmatched = sum(_count_comparable_items(mat) for mat in self.unmatched_target_materials)
        return matched_target + unmatched

    @property
    def num_total_extracted_items(self) -> int:
        """TP + FP: all extracted comparable items (including config nested)."""
        matched_extracted = sum(
            len(m.measurement_result.matched_pairs) + len(m.measurement_result.unmatched_extracted)
            for m in self.matched_materials
        )
        # Config nested measurements from matched material pairs
        for m in self.matched_materials:
            if m.config_match is not None:
                for nested in m.config_match.nested_measurement_results:
                    matched_extracted += len(nested.matched_pairs) + len(nested.unmatched_extracted)
                for cfg in m.config_match.unmatched_extracted:
                    matched_extracted += len(_extract_config_comparable_items(cfg))
        unmatched = sum(_count_comparable_items(mat) for mat in self.unmatched_extracted_materials)
        return matched_extracted + unmatched

    # --- Measurement-level P / R / F1 ---

    @property
    def precision(self) -> float:
        tp = self.num_matched_items
        total_extracted = self.num_total_extracted_items
        return tp / total_extracted if total_extracted else 0.0

    @property
    def recall(self) -> float:
        tp = self.num_matched_items
        total_target = self.num_total_target_items
        return tp / total_target if total_target else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    # Backward-compat aliases used by reporting code
    @property
    def num_target(self) -> int:
        return self.num_target_materials

    @property
    def num_extracted(self) -> int:
        return self.num_extracted_materials


# ---------------------------------------------------------------------------
# Resolve a material's synthesis chain into a flat list of ProcessEvents
# ---------------------------------------------------------------------------


def resolve_process_events(
    material: Material,
    synthesis: dict[str, SynthesisGroup],
) -> list[ProcessEvent]:
    """Walk a material's process_steps and flatten all ProcessEvents in order.

    Each ProcessStep references a synthesis group by base_name and provides
    variable substitutions. We resolve each step and concatenate the resulting
    ProcessEvents.
    """
    if material.process_steps is None:
        return []

    all_events: list[ProcessEvent] = []
    for step in material.process_steps:
        synth_group = synthesis.get(step.base_name)
        if synth_group is None:
            continue
        if synth_group.template_vars and step.variables:
            resolved = synth_group.substitute_variables(step.variables)
        else:
            resolved = list(synth_group.process_events)

        # Auto-inject step.inputs into the first ProcessEvent's inputs
        if step.inputs and resolved:
            resolved[0] = replace(resolved[0], inputs=resolved[0].inputs + step.inputs)

        all_events.extend(resolved)
    return all_events


def normalize_process_events(events: list[ProcessEvent]) -> list[ProcessEvent]:
    """Prepend an implicit Mixing step (if not already present) and remove Cut events."""
    filtered = [e for e in events if e.kind != ProcessKind.Cut]
    if filtered and filtered[0].kind == ProcessKind.Mixing:
        return filtered
    return [ProcessEvent(kind=ProcessKind.Mixing)] + filtered


# ---------------------------------------------------------------------------
# Edit distance on ProcessEvent kind sequences
# ---------------------------------------------------------------------------


def normalize_kind(kind: object) -> str:
    """Normalize a ProcessEvent kind to a comparable string."""
    if hasattr(kind, "value"):
        return str(kind.value)
    return str(kind)


@dataclass
class ProcessEventAlignmentResult:
    """Result of aligning two process event sequences."""

    matched_pairs: list[tuple[ProcessEvent, ProcessEvent]]  # aligned same-kind
    unmatched_target: list[ProcessEvent]
    unmatched_extracted: list[ProcessEvent]
    edit_distance: int
    alignment: list[tuple[ProcessEvent | None, ProcessEvent | None]] = field(default_factory=list)


def _levenshtein_dp(
    kinds_a: list[str],
    kinds_b: list[str],
) -> list[list[int]]:
    """Build the Levenshtein DP table for two kind-string sequences."""
    n, m = len(kinds_a), len(kinds_b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if kinds_a[i - 1] == kinds_b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],  # delete
                    dp[i][j - 1],  # insert
                    dp[i - 1][j - 1],  # substitute
                )
    return dp


def align_process_events(
    target_events: Sequence[ProcessEvent],
    extracted_events: Sequence[ProcessEvent],
) -> ProcessEventAlignmentResult:
    """Align two process event sequences using Levenshtein backtrace.

    Returns matched pairs (same kind), plus unmatched events on each side,
    along with the edit distance.
    """
    kinds_a = [normalize_kind(e.kind) for e in target_events]
    kinds_b = [normalize_kind(e.kind) for e in extracted_events]

    dp = _levenshtein_dp(kinds_a, kinds_b)
    edit_distance = dp[len(kinds_a)][len(kinds_b)]

    # Backtrace to find alignment
    matched_pairs: list[tuple[ProcessEvent, ProcessEvent]] = []
    unmatched_target: list[ProcessEvent] = []
    unmatched_extracted: list[ProcessEvent] = []
    alignment: list[tuple[ProcessEvent | None, ProcessEvent | None]] = []

    i, j = len(kinds_a), len(kinds_b)
    while i > 0 or j > 0:
        if i > 0 and j > 0 and kinds_a[i - 1] == kinds_b[j - 1]:
            # Match
            matched_pairs.append((target_events[i - 1], extracted_events[j - 1]))
            alignment.append((target_events[i - 1], extracted_events[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            # Substitution — both are consumed but don't match
            unmatched_target.append(target_events[i - 1])
            unmatched_extracted.append(extracted_events[j - 1])
            alignment.append((target_events[i - 1], extracted_events[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            # Deletion from target (target event has no match)
            unmatched_target.append(target_events[i - 1])
            alignment.append((target_events[i - 1], None))
            i -= 1
        else:
            # Insertion from extracted (extracted event has no match)
            unmatched_extracted.append(extracted_events[j - 1])
            alignment.append((None, extracted_events[j - 1]))
            j -= 1

    # Reverse since we backtraced from the end
    matched_pairs.reverse()
    unmatched_target.reverse()
    unmatched_extracted.reverse()
    alignment.reverse()

    return ProcessEventAlignmentResult(
        matched_pairs=matched_pairs,
        unmatched_target=unmatched_target,
        unmatched_extracted=unmatched_extracted,
        edit_distance=edit_distance,
        alignment=alignment,
    )


def process_event_edit_distance(
    events_a: Sequence[ProcessEvent],
    events_b: Sequence[ProcessEvent],
) -> int:
    """Compute edit distance between two ordered lists of ProcessEvents,
    comparing only the ``kind`` field.

    Uses standard dynamic-programming Levenshtein distance.
    """
    kinds_a = [normalize_kind(e.kind) for e in events_a]
    kinds_b = [normalize_kind(e.kind) for e in events_b]
    dp = _levenshtein_dp(kinds_a, kinds_b)
    return dp[len(kinds_a)][len(kinds_b)]


def alignment_kind_metrics(result: ProcessEventAlignmentResult) -> tuple[float, float, float]:
    """Compute process kind P/R/F1 from alignment matched pairs.

    Returns (precision, recall, f1).
    """
    tp = len(result.matched_pairs)
    target = tp + len(result.unmatched_target)
    extracted = tp + len(result.unmatched_extracted)
    prec = tp / extracted if extracted else 0.0
    rec = tp / target if target else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


# ---------------------------------------------------------------------------
# Comparable-item extraction
# ---------------------------------------------------------------------------


def _extract_comparable_items(material: Material[Any]) -> list[ComparableItem]:
    """Extract a flat list of ComparableItem wrappers from a material.

    Handles top-level Measurement, CompMeasurement, LatticeMeasurement,
    and GlobalLatticeParam (sub-fields). Configuration objects are matched
    separately via match_configurations().
    """
    items: list[ComparableItem] = []
    for m in material.measurements:
        if isinstance(m, Measurement):
            items.append(ComparableItem(type="measurement", item=m))
        elif isinstance(m, CompMeasurement):
            items.append(ComparableItem(type="composition", item=m))
        elif isinstance(m, LatticeMeasurement):
            items.append(ComparableItem(type="lattice", item=m))
        elif isinstance(m, GlobalLatticeParam):
            glp_name = m.name or ""
            if m.lattice is not None:
                items.append(ComparableItem(type="lattice", item=m.lattice, context=glp_name))
            if m.struct is not None:
                items.append(ComparableItem(type="struct", item=m.struct, context=glp_name))
            if m.phase_fraction is not None:
                items.append(ComparableItem(type="phase_fraction", item=m.phase_fraction, context=glp_name))
    return items


def _count_comparable_items(material: Material[Any]) -> int:
    """Count the number of comparable items in a material (including config measurements)."""
    count = len(_extract_comparable_items(material))
    for config in _extract_configurations(material):
        count += len(_extract_config_comparable_items(config))
    return count


# ---------------------------------------------------------------------------
# Value-level decomposition
# ---------------------------------------------------------------------------


@dataclass
class ValueCountResult:
    """Counts of matching vs total sub-values for a matched pair."""

    tp: float  # number of matched sub-values (can be fractional for qualifier compat)
    target_count: int  # total sub-values in the target item
    extracted_count: int  # total sub-values in the extracted item


def _count_item_values(item: ComparableItem) -> int:
    """Count the number of individual sub-values in an unmatched ComparableItem."""
    if item.type == "measurement":
        m: Measurement = item.item
        count = 1  # primary value
        if m.temperature is not None:
            count += 1
        if m.pressure is not None:
            count += 1
        return count
    elif item.type == "composition":
        comp: CompMeasurement = item.item
        return len(comp.composition.as_dict())
    elif item.type == "lattice":
        return 6  # a, b, c, alpha, beta, gamma
    elif item.type == "struct":
        return 1
    elif item.type == "phase_fraction":
        return 1
    return 1


def _compare_item_values(target: ComparableItem, extracted: ComparableItem, match_score: float) -> ValueCountResult:
    """Compare sub-values between a matched pair of ComparableItems.

    For matched pairs, the primary matching criterion is assumed correct
    (it passed the matching threshold). Additional sub-values (temperature,
    pressure) are compared individually.
    """
    if target.type == "measurement":
        t_m: Measurement = target.item
        e_m: Measurement = extracted.item
        t_count = 1
        e_count = 1
        # Primary value matches (it's the matching criterion); use match_score
        tp = match_score
        # Temperature
        if t_m.temperature is not None:
            t_count += 1
        if e_m.temperature is not None:
            e_count += 1
        if t_m.temperature is not None and e_m.temperature is not None:
            tp += _quantity_score(t_m.temperature, e_m.temperature)
        # Pressure
        if t_m.pressure is not None:
            t_count += 1
        if e_m.pressure is not None:
            e_count += 1
        if t_m.pressure is not None and e_m.pressure is not None:
            tp += _quantity_score(t_m.pressure, e_m.pressure)
        return ValueCountResult(tp=tp, target_count=t_count, extracted_count=e_count)
    elif target.type == "composition":
        # All elements match (formula must match for the pair to be matched)
        n_elements = len(target.item.composition.as_dict())
        return ValueCountResult(tp=float(n_elements), target_count=n_elements, extracted_count=n_elements)
    elif target.type == "lattice":
        # All 6 params match (all must be within tolerance)
        return ValueCountResult(tp=6.0, target_count=6, extracted_count=6)
    elif target.type == "struct":
        return ValueCountResult(tp=1.0, target_count=1, extracted_count=1)
    elif target.type == "phase_fraction":
        return ValueCountResult(tp=match_score, target_count=1, extracted_count=1)
    return ValueCountResult(tp=match_score, target_count=1, extracted_count=1)


def _count_process_event_values(event: ProcessEvent) -> int:
    """Count individual sub-values in a ProcessEvent."""
    count = 1  # kind
    if event.temperature is not None:
        count += 1
    if event.duration is not None:
        count += 1
    return count


def _compare_process_event_values(target_evt: ProcessEvent, extracted_evt: ProcessEvent) -> ValueCountResult:
    """Compare sub-values between a matched pair of ProcessEvents."""
    t_count = 1  # kind
    e_count = 1
    tp = 1.0  # kind matches (they're aligned as same-kind)

    if target_evt.temperature is not None:
        t_count += 1
    if extracted_evt.temperature is not None:
        e_count += 1
    if target_evt.temperature is not None and extracted_evt.temperature is not None:
        tp += _quantity_score(target_evt.temperature, extracted_evt.temperature)

    if target_evt.duration is not None:
        t_count += 1
    if extracted_evt.duration is not None:
        e_count += 1
    if target_evt.duration is not None and extracted_evt.duration is not None:
        tp += _quantity_score(target_evt.duration, extracted_evt.duration)

    return ValueCountResult(tp=tp, target_count=t_count, extracted_count=e_count)


# ---------------------------------------------------------------------------
# Item-level matching
# ---------------------------------------------------------------------------


def _units_equal(a: pint.Unit, b: pint.Unit) -> bool:
    """Check if two pint units are equivalent."""
    return a == b


_CONTEXT_PUNCT_RE = re.compile(r"[()[\],:/+]")

# Minimum score for a comparable item match to be accepted.
MIN_ITEM_MATCH_SCORE = 0.25


def _context_score(a: str | None, b: str | None) -> float:
    """Score similarity between two context strings using Jaccard similarity.

    Both None → 1.0, one None → 0.0, both present → token-set Jaccard.
    """
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0

    def _tokenize(s: str) -> set[str]:
        s = _CONTEXT_PUNCT_RE.sub(" ", s.lower())
        return set(s.split())

    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)

    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# Qualifier compatibility matrix — indexed by (row, col) ValueQualifier values.
_QUALIFIER_COMPAT: dict[tuple[ValueQualifier, ValueQualifier], float] = {}


def _build_qualifier_compat_table() -> None:
    """Populate the qualifier compatibility lookup table."""
    E = ValueQualifier.EXACT
    A = ValueQualifier.APPROXIMATE
    AB = ValueQualifier.ABOVE
    BL = ValueQualifier.BELOW
    GE = ValueQualifier.ABOVE_OR_EQUAL
    LE = ValueQualifier.BELOW_OR_EQUAL
    MA = ValueQualifier.MUCH_ABOVE
    MB = ValueQualifier.MUCH_BELOW

    # Rows: E, A, AB, BL, GE, LE, MA, MB
    order = [E, A, AB, BL, GE, LE, MA, MB]
    matrix = [
        # E     A     AB    BL    GE    LE    MA    MB
        [1.0, 0.75, 0.5, 0.5, 0.5, 0.5, 0.25, 0.25],  # EXACT
        [0.75, 1.0, 0.5, 0.5, 0.5, 0.5, 0.25, 0.25],  # APPROXIMATE
        [0.5, 0.5, 1.0, 0, 0.75, 0, 0.5, 0],  # ABOVE
        [0.5, 0.5, 0, 1.0, 0, 0.75, 0, 0.5],  # BELOW
        [0.5, 0.5, 0.75, 0, 1.0, 0, 0.5, 0],  # ABOVE_OR_EQUAL
        [0.5, 0.5, 0, 0.75, 0, 1.0, 0, 0.5],  # BELOW_OR_EQUAL
        [0.25, 0.25, 0.5, 0, 0.5, 0, 1.0, 0],  # MUCH_ABOVE
        [0.25, 0.25, 0, 0.5, 0, 0.5, 0, 1.0],  # MUCH_BELOW
    ]
    for i, qi in enumerate(order):
        for j, qj in enumerate(order):
            _QUALIFIER_COMPAT[(qi, qj)] = matrix[i][j]


_build_qualifier_compat_table()


def _qualifier_compatibility(a: ValueQualifier, b: ValueQualifier) -> float:
    """Return compatibility score (0.0–1.0) between two value qualifiers."""
    return _QUALIFIER_COMPAT.get((a, b), 0.0)


def _split_kind_to_words(kind_str: str) -> set[str]:
    """Split a kind string into lowercase words, handling both snake_case and camelCase."""
    # First split by underscores
    parts = kind_str.split("_")
    words: set[str] = set()
    for part in parts:
        # Split camelCase: insert boundary before uppercase letters
        camel_words = re.sub(r"([a-z])([A-Z])", r"\1_\2", part).split("_")
        for w in camel_words:
            w_lower = w.lower().strip()
            if w_lower:
                words.add(w_lower)
    return words


def _kind_match_score(a_kind: str, b_kind: str, a_is_enum: bool, b_is_enum: bool) -> float:
    """Score how well two measurement kinds match (0.0–1.0).

    Exact string match → 1.0.
    If both are enums but don't match → 0.0.
    If at least one kind is a plain string (not an enum), uses fuzzy word
    overlap to allow generous matching of free-form kind strings.
    """
    if a_kind == b_kind:
        return 1.0

    # If both are enums, require exact match
    if a_is_enum and b_is_enum:
        return 0.0

    # At least one is a string – do fuzzy word matching
    a_words = _split_kind_to_words(a_kind)
    b_words = _split_kind_to_words(b_kind)

    overlap = a_words & b_words
    if not overlap:
        return 0.0

    n_overlap = len(overlap)
    if n_overlap >= 2:
        return 0.7
    else:
        # Single word match - lower confidence, scale by Jaccard similarity
        union = a_words | b_words
        jaccard = n_overlap / len(union) if union else 0.0
        return max(0.3, jaccard)


_ROOM_TEMP_K = ureg.Quantity(ROOM_TEMPERATURE.numeric_value, ROOM_TEMPERATURE.unit).to("kelvin").magnitude
_ROOM_TEMP_TOLERANCE_K = 2.0
_AMBIENT_PRESSURE_RANGE_ATM = (0.9, 1.1)
_CONDITION_AMBIENT_SCORE = 0.85  # soft penalty when one side omits an ambient condition

_QUALIFIER_WEIGHT = 1.0
_TEMPERATURE_WEIGHT = 2.0
_PRESSURE_WEIGHT = 2.0


def _is_room_temperature(q: Quantity) -> bool:
    """Check if a Quantity represents approximately room temperature."""
    if q.numeric_value is None:
        return False
    try:
        temp_k = ureg.Quantity(q.numeric_value, q.unit).to("kelvin").magnitude
        return abs(temp_k - _ROOM_TEMP_K) <= _ROOM_TEMP_TOLERANCE_K
    except Exception:
        return False


def _is_ambient_pressure(q: Quantity) -> bool:
    """Check if a Quantity represents approximately ambient/atmospheric pressure."""
    if q.numeric_value is None:
        return False
    try:
        p_atm = ureg.Quantity(q.numeric_value, q.unit).to("atm").magnitude
        return _AMBIENT_PRESSURE_RANGE_ATM[0] <= p_atm <= _AMBIENT_PRESSURE_RANGE_ATM[1]
    except Exception:
        return False


def _condition_match_score(
    a: Quantity | None,
    b: Quantity | None,
    is_ambient_fn: Any,
) -> tuple[float, bool]:
    """Score how well two condition quantities (temperature/pressure) match.

    Returns (score, is_active). is_active is False when both are None,
    meaning this condition should not factor into the blended score.
    """
    if a is None and b is None:
        return 0.0, False
    if a is not None and b is not None:
        return _quantity_score(a, b), True
    # One is None, one isn't — check if the present one is ambient
    present = a if a is not None else b
    if is_ambient_fn(present):
        return _CONDITION_AMBIENT_SCORE, True
    return 0.0, True


def measurement_score(a: Measurement[Any], b: Measurement[Any]) -> float:
    """Score how well two Measurement objects match (0.0–1.0).

    kind/value/unit mismatch → 0.0; otherwise blends qualifier compatibility
    with temperature and pressure matching. Temperature and pressure each
    have 2x the weight of the qualifier.
    """
    a_kind = a.kind.value if hasattr(a.kind, "value") else str(a.kind)
    b_kind = b.kind.value if hasattr(b.kind, "value") else str(b.kind)
    a_is_enum = hasattr(a.kind, "value")
    b_is_enum = hasattr(b.kind, "value")

    kind_score = _kind_match_score(a_kind, b_kind, a_is_enum, b_is_enum)
    if kind_score == 0.0:
        return 0.0

    # numeric value
    if a.numeric_value is not None and b.numeric_value is not None:
        if abs(a.numeric_value - b.numeric_value) > 1e-6:
            return 0.0
    elif a.numeric_value != b.numeric_value:  # one is None, other isn't
        return 0.0

    # unit
    if not _units_equal(a.unit, b.unit):
        return 0.0

    # Blend qualifier with condition matching
    qualifier_score = _qualifier_compatibility(a.value_qualifier, b.value_qualifier)
    components: list[tuple[float, float]] = [(_QUALIFIER_WEIGHT, qualifier_score)]

    temp_score, temp_active = _condition_match_score(a.temperature, b.temperature, _is_room_temperature)
    if temp_active:
        components.append((_TEMPERATURE_WEIGHT, temp_score))

    pressure_score, pressure_active = _condition_match_score(a.pressure, b.pressure, _is_ambient_pressure)
    if pressure_active:
        components.append((_PRESSURE_WEIGHT, pressure_score))

    total_weight = sum(w for w, _ in components)
    blended = sum(w * s for w, s in components) / total_weight

    return kind_score * blended


def _compositions_matched(a: CompMeasurement, b: CompMeasurement) -> bool:
    """Check if two CompMeasurement objects match on normalized fractional composition."""
    norm_a = a.composition.fractional_composition.alphabetical_formula
    norm_b = b.composition.fractional_composition.alphabetical_formula
    return norm_a == norm_b


_COMP_METHOD_WEIGHT = 0.25


def _comp_measurement_score(target: CompMeasurement, extracted: CompMeasurement) -> float:
    """Score how well two CompMeasurement objects match (0.0–1.0).

    Composition formula accounts for 75% of the score, method for 25%.
    If the target method is ``Unspecified``, method is treated as matching.
    """
    if not _compositions_matched(target, extracted):
        return 0.0

    # Also allow balance compositions to pass through. this is because some papers are ambiguous
    # about how they measured the composition, so it's kinda the same as "unspecified"
    if target.method == MeasurementMethod.Unspecified or target.method == MeasurementMethod.Balance:
        method_score = 1.0
    else:
        method_score = 1.0 if target.method == extracted.method else 0.0

    return (1.0 - _COMP_METHOD_WEIGHT) + _COMP_METHOD_WEIGHT * method_score


def _lattice_matched(a: PymatgenLattice, b: PymatgenLattice, tol: float = 0.01) -> bool:
    """Check if two Lattice objects match within tolerance on (a, b, c, alpha, beta, gamma)."""
    params_a = a.parameters  # (a, b, c, alpha, beta, gamma)
    params_b = b.parameters
    return all(abs(pa - pb) < tol for pa, pb in zip(params_a, params_b))


def _quantity_score(a: Quantity, b: Quantity) -> float:
    """Score how well two Quantity objects match (0.0–1.0).

    value/unit mismatch → 0.0; otherwise returns qualifier compatibility.
    """
    if not isinstance(a, Quantity) or not isinstance(b, Quantity):
        return 0.0
    if a.numeric_value is not None and b.numeric_value is not None:
        if abs(a.numeric_value - b.numeric_value) > 1e-6:
            return 0.0
    elif a.numeric_value != b.numeric_value:
        return 0.0
    if not _units_equal(a.unit, b.unit):
        return 0.0
    return _qualifier_compatibility(a.value_qualifier, b.value_qualifier)


def _comparable_item_score(a: ComparableItem, b: ComparableItem) -> float:
    """Score how well two ComparableItems match (0.0–1.0).

    Items must have the same type. Context similarity is factored in via
    Jaccard scoring. The final score is context_score * item_score.
    """
    if a.type != b.type:
        return 0.0

    context_score = _context_score(a.context, b.context)
    if context_score == 0.0:
        return 0.0

    if a.type == "measurement":
        item_score = measurement_score(a.item, b.item)
    elif a.type == "composition":
        item_score = _comp_measurement_score(a.item, b.item)
    elif a.type == "lattice":
        item_score = 1.0 if _lattice_matched(a.item.lattice, b.item.lattice) else 0.0
    elif a.type == "struct":
        item_score = 1.0 if a.item == b.item else 0.0
    elif a.type == "phase_fraction":
        item_score = _quantity_score(a.item, b.item)
    else:
        item_score = 0.0

    return context_score * item_score


def _hungarian_match(
    cost_matrix: list[list[float]],
    n_rows: int,
    n_cols: int,
    max_cost: float,
) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    """Run Hungarian algorithm and return matched/unmatched indices.

    Pairs with ``cost_matrix[r][c] < max_cost`` are considered matched.

    Returns ``(matched, unmatched_rows, unmatched_cols)`` where *matched*
    entries are ``(row_idx, col_idx, cost)``.
    """
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matched: list[tuple[int, int, float]] = []
    matched_row_set: set[int] = set()
    matched_col_set: set[int] = set()

    for r, c in zip(row_ind, col_ind):
        if r < n_rows and c < n_cols and cost_matrix[r][c] < max_cost:
            matched.append((r, c, cost_matrix[r][c]))
            matched_row_set.add(r)
            matched_col_set.add(c)

    unmatched_rows = [i for i in range(n_rows) if i not in matched_row_set]
    unmatched_cols = [j for j in range(n_cols) if j not in matched_col_set]

    return matched, unmatched_rows, unmatched_cols


def match_comparable_items(
    target_items: list[ComparableItem],
    extracted_items: list[ComparableItem],
) -> MeasurementMatchResult:
    """Match comparable items between two lists using Hungarian assignment.

    Builds a score matrix and uses ``linear_sum_assignment`` to find the
    optimal matching that maximises total score.  Only pairs with
    score >= MIN_ITEM_MATCH_SCORE are kept.
    """
    n_target = len(target_items)
    n_extracted = len(extracted_items)

    if n_target == 0:
        return MeasurementMatchResult(
            matched_pairs=[],
            unmatched_target=[],
            unmatched_extracted=list(extracted_items),
        )
    if n_extracted == 0:
        return MeasurementMatchResult(
            matched_pairs=[],
            unmatched_target=list(target_items),
            unmatched_extracted=[],
        )

    # Build cost matrix (negated scores) for minimisation.
    # Padding cells stay at 0.0 (equivalent to unmatched).
    size = max(n_target, n_extracted)
    cost_matrix = [[0.0] * size for _ in range(size)]

    for i in range(n_target):
        for j in range(n_extracted):
            cost_matrix[i][j] = -_comparable_item_score(target_items[i], extracted_items[j])

    matched, unmatched_row_ids, unmatched_col_ids = _hungarian_match(
        cost_matrix, n_target, n_extracted, max_cost=-MIN_ITEM_MATCH_SCORE,
    )

    return MeasurementMatchResult(
        matched_pairs=[(target_items[r], extracted_items[c], -cost) for r, c, cost in matched],
        unmatched_target=[target_items[i] for i in unmatched_row_ids],
        unmatched_extracted=[extracted_items[j] for j in unmatched_col_ids],
    )


# ---------------------------------------------------------------------------
# Configuration matching
# ---------------------------------------------------------------------------

CONFIG_TAGS_WEIGHT = 2.0
CONFIG_STRUCT_WEIGHT = 2.0
CONFIG_NAME_WEIGHT = 1.0
CONFIG_MEASUREMENT_WEIGHT = 3.0
CONFIG_WITHIN_WEIGHT = 2.0
CONFIG_UNMATCHED_PENALTY = 5.0


def _extract_configurations(material: Material[Any]) -> list[Configuration]:
    """Extract Configuration objects from a material's measurements."""
    return [m for m in material.measurements if isinstance(m, Configuration)]


def _extract_config_comparable_items(config: Configuration) -> list[ComparableItem]:
    """Extract ComparableItems from a single Configuration's measurements (no context tag)."""
    items: list[ComparableItem] = []
    for nested in config.measurements:
        if isinstance(nested, Measurement):
            items.append(ComparableItem(type="measurement", item=nested))
        elif isinstance(nested, LatticeMeasurement):
            items.append(ComparableItem(type="lattice", item=nested))
        elif isinstance(nested, CompMeasurement):
            items.append(ComparableItem(type="composition", item=nested))
    return items


def _build_ancestry_chain(
    config: Configuration,
    config_map: dict[str, Configuration],
) -> list[str]:
    """Walk the `within` chain and return ancestor names from root to immediate parent."""
    ancestors: list[str] = []
    current = config
    visited: set[str] = set()
    while current.within is not None and current.within not in visited:
        visited.add(current.within)
        parent = config_map.get(current.within)
        if parent is None:
            ancestors.append(current.within)
            break
        ancestors.append(parent.name or "")
        current = parent
    ancestors.reverse()
    return ancestors


def _collect_ancestry_tags(
    config: Configuration,
    config_map: dict[str, Configuration],
) -> set[ConfigTag]:
    """Collect tags from config plus all ancestors via `within` chain."""
    tags: set[ConfigTag] = set(config.tags) if config.tags else set()
    current = config
    visited: set[str] = set()
    while current.within is not None and current.within not in visited:
        visited.add(current.within)
        parent = config_map.get(current.within)
        if parent is None:
            break
        if parent.tags:
            tags |= parent.tags
        current = parent
    return tags


def _ancestry_context_string(
    config: Configuration,
    config_map: dict[str, Configuration],
) -> str:
    """Build a context string from name + ancestry for Jaccard comparison."""
    parts: list[str] = []
    ancestors = _build_ancestry_chain(config, config_map)
    parts.extend(ancestors)
    if config.name:
        parts.append(config.name)
    return " ".join(parts)


def _check_within_match(
    target_cfg: Configuration,
    extracted_cfg: Configuration,
    matched_pairs: list[tuple[Configuration, Configuration, float]],
) -> bool:
    """Check if the ``within`` (parent) relationship is structurally preserved.

    Configurations form a tree via the ``within`` field: a config with
    ``within="gamma-matrix"`` is a child of the config named "gamma-matrix".
    After Hungarian assignment pairs target configs with extracted configs,
    we need to verify that the *tree edges* were also preserved — i.e. that
    if a target child points to target parent P, and the extracted child
    points to extracted parent Q, then P and Q were themselves matched
    together in the assignment.

    This is a binary structural check used at value-scoring time.  A fuzzy
    string heuristic in ``_config_cost`` guides the Hungarian toward
    structurally-compatible matches, but only this post-assignment check can
    confirm the edge is truly preserved (since during cost computation we
    don't yet know the full assignment).

    Returns True when:
    - Both configs are roots (``within is None`` on both sides).
    - Both configs have ``within`` set, and the referenced parents appear
      as a ``(target_parent, extracted_parent)`` pair in *matched_pairs*.

    Returns False when:
    - Exactly one side has ``within`` (nesting depth mismatch).
    - Both have ``within`` but their parents were not matched together.
    """
    if target_cfg.within is None and extracted_cfg.within is None:
        return True  # both roots
    if target_cfg.within is None or extracted_cfg.within is None:
        return False  # one is nested, other isn't

    # Both have within — check if their parents were matched together
    for t_parent, e_parent, _ in matched_pairs:
        if t_parent.name == target_cfg.within and e_parent.name == extracted_cfg.within:
            return True
    return False


def _count_config_field_values(config: Configuration) -> int:
    """Count tag + struct + within values for value-level metrics."""
    count = 0
    if config.tags:
        count += len(config.tags)
    if config.struct is not None:
        count += 1
    if config.within is not None:
        count += 1
    return count


def _compare_config_field_values(
    target: Configuration,
    extracted: Configuration,
    matched_pairs: list[tuple[Configuration, Configuration, float]] | None = None,
) -> ValueCountResult:
    """Compare tags/struct/within between matched configs."""
    tp = 0.0
    t_count = 0
    e_count = 0

    # Tags comparison — each tag is an individual item
    t_tags = set(target.tags) if target.tags else set()
    e_tags = set(extracted.tags) if extracted.tags else set()
    t_count += len(t_tags)
    e_count += len(e_tags)
    tp += len(t_tags & e_tags)

    # Struct comparison — 1 item
    if target.struct is not None:
        t_count += 1
    if extracted.struct is not None:
        e_count += 1
    if target.struct is not None and extracted.struct is not None:
        if target.struct == extracted.struct:
            tp += 1.0

    # Within — 1 item if present on either side
    if target.within is not None:
        t_count += 1
    if extracted.within is not None:
        e_count += 1
    if target.within is not None or extracted.within is not None:
        # This check below ensures that we are checking for the tree structure as well.
        # unfortunately, we do not use this edge information when calculating the cost since that
        # is an extremely complicated matching algorithm. Since our eval script is already thousands of lines
        # long, it's probably best. It's also a tradeoff between: if you care more about
        # getting the edge relationships vs getting the numbers into Configurations
        # By only checking the "within" field afterwards, we care a lot more about
        # getting the right values in Configurations
        if matched_pairs is not None and _check_within_match(target, extracted, matched_pairs):
            tp += 1.0

    return ValueCountResult(tp=tp, target_count=t_count, extracted_count=e_count)


def _config_cost(
    target: Configuration,
    extracted: Configuration,
    target_config_map: dict[str, Configuration],
    extracted_config_map: dict[str, Configuration],
) -> tuple[float, MeasurementMatchResult, ConfigScoreBreakdown]:
    """Compute the cost of matching two configurations.

    Returns (cost, nested_measurement_result, breakdown).
    """
    # Tags similarity (Jaccard on ancestry-collected tags)
    t_tags = _collect_ancestry_tags(target, target_config_map)
    e_tags = _collect_ancestry_tags(extracted, extracted_config_map)
    if not t_tags and not e_tags:
        tags_jaccard = 1.0
    elif not t_tags or not e_tags:
        tags_jaccard = 0.0
    else:
        tags_jaccard = len(t_tags & e_tags) / len(t_tags | e_tags)

    # Struct match
    if target.struct is None and extracted.struct is None:
        struct_match = 1.0
    elif target.struct is not None and extracted.struct is not None:
        struct_match = 1.0 if target.struct == extracted.struct else 0.0
    else:
        struct_match = 0.0

    # Name/ancestry similarity (Jaccard token similarity)
    t_context = _ancestry_context_string(target, target_config_map)
    e_context = _ancestry_context_string(extracted, extracted_config_map)
    if not t_context and not e_context:
        name_sim = 1.0
    else:
        name_sim = _context_score(t_context or None, e_context or None)

    # Within similarity (fuzzy heuristic — exact structural check is post-assignment)
    if target.within is None and extracted.within is None:
        within_sim = 1.0
    elif target.within is None or extracted.within is None:
        within_sim = 0.0
    else:
        within_sim = _context_score(target.within, extracted.within)

    # Nested measurement matching
    t_items = _extract_config_comparable_items(target)
    e_items = _extract_config_comparable_items(extracted)
    meas_result = match_comparable_items(t_items, e_items)
    if meas_result.total > 0:
        meas_sim = meas_result.match_score / meas_result.total
    else:
        meas_sim = 1.0

    cost = (
        CONFIG_TAGS_WEIGHT * (1.0 - tags_jaccard)
        + CONFIG_STRUCT_WEIGHT * (1.0 - struct_match)
        + CONFIG_NAME_WEIGHT * (1.0 - name_sim)
        + CONFIG_MEASUREMENT_WEIGHT * (1.0 - meas_sim)
        + CONFIG_WITHIN_WEIGHT * (1.0 - within_sim)
    )

    breakdown = ConfigScoreBreakdown(
        tags=tags_jaccard,
        struct=struct_match,
        name=name_sim,
        measurement=meas_sim,
        within=within_sim,
    )

    return cost, meas_result, breakdown


def match_configurations(
    target_configs: list[Configuration],
    extracted_configs: list[Configuration],
    target_config_map: dict[str, Configuration],
    extracted_config_map: dict[str, Configuration],
) -> ConfigurationMatchResult:
    """Match configurations using Hungarian assignment."""
    n_target = len(target_configs)
    n_extracted = len(extracted_configs)

    if n_target == 0 and n_extracted == 0:
        return ConfigurationMatchResult(
            matched_pairs=[],
            unmatched_target=[],
            unmatched_extracted=[],
            nested_measurement_results=[],
            breakdowns=[],
        )

    size = max(n_target, n_extracted)
    cost_matrix = [[CONFIG_UNMATCHED_PENALTY] * size for _ in range(size)]
    meas_results: dict[tuple[int, int], MeasurementMatchResult] = {}
    breakdown_map: dict[tuple[int, int], ConfigScoreBreakdown] = {}

    for i in range(n_target):
        for j in range(n_extracted):
            cost, meas_result, breakdown = _config_cost(
                target_configs[i],
                extracted_configs[j],
                target_config_map,
                extracted_config_map,
            )
            cost_matrix[i][j] = cost
            meas_results[(i, j)] = meas_result
            breakdown_map[(i, j)] = breakdown

    matched, unmatched_row_ids, unmatched_col_ids = _hungarian_match(
        cost_matrix, n_target, n_extracted, max_cost=CONFIG_UNMATCHED_PENALTY,
    )

    max_weight = (
        CONFIG_TAGS_WEIGHT
        + CONFIG_STRUCT_WEIGHT
        + CONFIG_NAME_WEIGHT
        + CONFIG_MEASUREMENT_WEIGHT
        + CONFIG_WITHIN_WEIGHT
    )
    matched_pairs: list[tuple[Configuration, Configuration, float]] = []
    nested_results: list[MeasurementMatchResult] = []
    breakdowns: list[ConfigScoreBreakdown] = []

    for r, c, cost in matched:
        score = max(0.0, 1.0 - cost / max_weight)
        matched_pairs.append((target_configs[r], extracted_configs[c], score))
        nested_results.append(meas_results[(r, c)])
        breakdowns.append(breakdown_map[(r, c)])

    return ConfigurationMatchResult(
        matched_pairs=matched_pairs,
        unmatched_target=[target_configs[i] for i in unmatched_row_ids],
        unmatched_extracted=[extracted_configs[j] for j in unmatched_col_ids],
        nested_measurement_results=nested_results,
        breakdowns=breakdowns,
    )


def _build_config_map(configs: list[Configuration]) -> dict[str, Configuration]:
    """Build a name→Configuration map for ancestry lookups."""
    config_map: dict[str, Configuration] = {}
    for c in configs:
        if c.name:
            config_map[c.name] = c
    return config_map


# ---------------------------------------------------------------------------
# Material-level cost
# ---------------------------------------------------------------------------

# Weights for combining sub-costs into a single material cost.
# Tweak these as needed; the exact values are less important than relative scale.
PROCESS_DISTANCE_WEIGHT = 1.0
MEASUREMENT_MISMATCH_WEIGHT = 1.0


@dataclass
class MaterialCostResult:
    """Detailed result of computing the cost between two materials."""

    cost: float
    process_edit_distance: int
    measurement_result: MeasurementMatchResult
    process_alignment: ProcessEventAlignmentResult | None = None
    config_match: ConfigurationMatchResult | None = None


def material_cost(
    target: Material,
    extracted: Material,
    target_synthesis: dict[str, SynthesisGroup],
    extracted_synthesis: dict[str, SynthesisGroup],
) -> MaterialCostResult:
    """Compute the cost of matching *target* to *extracted*."""
    # --- process chain alignment ---
    target_events = normalize_process_events(resolve_process_events(target, target_synthesis))
    extracted_events = normalize_process_events(resolve_process_events(extracted, extracted_synthesis))
    proc_alignment = align_process_events(target_events, extracted_events)
    proc_dist = proc_alignment.edit_distance

    # --- configuration matching ---
    target_configs = _extract_configurations(target)
    extracted_configs = _extract_configurations(extracted)
    target_config_map = _build_config_map(target_configs)
    extracted_config_map = _build_config_map(extracted_configs)
    config_result = match_configurations(target_configs, extracted_configs, target_config_map, extracted_config_map)

    # --- non-config comparable-item matching ---
    target_items = _extract_comparable_items(target)
    extracted_items = _extract_comparable_items(extracted)
    m_result = match_comparable_items(target_items, extracted_items)
    mismatches = m_result.total - m_result.match_score

    # --- config cost contribution ---
    config_cost = 0.0
    for t_cfg, e_cfg, score in config_result.matched_pairs:
        config_cost += 1.0 - score
    config_cost += len(config_result.unmatched_target) + len(config_result.unmatched_extracted)
    # Add nested measurement mismatches from matched config pairs
    for nested_meas in config_result.nested_measurement_results:
        nested_mismatches = nested_meas.total - nested_meas.match_score
        config_cost += MEASUREMENT_MISMATCH_WEIGHT * nested_mismatches

    cost = PROCESS_DISTANCE_WEIGHT * proc_dist + MEASUREMENT_MISMATCH_WEIGHT * mismatches + config_cost
    return MaterialCostResult(
        cost=cost,
        process_edit_distance=proc_dist,
        measurement_result=m_result,
        process_alignment=proc_alignment,
        config_match=config_result,
    )


# ---------------------------------------------------------------------------
# Hungarian matching across experiments
# ---------------------------------------------------------------------------

# Penalty for leaving a material unmatched (controls whether the algorithm
# prefers a bad match over no match).  Set high enough that expanded
# comparable-item counts don't accidentally push real matches over the
# threshold.
UNMATCHED_PENALTY = 50.0


def _collect_materials(
    items: Sequence[Experiment],
) -> list[MaterialWithContext]:
    """Convert experiments into MaterialWithContext entries."""

    result: list[MaterialWithContext] = []
    for item in items:
        for m in item.output_materials:
            result.append(MaterialWithContext(material=m, synthesis_group_map=item.synthesis_group_map))
    return result


def compare_experiments(
    target: Sequence[Experiment],
    extracted: Sequence[Experiment],
) -> ExperimentComparisonResult:
    """Compare two sets of experiments by optimal material matching.

    Builds a cost matrix using ``material_cost`` and runs the Hungarian algorithm
    (``linear_sum_assignment``) to find the minimum-cost assignment. Materials
    that are too expensive to match (cost >= ``UNMATCHED_PENALTY``) are left
    unmatched.
    """
    target_items = _collect_materials(target)
    extracted_items = _collect_materials(extracted)

    n_target = len(target_items)
    n_extracted = len(extracted_items)

    if n_target == 0:
        raise ValueError("target must not be empty")

    if n_extracted == 0:
        return ExperimentComparisonResult(
            matched_materials=[],
            unmatched_target_materials=[item.material for item in target_items],
            unmatched_extracted_materials=[],
            total_cost=0.0,
        )

    # Build cost matrix — pad to square with UNMATCHED_PENALTY so the solver
    # can choose to leave items unmatched.
    size = max(n_target, n_extracted)
    cost_results: dict[tuple[int, int], MaterialCostResult] = {}
    cost_matrix = [[UNMATCHED_PENALTY] * size for _ in range(size)]

    for i in range(n_target):
        for j in range(n_extracted):
            result = material_cost(
                target_items[i].material,
                extracted_items[j].material,
                target_items[i].synthesis_group_map,
                extracted_items[j].synthesis_group_map,
            )
            cost_matrix[i][j] = result.cost
            cost_results[(i, j)] = result

    matched, unmatched_row_ids, unmatched_col_ids = _hungarian_match(
        cost_matrix, n_target, n_extracted, max_cost=UNMATCHED_PENALTY,
    )

    matched_materials: list[MaterialMatchResult] = []
    total_cost = 0.0

    for r, c, cost in matched:
        result = cost_results[(r, c)]
        matched_materials.append(
            MaterialMatchResult(
                target=target_items[r].material,
                extracted=extracted_items[c].material,
                cost=result.cost,
                process_edit_distance=result.process_edit_distance,
                measurement_result=result.measurement_result,
                process_alignment=result.process_alignment,
                config_match=result.config_match,
            )
        )
        total_cost += result.cost

    return ExperimentComparisonResult(
        matched_materials=matched_materials,
        unmatched_target_materials=[target_items[i].material for i in unmatched_row_ids],
        unmatched_extracted_materials=[extracted_items[j].material for j in unmatched_col_ids],
        total_cost=total_cost,
    )


# ---------------------------------------------------------------------------
# Multi-level metrics
# ---------------------------------------------------------------------------


def _prf1(tp: float, total_target: int, total_extracted: int) -> tuple[float, float, float]:
    """Compute precision, recall, F1 from TP and total counts."""
    p = tp / total_extracted if total_extracted else 0.0
    r = tp / total_target if total_target else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


_OVERALL_F1_WEIGHTS: dict[str, float] = {
    "value": 0.50,
    "config": 0.15,
    "process": 0.20,
    "material": 0.15,
}


@dataclass
class MultiLevelMetrics:
    """Precision / Recall / F1 at five granularity levels."""

    # Value level (most granular)
    value_tp: float
    value_target: int
    value_extracted: int

    # Measurement level (ComparableItem)
    measurement_tp: float
    measurement_target: int
    measurement_extracted: int

    # Configuration level
    config_tp: float = 0.0
    config_target: int = 0
    config_extracted: int = 0

    # Process event level
    process_tp: int = 0
    process_target: int = 0
    process_extracted: int = 0

    # Material level
    material_tp: int = 0
    material_target: int = 0
    material_extracted: int = 0

    # --- Value-level P/R/F1 ---

    @property
    def value_precision(self) -> float:
        return self.value_tp / self.value_extracted if self.value_extracted else 0.0

    @property
    def value_recall(self) -> float:
        return self.value_tp / self.value_target if self.value_target else 0.0

    @property
    def value_f1(self) -> float:
        p, r = self.value_precision, self.value_recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    # --- Measurement-level P/R/F1 ---

    @property
    def measurement_precision(self) -> float:
        return self.measurement_tp / self.measurement_extracted if self.measurement_extracted else 0.0

    @property
    def measurement_recall(self) -> float:
        return self.measurement_tp / self.measurement_target if self.measurement_target else 0.0

    @property
    def measurement_f1(self) -> float:
        p, r = self.measurement_precision, self.measurement_recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    # --- Configuration-level P/R/F1 ---

    @property
    def config_precision(self) -> float:
        return self.config_tp / self.config_extracted if self.config_extracted else 0.0

    @property
    def config_recall(self) -> float:
        return self.config_tp / self.config_target if self.config_target else 0.0

    @property
    def config_f1(self) -> float:
        p, r = self.config_precision, self.config_recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    # --- Process-event-level P/R/F1 ---

    @property
    def process_precision(self) -> float:
        return self.process_tp / self.process_extracted if self.process_extracted else 0.0

    @property
    def process_recall(self) -> float:
        return self.process_tp / self.process_target if self.process_target else 0.0

    @property
    def process_f1(self) -> float:
        p, r = self.process_precision, self.process_recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    # --- Material-level P/R/F1 ---

    @property
    def material_precision(self) -> float:
        return self.material_tp / self.material_extracted if self.material_extracted else 0.0

    @property
    def material_recall(self) -> float:
        return self.material_tp / self.material_target if self.material_target else 0.0

    @property
    def material_f1(self) -> float:
        p, r = self.material_precision, self.material_recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    # --- Overall metrics ---

    def _active_levels(self) -> dict[str, tuple[int, int]]:
        """Return levels that have at least one target or extracted item."""
        level_data: dict[str, tuple[int, int]] = {
            "value": (self.value_target, self.value_extracted),
            "config": (self.config_target, self.config_extracted),
            "process": (self.process_target, self.process_extracted),
            "material": (self.material_target, self.material_extracted),
        }
        return {k: v for k, v in level_data.items() if v[0] > 0 or v[1] > 0}

    def _weighted_average(self, values: dict[str, float]) -> float:
        """Weighted average over active levels, redistributing inactive weights."""
        active = self._active_levels()
        if not active:
            return 0.0
        total_weight = sum(_OVERALL_F1_WEIGHTS[k] for k in active)
        return sum(_OVERALL_F1_WEIGHTS[k] * values[k] for k in active) / total_weight

    @property
    def overall_precision(self) -> float:
        """Weighted average of level precisions (excluding measurement)."""
        return self._weighted_average(
            {
                "value": self.value_precision,
                "config": self.config_precision,
                "process": self.process_precision,
                "material": self.material_precision,
            }
        )

    @property
    def overall_recall(self) -> float:
        """Weighted average of level recalls (excluding measurement)."""
        return self._weighted_average(
            {
                "value": self.value_recall,
                "config": self.config_recall,
                "process": self.process_recall,
                "material": self.material_recall,
            }
        )

    @property
    def overall_f1(self) -> float:
        """Weighted average of level F1s (excluding measurement, which is subsumed by value).

        Levels with no target and no extracted items are excluded and their
        weight is redistributed proportionally to the remaining levels.
        """
        return self._weighted_average(
            {
                "value": self.value_f1,
                "config": self.config_f1,
                "process": self.process_f1,
                "material": self.material_f1,
            }
        )


def _accumulate_measurement_values(
    meas_result: MeasurementMatchResult,
    val_tp: float,
    val_target: int,
    val_extracted: int,
) -> tuple[float, int, int]:
    """Accumulate value-level counts from a MeasurementMatchResult."""
    for t_item, e_item, score in meas_result.matched_pairs:
        vcr = _compare_item_values(t_item, e_item, score)
        val_tp += vcr.tp
        val_target += vcr.target_count
        val_extracted += vcr.extracted_count

    for t_item in meas_result.unmatched_target:
        val_target += _count_item_values(t_item)

    for e_item in meas_result.unmatched_extracted:
        val_extracted += _count_item_values(e_item)

    return val_tp, val_target, val_extracted


def compute_multi_level_metrics(
    result: ExperimentComparisonResult,
) -> MultiLevelMetrics:
    """Aggregate counts at all five levels from an ExperimentComparisonResult.

    Process events are only counted for matched material pairs (unmatched materials
    are penalized at material level, avoiding double-penalization).
    """
    # --- Material level ---
    material_tp = len(result.matched_materials)
    material_target = result.num_target_materials
    material_extracted = result.num_extracted_materials

    # --- Measurement level (reuses existing ComparableItem counts) ---
    meas_tp = result.num_matched_items
    meas_target = result.num_total_target_items
    meas_extracted = result.num_total_extracted_items

    # --- Configuration level ---
    config_tp = 0.0
    config_target = 0
    config_extracted = 0

    # --- Process event level and Value level ---
    proc_tp = 0
    proc_target = 0
    proc_extracted = 0

    val_tp = 0.0
    val_target = 0
    val_extracted = 0

    for match in result.matched_materials:
        # -- Non-config measurement values --
        val_tp, val_target, val_extracted = _accumulate_measurement_values(
            match.measurement_result, val_tp, val_target, val_extracted
        )

        # -- Configuration level and values --
        cm = match.config_match
        if cm is not None:
            # Config-level counts
            config_tp += len(cm.matched_pairs)
            config_target += len(cm.matched_pairs) + len(cm.unmatched_target)
            config_extracted += len(cm.matched_pairs) + len(cm.unmatched_extracted)

            # Config field values from matched pairs
            for idx, (t_cfg, e_cfg, _score) in enumerate(cm.matched_pairs):
                vcr = _compare_config_field_values(t_cfg, e_cfg, cm.matched_pairs)
                val_tp += vcr.tp
                val_target += vcr.target_count
                val_extracted += vcr.extracted_count

                # Nested measurement values from matched config pairs
                nested_meas = cm.nested_measurement_results[idx]
                val_tp, val_target, val_extracted = _accumulate_measurement_values(
                    nested_meas, val_tp, val_target, val_extracted
                )

            # Unmatched config fields and measurements count as FN/FP
            for cfg in cm.unmatched_target:
                val_target += _count_config_field_values(cfg)
                for item in _extract_config_comparable_items(cfg):
                    val_target += _count_item_values(item)

            for cfg in cm.unmatched_extracted:
                val_extracted += _count_config_field_values(cfg)
                for item in _extract_config_comparable_items(cfg):
                    val_extracted += _count_item_values(item)

        # -- Process events --
        alignment = match.process_alignment
        if alignment is not None:
            n_matched = len(alignment.matched_pairs)
            proc_tp += n_matched
            proc_target += n_matched + len(alignment.unmatched_target)
            proc_extracted += n_matched + len(alignment.unmatched_extracted)

            # Process event values
            for t_evt, e_evt in alignment.matched_pairs:
                vcr = _compare_process_event_values(t_evt, e_evt)
                val_tp += vcr.tp
                val_target += vcr.target_count
                val_extracted += vcr.extracted_count

            for t_evt in alignment.unmatched_target:
                val_target += _count_process_event_values(t_evt)

            for e_evt in alignment.unmatched_extracted:
                val_extracted += _count_process_event_values(e_evt)

    # Values from unmatched materials (measurement + config values)
    for m in result.unmatched_target_materials:
        for item in _extract_comparable_items(m):
            val_target += _count_item_values(item)
        for cfg in _extract_configurations(m):
            config_target += 1
            val_target += _count_config_field_values(cfg)
            for item in _extract_config_comparable_items(cfg):
                val_target += _count_item_values(item)

    for m in result.unmatched_extracted_materials:
        for item in _extract_comparable_items(m):
            val_extracted += _count_item_values(item)
        for cfg in _extract_configurations(m):
            config_extracted += 1
            val_extracted += _count_config_field_values(cfg)
            for item in _extract_config_comparable_items(cfg):
                val_extracted += _count_item_values(item)

    return MultiLevelMetrics(
        value_tp=val_tp,
        value_target=val_target,
        value_extracted=val_extracted,
        measurement_tp=meas_tp,
        measurement_target=meas_target,
        measurement_extracted=meas_extracted,
        config_tp=config_tp,
        config_target=config_target,
        config_extracted=config_extracted,
        process_tp=proc_tp,
        process_target=proc_target,
        process_extracted=proc_extracted,
        material_tp=material_tp,
        material_target=material_target,
        material_extracted=material_extracted,
    )
