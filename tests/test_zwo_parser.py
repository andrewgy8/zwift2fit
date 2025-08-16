"""
Tests for the zwo_parser module.

This module contains comprehensive tests for ZWO file parsing functionality,
including testing of individual functions and edge cases.
"""

import pytest
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Add parent directory to path to import the module
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from zwo_parser import (
    WorkoutSegment,
    Workout,
    parse_zwo_to_workout,
    parse_zwo_to_segments,
    _get_text_or_default,
    _parse_warmup,
    _parse_steady_state,
    _parse_cooldown,
    _parse_intervals_t,
    _parse_workout_elements,
)


class TestWorkoutSegment:
    """Test the WorkoutSegment dataclass"""

    def test_basic_segment_creation(self):
        """Test creating a basic workout segment"""
        segment = WorkoutSegment(type="steady", duration=600, power=0.8)
        assert segment.type == "steady"
        assert segment.duration == 600
        assert segment.power == 0.8
        assert segment.power_start is None
        assert segment.power_end is None
        assert segment.repeat_count is None

    def test_warmup_segment_creation(self):
        """Test creating a warmup segment with power range"""
        segment = WorkoutSegment(
            type="warmup", duration=300, power_start=0.4, power_end=0.7
        )
        assert segment.type == "warmup"
        assert segment.duration == 300
        assert segment.power_start == 0.4
        assert segment.power_end == 0.7
        assert segment.power is None


class TestWorkout:
    """Test the Workout dataclass"""

    def test_basic_workout_creation(self):
        """Test creating a basic workout"""
        segments = [
            WorkoutSegment(type="warmup", duration=300, power_start=0.4, power_end=0.7),
            WorkoutSegment(type="steady", duration=600, power=0.8),
            WorkoutSegment(
                type="cooldown", duration=180, power_start=0.6, power_end=0.3
            ),
        ]
        workout = Workout(
            name="Test Workout", description="Test Description", segments=segments
        )

        assert workout.name == "Test Workout"
        assert workout.description == "Test Description"
        assert len(workout.segments) == 3
        assert workout.total_duration == 1080  # 300 + 600 + 180
        assert workout.segment_count == 3

    def test_empty_workout(self):
        """Test workout with no segments"""
        workout = Workout(name="Empty", description="", segments=[])
        assert workout.total_duration == 0
        assert workout.segment_count == 0


class TestUtilityFunctions:
    """Test utility functions"""

    def test_get_text_or_default_with_text(self):
        """Test _get_text_or_default with element containing text"""
        element = ET.Element("test")
        element.text = "Hello World"
        result = _get_text_or_default(element, "default")
        assert result == "Hello World"

    def test_get_text_or_default_without_text(self):
        """Test _get_text_or_default with element without text"""
        element = ET.Element("test")
        result = _get_text_or_default(element, "default")
        assert result == "default"

    def test_get_text_or_default_with_none(self):
        """Test _get_text_or_default with None element"""
        result = _get_text_or_default(None, "default")
        assert result == "default"


