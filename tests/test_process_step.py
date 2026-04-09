"""Tests for ProcessStep dataclass and parsers."""

import pytest

from litxbench.core.models import ProcessStep


class TestParseMaterialStep:
    """Tests for ProcessStep.parse_material_step()."""

    def test_parse_simple_step_no_brackets(self):
        """Test parsing a simple step without brackets."""
        step = ProcessStep.parse_material_step("annealing")
        assert step.base_name == "annealing"
        assert step.variables == {}
        assert step.inputs == []

    def test_parse_step_with_single_variable(self):
        """Test parsing a step with one variable assignment."""
        step = ProcessStep.parse_material_step("annealing[Temp=800]")
        assert step.base_name == "annealing"
        assert step.variables == {"Temp": "800"}
        assert step.inputs == []

    def test_parse_step_with_multiple_variables(self):
        """Test parsing a step with multiple variable assignments."""
        step = ProcessStep.parse_material_step("milling[Temp=800,Speed=100]")
        assert step.base_name == "milling"
        assert step.variables == {"Temp": "800", "Speed": "100"}

    def test_parse_step_with_suffix(self):
        """Test parsing a step with a suffix."""
        step = ProcessStep.parse_material_step("annealing[Temp=800]_v2")
        assert step.base_name == "annealing"
        assert step.variables == {"Temp": "800"}

    def test_parse_step_with_suffix_no_variables(self):
        """Test parsing a step with suffix but no variables.

        Note: Without brackets, the suffix is part of the base_name.
        Suffixes are only extracted when they appear after brackets.
        """
        step = ProcessStep.parse_material_step("annealing_v2")
        assert step.base_name == "annealing_v2"
        assert step.variables == {}

    def test_parse_step_with_whitespace_in_variables(self):
        """Test parsing handles whitespace around variables."""
        step = ProcessStep.parse_material_step("milling[ Temp = 800 , Speed = 100 ]")
        assert step.base_name == "milling"
        assert step.variables == {"Temp": "800", "Speed": "100"}

    def test_parse_step_with_complex_suffix(self):
        """Test parsing a step with complex suffix."""
        step = ProcessStep.parse_material_step("annealing[Temp=800]_step_2_v3")
        assert step.base_name == "annealing"
        assert step.variables == {"Temp": "800"}

    def test_parse_step_with_inputs(self):
        """Test parsing a step with explicit inputs."""
        step = ProcessStep.parse_material_step("annealing[Temp=800]", inputs=["base"])
        assert step.base_name == "annealing"
        assert step.variables == {"Temp": "800"}
        assert step.inputs == ["base"]

    def test_parse_step_with_multiple_inputs(self):
        """Test parsing a step with multiple inputs."""
        step = ProcessStep.parse_material_step("mix", inputs=["sample1", "sample2"])
        assert step.base_name == "mix"
        assert step.inputs == ["sample1", "sample2"]


class TestParseProcessString:
    """Tests for ProcessStep.parse_process_string()."""

    def test_single_event_no_inputs_raises_error(self):
        """Test that parsing a single event with no inputs raises ValueError."""
        with pytest.raises(ValueError, match="the first event must have at least one explicit input"):
            ProcessStep.parse_process_string("melting")

    def test_single_event_with_input(self):
        """Test parsing input->event."""
        steps = ProcessStep.parse_process_string("powder->melting")
        assert len(steps) == 1
        assert steps[0].base_name == "melting"
        assert steps[0].inputs == ["powder"]

    def test_two_events_with_input(self):
        """Test parsing input->event->event."""
        steps = ProcessStep.parse_process_string("powder->melting->annealing[Temp=800]")
        assert len(steps) == 2
        assert steps[0].base_name == "melting"
        assert steps[0].inputs == ["powder"]
        assert steps[1].base_name == "annealing"
        assert steps[1].variables == {"Temp": "800"}
        assert steps[1].inputs == []

    def test_multi_input_first_step(self):
        """Test parsing with multiple comma-separated inputs in the first segment."""
        steps = ProcessStep.parse_process_string("sample1,sample2->mix->anneal")
        assert len(steps) == 2
        assert steps[0].base_name == "mix"
        assert steps[0].inputs == ["sample1", "sample2"]
        assert steps[1].base_name == "anneal"
        assert steps[1].inputs == []

    def test_no_explicit_inputs_raises_error(self):
        """Test that parsing without explicit inputs on first event raises ValueError."""
        with pytest.raises(ValueError, match="the first event must have at least one explicit input"):
            ProcessStep.parse_process_string("melting")

    def test_long_chain(self):
        """Test parsing a long chain of events."""
        steps = ProcessStep.parse_process_string(
            "elements->melt->conventionally_cast->homogenization->annealing->preparation"
        )
        assert len(steps) == 5
        assert steps[0].base_name == "melt"
        assert steps[0].inputs == ["elements"]
        assert steps[1].base_name == "conventionally_cast"
        assert steps[1].inputs == []
        assert steps[4].base_name == "preparation"


