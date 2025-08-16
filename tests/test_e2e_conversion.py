"""
End-to-end tests for ZWO to FIT file conversion.

This module contains comprehensive integration tests that validate the entire
workflow from parsing ZWO files to writing valid FIT files.
"""

import pytest
import struct
from pathlib import Path

# Add parent directory to path to import the modules
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from zwo_parser import parse_zwo_to_workout
from fit_writer import FITFileWriter
from zwift2fit import convert_zwo_to_fit, create_fit_file


class TestEndToEndConversion:
    """Test complete ZWO to FIT conversion workflow"""

    def test_simple_workout_conversion(self, tmp_path):
        """Test conversion of a simple workout with basic segments"""
        # Create a simple ZWO file
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Simple Test Workout</name>
    <workout>
        <Warmup Duration="300" PowerLow="0.5" PowerHigh="0.75"/>
        <SteadyState Duration="600" Power="0.8"/>
        <Cooldown Duration="300" PowerHigh="0.6" PowerLow="0.4"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "simple_workout.zwo"
        fit_path = tmp_path / "simple_workout.fit"

        # Write ZWO file
        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        # Convert to FIT
        result = convert_zwo_to_fit(str(zwo_path), str(fit_path), ftp=250)

        # Verify conversion succeeded
        assert result is True
        assert fit_path.exists()

        # Verify FIT file structure
        with open(fit_path, "rb") as f:
            # Check FIT file header
            header = f.read(14)
            assert header[0] == 14  # header_size
            assert header[1] == 32  # protocol_version
            assert header[8:12] == b".FIT"  # data_type

            # Check file has reasonable size
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            assert file_size > 100  # Should have substantial content

        # Verify original workout was parsed correctly
        workout = parse_zwo_to_workout(str(zwo_path))
        assert workout.name == "Simple Test Workout"
        assert len(workout.segments) == 3

        # Check segments
        assert workout.segments[0].type == "warmup"
        assert workout.segments[0].duration == 300
        assert workout.segments[1].type == "steady"
        assert workout.segments[1].duration == 600
        assert workout.segments[2].type == "cooldown"
        assert workout.segments[2].duration == 300

    def test_interval_workout_conversion(self, tmp_path):
        """Test conversion of workout with intervals"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Interval Training</name>
    <workout>
        <Warmup Duration="600" PowerLow="0.5" PowerHigh="0.75"/>
        <IntervalsT Repeat="3" OnDuration="240" OffDuration="120" OnPower="1.2" OffPower="0.5"/>
        <Cooldown Duration="600" PowerHigh="0.7" PowerLow="0.4"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "interval_workout.zwo"
        fit_path = tmp_path / "interval_workout.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        # Convert with custom FTP
        result = convert_zwo_to_fit(str(zwo_path), str(fit_path), ftp=300)

        assert result is True
        assert fit_path.exists()

        # Verify the workout structure
        workout = parse_zwo_to_workout(str(zwo_path))
        assert workout.name == "Interval Training"
        # Should have warmup + 3 work intervals + 3 rest intervals + cooldown = 8 segments
        assert len(workout.segments) == 8

        # Check interval pattern
        assert workout.segments[0].type == "warmup"
        assert workout.segments[1].type == "interval_work"
        assert workout.segments[1].power == 1.2
        assert workout.segments[2].type == "interval_rest"
        assert workout.segments[2].power == 0.5
        assert workout.segments[-1].type == "cooldown"

    def test_complex_workout_conversion(self, tmp_path):
        """Test conversion of complex workout with multiple segment types"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Complex Training Session</name>
    <workout>
        <Warmup Duration="600" PowerLow="0.4" PowerHigh="0.7"/>
        <SteadyState Duration="300" Power="0.6"/>
        <IntervalsT Repeat="2" OnDuration="180" OffDuration="60" OnPower="1.4" OffPower="0.3"/>
        <SteadyState Duration="240" Power="0.85"/>
        <IntervalsT Repeat="1" OnDuration="300" OffDuration="180" OnPower="1.1" OffPower="0.4"/>
        <Cooldown Duration="600" PowerHigh="0.6" PowerLow="0.3"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "complex_workout.zwo"
        fit_path = tmp_path / "complex_workout.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        result = convert_zwo_to_fit(str(zwo_path), str(fit_path), ftp=280)

        assert result is True
        assert fit_path.exists()

        # Verify complex structure
        workout = parse_zwo_to_workout(str(zwo_path))
        assert workout.name == "Complex Training Session"

        # Count expected segments:
        # Warmup(1) + Steady(1) + Intervals(2x2=4) + Steady(1) + Intervals(1x2=2) + Cooldown(1) = 10
        expected_segments = 10
        assert len(workout.segments) == expected_segments

        # Verify file size is appropriate for complex workout
        file_size = fit_path.stat().st_size
        assert file_size > 300  # Should be substantial for 10 segments

    def test_minimal_workout_conversion(self, tmp_path):
        """Test conversion of minimal workout with single segment"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Minimal</name>
    <workout>
        <SteadyState Duration="1200" Power="0.75"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "minimal_workout.zwo"
        fit_path = tmp_path / "minimal_workout.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        result = convert_zwo_to_fit(str(zwo_path), str(fit_path))

        assert result is True
        assert fit_path.exists()

        workout = parse_zwo_to_workout(str(zwo_path))
        assert len(workout.segments) == 1
        assert workout.segments[0].type == "steady"
        assert workout.segments[0].duration == 1200
        assert workout.segments[0].power == 0.75

    def test_fit_file_structure_validation(self, tmp_path):
        """Test that generated FIT file has correct internal structure"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Structure Test</name>
    <workout>
        <Warmup Duration="300" PowerLow="0.5" PowerHigh="0.75"/>
        <SteadyState Duration="600" Power="0.8"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "structure_test.zwo"
        fit_path = tmp_path / "structure_test.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        convert_zwo_to_fit(str(zwo_path), str(fit_path), ftp=250)

        # Read and validate FIT file structure in detail
        with open(fit_path, "rb") as f:
            # Read header
            header = f.read(14)
            assert len(header) == 14

            # Extract data size from header
            data_size = struct.unpack("<I", header[4:8])[0]
            assert data_size > 0

            # Read data section
            data = f.read(data_size)
            assert len(data) == data_size

            # Read CRC
            crc_bytes = f.read(2)
            assert len(crc_bytes) == 2

            # Verify we've read the entire file
            remaining = f.read()
            assert len(remaining) == 0

        # Verify total file size
        expected_size = 14 + data_size + 2  # header + data + crc
        actual_size = fit_path.stat().st_size
        assert actual_size == expected_size

    def test_different_ftp_values(self, tmp_path):
        """Test conversion with different FTP values produces different results"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>FTP Test</name>
    <workout>
        <SteadyState Duration="600" Power="1.0"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "ftp_test.zwo"
        fit_path_250 = tmp_path / "ftp_250.fit"
        fit_path_300 = tmp_path / "ftp_300.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        # Convert with different FTP values
        convert_zwo_to_fit(str(zwo_path), str(fit_path_250), ftp=250)
        convert_zwo_to_fit(str(zwo_path), str(fit_path_300), ftp=300)

        # Files should exist but have different content
        assert fit_path_250.exists()
        assert fit_path_300.exists()

        # Read both files
        with open(fit_path_250, "rb") as f:
            content_250 = f.read()
        with open(fit_path_300, "rb") as f:
            content_300 = f.read()

        # Content should be different (different power targets)
        assert content_250 != content_300

        # But headers should be the same structure
        assert content_250[:12] == content_300[:12]  # Same header structure

    def test_unicode_workout_names(self, tmp_path):
        """Test conversion with Unicode characters in workout names"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>测试 Тест Épreuve</name>
    <workout>
        <SteadyState Duration="600" Power="0.8"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "unicode_test.zwo"
        fit_path = tmp_path / "unicode_test.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        result = convert_zwo_to_fit(str(zwo_path), str(fit_path))

        assert result is True
        assert fit_path.exists()

        # Verify workout name was parsed correctly
        workout = parse_zwo_to_workout(str(zwo_path))
        assert "测试 Тест Épreuve" in workout.name


