"""Tests for SynthesisGroup dataclass and variable substitution."""

import pytest

from litxbench.core.models import ProcessEvent, Quantity, SynthesisGroup
from litxbench.core.units import Celsius, Hour


class TestFromNameAndEvents:
    """Tests for SynthesisGroup.from_name_and_events()."""

    def test_simple_name_no_variables(self):
        """Test parsing a simple group name without template variables."""
        events = [ProcessEvent(kind="annealing")]
        synth_group = SynthesisGroup.from_name_and_events("annealing", events)

        assert synth_group.name == "annealing"
        assert synth_group.base_name == "annealing"
        assert synth_group.template_vars == set()
        assert synth_group.process_events == events

    def test_single_template_variable(self):
        """Test parsing group name with one template variable."""
        events = [ProcessEvent(kind="annealing")]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp]", events)

        assert synth_group.name == "annealing[Temp]"
        assert synth_group.base_name == "annealing"
        assert synth_group.template_vars == {"Temp"}
        assert synth_group.process_events == events

    def test_multiple_template_variables(self):
        """Test parsing group name with multiple template variables."""
        events = [ProcessEvent(kind="annealing")]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp,Speed]", events)

        assert synth_group.name == "annealing[Temp,Speed]"
        assert synth_group.base_name == "annealing"
        assert synth_group.template_vars == {"Temp", "Speed"}
        assert synth_group.process_events == events

    def test_whitespace_in_template_variables(self):
        """Test parsing handles whitespace around template variables."""
        events = [ProcessEvent(kind="annealing")]
        synth_group = SynthesisGroup.from_name_and_events("annealing[ Temp , Speed ]", events)

        assert synth_group.base_name == "annealing"
        assert synth_group.template_vars == {"Temp", "Speed"}



class TestSubstituteVariables:
    """Tests for SynthesisGroup.substitute_variables()."""

    def test_substitute_in_quantity_value(self):
        """Test substituting template variable in Quantity value."""
        events = [ProcessEvent(kind="annealing", temperature=Quantity(value="[Temp]", unit=Celsius))]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp]", events)

        substituted = synth_group.substitute_variables({"Temp": "660"})

        assert len(substituted) == 1
        assert substituted[0].temperature.value == "660"
        assert substituted[0].temperature.unit == Celsius
        # Original should be unchanged
        assert events[0].temperature.value == "[Temp]"

    def test_substitute_in_description(self):
        """Test substituting template variable in description string."""
        events = [ProcessEvent(kind="annealing", description="Heated to [Temp] degrees")]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp]", events)

        substituted = synth_group.substitute_variables({"Temp": "660"})

        assert len(substituted) == 1
        assert substituted[0].description == "Heated to 660 degrees"
        # Original should be unchanged
        assert events[0].description == "Heated to [Temp] degrees"

    def test_substitute_multiple_variables(self):
        """Test substituting multiple template variables."""
        events = [
            ProcessEvent(
                kind="annealing",
                temperature=Quantity(value="[Temp]", unit=Celsius),
                description="Annealing at [Speed] rpm",
            )
        ]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp,Speed]", events)

        substituted = synth_group.substitute_variables({"Temp": "660", "Speed": "100"})

        assert len(substituted) == 1
        assert substituted[0].temperature.value == "660"
        assert substituted[0].description == "Annealing at 100 rpm"

    def test_substitute_in_multiple_events(self):
        """Test substituting variables in multiple process events."""
        events = [
            ProcessEvent(kind="heating", temperature=Quantity(value="[Temp]", unit=Celsius)),
            ProcessEvent(kind="holding", temperature=Quantity(value="[Temp]", unit=Celsius)),
        ]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp]", events)

        substituted = synth_group.substitute_variables({"Temp": "660"})

        assert len(substituted) == 2
        assert substituted[0].temperature.value == "660"
        assert substituted[1].temperature.value == "660"

    def test_no_template_variables(self):
        """Test substitution when there are no template variables."""
        events = [ProcessEvent(kind="annealing", temperature=Quantity(value=800, unit=Celsius))]
        synth_group = SynthesisGroup.from_name_and_events("annealing", events)

        substituted = synth_group.substitute_variables({})

        assert len(substituted) == 1
        assert substituted[0].temperature.value == 800

    def test_missing_variable_raises_error(self):
        """Test that missing template variable raises ValueError."""
        events = [ProcessEvent(kind="annealing", temperature=Quantity(value="[Temp]", unit=Celsius))]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp]", events)

        with pytest.raises(ValueError, match="Missing values for template variables"):
            synth_group.substitute_variables({})

    def test_extra_variables_are_ignored(self):
        """Test that extra variables in the dict don't cause errors."""
        events = [ProcessEvent(kind="annealing", temperature=Quantity(value="[Temp]", unit=Celsius))]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp]", events)

        substituted = synth_group.substitute_variables({"Temp": "660", "ExtraVar": "999"})

        assert len(substituted) == 1
        assert substituted[0].temperature.value == "660"

    def test_none_fields_are_preserved(self):
        """Test that None fields remain None after substitution."""
        events = [ProcessEvent(kind="annealing", temperature=Quantity(value="[Temp]", unit=Celsius), description=None)]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp]", events)

        substituted = synth_group.substitute_variables({"Temp": "660"})

        assert substituted[0].description is None

    def test_fields_without_template_are_unchanged(self):
        """Test that fields without template placeholders remain unchanged."""
        events = [
            ProcessEvent(
                kind="annealing",
                temperature=Quantity(value="[Temp]", unit=Celsius),
                duration=Quantity(value=1, unit=Hour),
                source="Methods section",
            )
        ]
        synth_group = SynthesisGroup.from_name_and_events("annealing[Temp]", events)

        substituted = synth_group.substitute_variables({"Temp": "660"})

        assert substituted[0].temperature.value == "660"
        assert substituted[0].duration.value == 1
        assert substituted[0].source == "Methods section"