class TestParseEventName:
    """Tests for ProcessStep.parse_event_name()."""

    def test_parse_simple_event_no_brackets(self):
        """Test parsing a simple event name without brackets."""
        step = ProcessStep.parse_event_name("annealing")
        assert step.base_name == "annealing"
        assert step.variables == {}

    def test_parse_event_with_single_template_var(self):
        """Test parsing an event with one template variable."""
        step = ProcessStep.parse_event_name("annealing[Temp]")
        assert step.base_name == "annealing"
        assert step.variables == {"Temp": ""}

    def test_parse_event_with_multiple_template_vars(self):
        """Test parsing an event with multiple template variables."""
        step = ProcessStep.parse_event_name("milling[Temp,Speed]")
        assert step.base_name == "milling"
        assert step.variables == {"Temp": "", "Speed": ""}

    def test_parse_event_with_suffix(self):
        """Test parsing an event - suffix after brackets is ignored."""
        step = ProcessStep.parse_event_name("annealing[Temp]_v2")
        assert step.base_name == "annealing"
        assert step.variables == {"Temp": ""}

    def test_parse_event_with_suffix_no_template_vars(self):
        """Test parsing an event with suffix but no template variables.

        Note: Without brackets, the suffix is part of the base_name.
        Suffixes are only extracted when they appear after brackets.
        """
        step = ProcessStep.parse_event_name("annealing_v2")
        assert step.base_name == "annealing_v2"
        assert step.variables == {}

    def test_parse_event_with_whitespace_in_template_vars(self):
        """Test parsing handles whitespace around template variables."""
        step = ProcessStep.parse_event_name("milling[ Temp , Speed ]")
        assert step.base_name == "milling"
        assert step.variables == {"Temp": "", "Speed": ""}


class TestToString:
    """Tests for ProcessStep.to_string()."""

    def test_simple_step_no_brackets_to_string(self):
        """Test converting simple step without brackets to string."""
        step = ProcessStep(base_name="annealing", variables={})
        assert step.to_string() == "annealing"

    def test_step_with_single_variable_to_string(self):
        """Test converting step with one variable to string."""
        step = ProcessStep(base_name="annealing", variables={"Temp": "800"})
        assert step.to_string() == "annealing[Temp=800]"

    def test_step_with_multiple_variables_to_string(self):
        """Test converting step with multiple variables to string."""
        # Note: dict order is preserved in Python 3.7+
        step = ProcessStep(base_name="milling", variables={"Temp": "800", "Speed": "100"})
        result = step.to_string()
        # Check that both variables are present (order may vary)
        assert result.startswith("milling[")
        assert "Temp=800" in result
        assert "Speed=100" in result
        assert result.endswith("]")

    def test_step_with_suffix_to_string(self):
        """Test converting step to string."""
        step = ProcessStep(base_name="annealing", variables={"Temp": "800"})
        assert step.to_string() == "annealing[Temp=800]"

    def test_event_with_template_vars_to_string(self):
        """Test converting event with template variables to string."""
        step = ProcessStep(base_name="annealing", variables={"Temp": ""})
        assert step.to_string() == "annealing[Temp]"

    def test_event_with_multiple_template_vars_to_string(self):
        """Test converting event with multiple template variables to string."""
        step = ProcessStep(base_name="milling", variables={"Temp": "", "Speed": ""})
        assert step.to_string() == "milling[Temp,Speed]"


class TestRoundTrip:
    """Tests for round-trip conversion (parse -> to_string -> parse)."""

    def test_material_step_round_trip(self):
        """Test that parsing and converting back gives the same string."""
        original = "annealing[Temp=800]"
        step = ProcessStep.parse_material_step(original)
        result = step.to_string()
        assert result == original

    def test_event_name_round_trip(self):
        """Test that parsing event and converting back gives the same string."""
        original = "annealing[Temp]"
        step = ProcessStep.parse_event_name(original)
        result = step.to_string()
        assert result == original

    def test_simple_step_round_trip(self):
        """Test round trip for simple step without brackets."""
        original = "annealing"
        step = ProcessStep.parse_material_step(original)
        result = step.to_string()
        assert result == original


class TestMultipleBracketGroupValidation:
    def test_rejects_multiple_brackets(self):
        with pytest.raises(ValueError, match="Multiple bracket groups"):
            ProcessStep.parse_material_step("annealing[Temp=950][Time=100]")