class TestErrorHandling:
    """Test error handling in end-to-end conversion"""

    def test_invalid_zwo_file(self, tmp_path):
        """Test handling of invalid ZWO file"""
        zwo_path = tmp_path / "invalid.zwo"
        fit_path = tmp_path / "invalid.fit"

        # Write invalid XML
        with open(zwo_path, "w") as f:
            f.write("This is not valid XML")

        result = convert_zwo_to_fit(str(zwo_path), str(fit_path))

        # Conversion should fail gracefully
        assert result is False
        assert not fit_path.exists()

    def test_missing_zwo_file(self, tmp_path):
        """Test handling of missing ZWO file"""
        zwo_path = tmp_path / "nonexistent.zwo"
        fit_path = tmp_path / "output.fit"

        result = convert_zwo_to_fit(str(zwo_path), str(fit_path))

        assert result is False
        assert not fit_path.exists()

    def test_empty_workout(self, tmp_path):
        """Test handling of workout with no segments"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Empty Workout</name>
    <workout>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "empty_workout.zwo"
        fit_path = tmp_path / "empty_workout.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        result = convert_zwo_to_fit(str(zwo_path), str(fit_path))

        # Should fail because no segments to convert
        assert result is False
        assert not fit_path.exists()

    def test_invalid_output_directory(self, tmp_path):
        """Test handling of invalid output directory"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Test</name>
    <workout>
        <SteadyState Duration="600" Power="0.8"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "test.zwo"
        fit_path = "/invalid/path/that/does/not/exist/output.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        result = convert_zwo_to_fit(str(zwo_path), fit_path)

        assert result is False