class TestElementParsing:
    """Test parsing of individual XML elements"""

    def test_parse_warmup(self):
        """Test parsing of Warmup element"""
        element = ET.Element("Warmup")
        element.set("Duration", "300")
        element.set("PowerLow", "0.4")
        element.set("PowerHigh", "0.7")

        segment = _parse_warmup(element)
        assert segment.type == "warmup"
        assert segment.duration == 300
        assert segment.power_start == 0.4
        assert segment.power_end == 0.7
        assert segment.power is None

    def test_parse_warmup_with_defaults(self):
        """Test parsing of Warmup element with missing attributes"""
        element = ET.Element("Warmup")

        segment = _parse_warmup(element)
        assert segment.type == "warmup"
        assert segment.duration == 0
        assert segment.power_start == 0.5
        assert segment.power_end == 0.75

    def test_parse_steady_state(self):
        """Test parsing of SteadyState element"""
        element = ET.Element("SteadyState")
        element.set("Duration", "600")
        element.set("Power", "0.8")

        segment = _parse_steady_state(element)
        assert segment.type == "steady"
        assert segment.duration == 600
        assert segment.power == 0.8
        assert segment.power_start is None
        assert segment.power_end is None

    def test_parse_steady_state_with_defaults(self):
        """Test parsing of SteadyState element with missing attributes"""
        element = ET.Element("SteadyState")

        segment = _parse_steady_state(element)
        assert segment.type == "steady"
        assert segment.duration == 0
        assert segment.power == 0.5

    def test_parse_cooldown(self):
        """Test parsing of Cooldown element"""
        element = ET.Element("Cooldown")
        element.set("Duration", "180")
        element.set("PowerLow", "0.6")
        element.set("PowerHigh", "0.3")

        segment = _parse_cooldown(element)
        assert segment.type == "cooldown"
        assert segment.duration == 180
        assert segment.power_start == 0.6
        assert segment.power_end == 0.3
        assert segment.power is None

    def test_parse_intervals_t(self):
        """Test parsing of IntervalsT element"""
        element = ET.Element("IntervalsT")
        element.set("Repeat", "3")
        element.set("OnDuration", "120")
        element.set("OffDuration", "60")
        element.set("OnPower", "1.2")
        element.set("OffPower", "0.4")

        segments = _parse_intervals_t(element)

        # Should create 3 work intervals and 3 rest intervals (rest after each including last)
        assert len(segments) == 6

        # Check work intervals
        work_segments = [s for s in segments if s.type == "interval_work"]
        assert len(work_segments) == 3
        for segment in work_segments:
            assert segment.duration == 120
            assert segment.power == 1.2

        # Check rest intervals
        rest_segments = [s for s in segments if s.type == "interval_rest"]
        assert len(rest_segments) == 3
        for segment in rest_segments:
            assert segment.duration == 60
            assert segment.power == 0.4

    def test_parse_intervals_t_with_zero_off_duration(self):
        """Test parsing of IntervalsT element with zero off duration"""
        element = ET.Element("IntervalsT")
        element.set("Repeat", "2")
        element.set("OnDuration", "60")
        element.set("OffDuration", "0")
        element.set("OnPower", "1.0")
        element.set("OffPower", "0.5")

        segments = _parse_intervals_t(element)

        # Should create 2 work intervals and 1 rest interval (no rest after last work when off_duration=0)
        assert len(segments) == 3
        work_segments = [s for s in segments if s.type == "interval_work"]
        rest_segments = [s for s in segments if s.type == "interval_rest"]
        assert len(work_segments) == 2
        assert len(rest_segments) == 1
        assert all(s.duration == 0 for s in rest_segments)

    def test_parse_workout_elements_mixed(self):
        """Test parsing of workout elements with mixed types"""
        # Create a mock workout root element
        root = ET.Element("workout_file")
        workout = ET.SubElement(root, "workout")

        # Add various element types
        warmup = ET.SubElement(workout, "Warmup")
        warmup.set("Duration", "300")
        warmup.set("PowerLow", "0.5")
        warmup.set("PowerHigh", "0.75")

        steady = ET.SubElement(workout, "SteadyState")
        steady.set("Duration", "600")
        steady.set("Power", "0.8")

        intervals = ET.SubElement(workout, "IntervalsT")
        intervals.set("Repeat", "2")
        intervals.set("OnDuration", "60")
        intervals.set("OffDuration", "30")
        intervals.set("OnPower", "1.2")
        intervals.set("OffPower", "0.4")

        cooldown = ET.SubElement(workout, "Cooldown")
        cooldown.set("Duration", "180")
        cooldown.set("PowerLow", "0.6")
        cooldown.set("PowerHigh", "0.3")

        segments = _parse_workout_elements(root)

        # Should have: warmup + steady + 2*(work+rest) + cooldown = 7 segments
        assert len(segments) == 7

        # Check order and types
        assert segments[0].type == "warmup"
        assert segments[1].type == "steady"
        assert segments[2].type == "interval_work"
        assert segments[3].type == "interval_rest"
        assert segments[4].type == "interval_work"
        assert segments[5].type == "interval_rest"
        assert segments[6].type == "cooldown"

        # Check some specific values
        assert segments[0].duration == 300
        assert segments[1].power == 0.8
        assert segments[2].power == 1.2
        assert segments[3].power == 0.4

    def test_parse_workout_elements_empty_workout(self):
        """Test parsing of empty workout element"""
        root = ET.Element("workout_file")
        ET.SubElement(root, "workout")
        # Empty workout element

        segments = _parse_workout_elements(root)
        assert len(segments) == 0

    def test_parse_workout_elements_no_workout(self):
        """Test parsing when no workout element exists"""
        root = ET.Element("workout_file")
        # No workout element

        segments = _parse_workout_elements(root)
        assert len(segments) == 0

    def test_parse_workout_elements_unknown_element(self):
        """Test parsing with unknown element types"""
        root = ET.Element("workout_file")
        workout = ET.SubElement(root, "workout")

        # Add known element
        steady = ET.SubElement(workout, "SteadyState")
        steady.set("Duration", "600")
        steady.set("Power", "0.8")

        # Add unknown element (should be ignored)
        unknown = ET.SubElement(workout, "UnknownElement")
        unknown.set("Duration", "300")
        unknown.set("Power", "1.0")

        # Add another known element
        warmup = ET.SubElement(workout, "Warmup")
        warmup.set("Duration", "180")
        warmup.set("PowerLow", "0.4")
        warmup.set("PowerHigh", "0.7")

        segments = _parse_workout_elements(root)

        # Should only parse the known elements
        assert len(segments) == 2
        assert segments[0].type == "steady"
        assert segments[1].type == "warmup"


class TestFileBasedParsing:
    """Test parsing of actual ZWO files"""

    def test_parse_basic_workout(self, test_files_dir):
        """Test parsing of basic workout file"""
        file_path = test_files_dir / "test_basic.zwo"
        workout = parse_zwo_to_workout(str(file_path))

        assert workout.name == "Basic Test Workout"
        assert workout.description == "A simple workout for testing basic functionality"
        assert len(workout.segments) == 3

        # Check warmup
        warmup = workout.segments[0]
        assert warmup.type == "warmup"
        assert warmup.duration == 300
        assert warmup.power_start == 0.4
        assert warmup.power_end == 0.7

        # Check steady state
        steady = workout.segments[1]
        assert steady.type == "steady"
        assert steady.duration == 600
        assert steady.power == 0.8

        # Check cooldown
        cooldown = workout.segments[2]
        assert cooldown.type == "cooldown"
        assert cooldown.duration == 180
        assert cooldown.power_start == 0.6
        assert cooldown.power_end == 0.3

    def test_parse_interval_workout(self, test_files_dir):
        """Test parsing of workout with intervals"""
        file_path = test_files_dir / "test_intervals.zwo"
        workout = parse_zwo_to_workout(str(file_path))

        assert workout.name == "Interval Test Workout"
        # warmup + 3*2 intervals + steady + 5*2 intervals + cooldown = 1 + 6 + 1 + 10 + 1 = 19
        assert len(workout.segments) == 19

        # Check that intervals are properly parsed
        interval_work_segments = [
            s for s in workout.segments if s.type == "interval_work"
        ]
        interval_rest_segments = [
            s for s in workout.segments if s.type == "interval_rest"
        ]

        assert len(interval_work_segments) == 8  # 3 + 5
        assert len(interval_rest_segments) == 8  # 3 + 5

    def test_parse_minimal_workout(self, test_files_dir):
        """Test parsing of minimal workout file"""
        file_path = test_files_dir / "test_minimal.zwo"
        workout = parse_zwo_to_workout(str(file_path))

        assert workout.name == "Minimal Workout"
        assert workout.description == ""  # Should default to empty string
        assert len(workout.segments) == 1

        segment = workout.segments[0]
        assert segment.type == "steady"
        assert segment.duration == 1800
        assert segment.power == 0.65

    def test_parse_empty_workout(self, test_files_dir):
        """Test parsing of workout with no segments"""
        file_path = test_files_dir / "test_empty.zwo"
        workout = parse_zwo_to_workout(str(file_path))

        assert workout.name == "Empty Workout"
        assert workout.description == "Workout with no segments"
        assert len(workout.segments) == 0
        assert workout.total_duration == 0

    def test_parse_zwo_to_segments(self, test_files_dir):
        """Test parse_zwo_to_segments function"""
        file_path = test_files_dir / "test_basic.zwo"
        segments = parse_zwo_to_segments(str(file_path))

        assert len(segments) == 3
        assert all(isinstance(s, WorkoutSegment) for s in segments)
        assert segments[0].type == "warmup"
        assert segments[1].type == "steady"
        assert segments[2].type == "cooldown"


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_file_not_found(self):
        """Test handling of non-existent file"""
        with pytest.raises(FileNotFoundError):
            parse_zwo_to_workout("non_existent_file.zwo")

    def test_invalid_xml(self):
        """Test handling of invalid XML"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".zwo", delete=False) as f:
            f.write("This is not valid XML")
            f.flush()

            try:
                with pytest.raises(ET.ParseError):
                    parse_zwo_to_workout(f.name)
            finally:
                os.unlink(f.name)

    def test_malformed_zwo(self):
        """Test handling of malformed ZWO file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".zwo", delete=False) as f:
            f.write('<?xml version="1.0"?><invalid_root></invalid_root>')
            f.flush()

            try:
                # Should not raise an error, but return workout with defaults
                workout = parse_zwo_to_workout(f.name)
                assert workout.name == "Workout"  # Default name
                assert workout.description == ""  # Default description
                assert len(workout.segments) == 0  # No segments
            finally:
                os.unlink(f.name)

    def test_missing_workout_element(self):
        """Test ZWO file without workout element"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".zwo", delete=False) as f:
            f.write(
                '<?xml version="1.0"?><workout_file><name>Test</name></workout_file>'
            )
            f.flush()

            try:
                workout = parse_zwo_to_workout(f.name)
                assert workout.name == "Test"
                assert len(workout.segments) == 0
            finally:
                os.unlink(f.name)


class TestIntegration:
    """Integration tests"""

    def test_round_trip_compatibility(self, test_files_dir):
        """Test that parsing produces consistent results"""
        file_path = test_files_dir / "test_basic.zwo"

        # Parse using different functions
        workout = parse_zwo_to_workout(str(file_path))
        segments = parse_zwo_to_segments(str(file_path))

        # Check consistency between the two functions
        assert len(workout.segments) == len(segments)
        assert workout.name == "Basic Test Workout"
        assert workout.description == "A simple workout for testing basic functionality"

        # Check segment consistency
        for i, (ws, s) in enumerate(zip(workout.segments, segments)):
            assert ws.type == s.type
            assert ws.duration == s.duration
            assert ws.power == s.power
            assert ws.power_start == s.power_start
            assert ws.power_end == s.power_end

    def test_performance_with_large_intervals(self):
        """Test performance with large number of intervals"""
        # Create a workout with many intervals
        with tempfile.NamedTemporaryFile(mode="w", suffix=".zwo", delete=False) as f:
            f.write('<?xml version="1.0"?>')
            f.write("<workout_file>")
            f.write("<name>Large Interval Test</name>")
            f.write("<workout>")
            f.write(
                '<IntervalsT Repeat="100" OnDuration="10" OffDuration="5" OnPower="1.0" OffPower="0.5"/>'
            )
            f.write("</workout>")
            f.write("</workout_file>")
            f.flush()

            try:
                import time

                start_time = time.time()
                workout = parse_zwo_to_workout(f.name)
                parse_time = time.time() - start_time

                # Should parse quickly (under 1 second) and create correct number of segments
                assert parse_time < 1.0
                assert len(workout.segments) == 200  # 100 work + 100 rest
            finally:
                os.unlink(f.name)


if __name__ == "__main__":
    pytest.main([__file__])