class TestDirectAPIUsage:
    """Test direct usage of the FITFileWriter API"""

    def test_direct_fit_writer_usage(self, tmp_path):
        """Test using FITFileWriter directly with parsed segments"""
        zwo_content = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Direct API Test</name>
    <workout>
        <Warmup Duration="300" PowerLow="0.5" PowerHigh="0.75"/>
        <SteadyState Duration="600" Power="0.8"/>
        <Cooldown Duration="300" PowerHigh="0.6" PowerLow="0.4"/>
    </workout>
</workout_file>"""

        zwo_path = tmp_path / "direct_api_test.zwo"
        fit_path = tmp_path / "direct_api_test.fit"

        with open(zwo_path, "w", encoding="utf-8") as f:
            f.write(zwo_content)

        # Parse ZWO file
        workout = parse_zwo_to_workout(str(zwo_path))

        # Use FITFileWriter directly
        writer = FITFileWriter()
        crc = writer.create_workout_file(
            workout.segments, str(fit_path), workout.name, ftp=275
        )

        # Verify result
        assert isinstance(crc, int)
        assert fit_path.exists()

        # Compare with high-level API result
        fit_path_comparison = tmp_path / "comparison.fit"
        create_fit_file(
            workout.segments, str(fit_path_comparison), workout.name, ftp=275
        )

        # Files should be identical (both use same underlying implementation)
        with open(fit_path, "rb") as f1, open(fit_path_comparison, "rb") as f2:
            content1 = f1.read()
            content2 = f2.read()
            assert content1 == content2

    def test_multiple_conversions_same_writer(self, tmp_path):
        """Test using same FIT writer instance for multiple conversions"""
        writer = FITFileWriter()

        for i in range(3):
            zwo_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Workout {i + 1}</name>
    <workout>
        <SteadyState Duration="{300 * (i + 1)}" Power="{0.7 + i * 0.1}"/>
    </workout>
</workout_file>'''

            zwo_path = tmp_path / f"workout_{i}.zwo"
            fit_path = tmp_path / f"workout_{i}.fit"

            with open(zwo_path, "w", encoding="utf-8") as f:
                f.write(zwo_content)

            # Parse and convert
            workout = parse_zwo_to_workout(str(zwo_path))
            crc = writer.create_workout_file(
                workout.segments, str(fit_path), workout.name, ftp=250
            )

            assert isinstance(crc, int)
            assert fit_path.exists()

            # Verify each file has appropriate content
            file_size = fit_path.stat().st_size
            assert file_size > 50  # Should have reasonable content


class TestIntegrationWithRealFiles:
    """Test integration with actual ZWO files if available"""

    def test_existing_zwo_file_if_present(self, tmp_path):
        """Test conversion of existing ZWO file if one exists in the project"""
        # Look for existing ZWO files in the project
        project_root = Path(__file__).parent.parent
        zwo_files = list(project_root.glob("*.zwo"))

        if not zwo_files:
            pytest.skip("No ZWO files found in project root")

        # Test with the first ZWO file found
        zwo_path = zwo_files[0]
        fit_path = tmp_path / f"{zwo_path.stem}_test.fit"

        # Convert using the conversion function
        result = convert_zwo_to_fit(str(zwo_path), str(fit_path), ftp=280)

        # If the file is valid, conversion should succeed
        if result:
            assert fit_path.exists()

            # Verify the converted file has valid structure
            with open(fit_path, "rb") as f:
                header = f.read(14)
                assert header[8:12] == b".FIT"

            # Verify the original file could be parsed
            workout = parse_zwo_to_workout(str(zwo_path))
            assert len(workout.segments) > 0


if __name__ == "__main__":
    pytest.main([__file__])
