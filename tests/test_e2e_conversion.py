"""
End-to-end tests for ZWO to FIT file conversion.

This module contains comprehensive integration tests that validate the entire
workflow from parsing ZWO files to writing valid FIT files.
"""

import pytest
import struct
import os
from pathlib import Path

from zwo_parser import parse_zwo_to_workout
from fit_writer import FITFileWriter
from zwift2fit import convert_zwo_to_fit, create_fit_file


class TestEndToEndConversion:
    """Test complete ZWO to FIT conversion workflow"""

    def test_basic_workout_conversion(self, tmp_path):
        """Test conversion of basic workout using test_basic.zwo fixture"""
        # Use existing test_basic.zwo fixture
        test_dir = Path(__file__).parent
        zwo_path = test_dir / "test_basic.zwo"
        fit_path = tmp_path / "basic_workout.fit"

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
        assert workout.name == "Basic Test Workout"
        assert len(workout.segments) == 3

        # Check segments
        assert workout.segments[0].type == "warmup"
        assert workout.segments[0].duration == 300
        assert workout.segments[1].type == "steady"
        assert workout.segments[1].duration == 600
        assert workout.segments[2].type == "cooldown"
        assert workout.segments[2].duration == 180

    def test_interval_workout_conversion(self, tmp_path):
        """Test conversion of workout with intervals using test_intervals.zwo fixture"""
        # Use existing test_intervals.zwo fixture
        test_dir = Path(__file__).parent
        zwo_path = test_dir / "test_intervals.zwo"
        fit_path = tmp_path / "interval_workout.fit"

        # Convert with custom FTP
        result = convert_zwo_to_fit(str(zwo_path), str(fit_path), ftp=300)

        assert result is True
        assert fit_path.exists()

        # Verify the workout structure
        workout = parse_zwo_to_workout(str(zwo_path))
        assert workout.name == "Interval Test Workout"
        # warmup + 3*2 intervals + steady + 5*2 intervals + cooldown = 1 + 6 + 1 + 10 + 1 = 19
        assert len(workout.segments) == 19

        # Check interval pattern
        assert workout.segments[0].type == "warmup"
        assert workout.segments[1].type == "interval_work"
        assert workout.segments[1].power == 1.2
        assert workout.segments[2].type == "interval_rest"
        assert workout.segments[2].power == 0.4
        assert workout.segments[-1].type == "cooldown"

    def test_complex_workout_conversion(self, tmp_path):
        """Test conversion of complex workout using max-oclock.zwo fixture"""
        # Use existing 1-max-oclock.zwo fixture which has multiple interval blocks
        project_root = Path(__file__).parent.parent
        zwo_path = project_root / "1-max-oclock.zwo"
        fit_path = tmp_path / "complex_workout.fit"

        result = convert_zwo_to_fit(str(zwo_path), str(fit_path), ftp=280)

        assert result is True
        assert fit_path.exists()

        # Verify complex structure
        workout = parse_zwo_to_workout(str(zwo_path))
        assert workout.name == "1 Max Oclock"

        # This workout has many segments: warmup + steady states + 3 interval blocks
        # warmup(1) + steady(4) + intervals(8*2=16) + steady(1) + intervals(8*2=16) + steady(1) + intervals(8*2=16) + steady(1) = 56
        expected_segments = 56
        assert len(workout.segments) == expected_segments

        # Verify file size is appropriate for complex workout
        file_size = fit_path.stat().st_size
        assert file_size > 500  # Should be substantial for many segments

    def test_minimal_workout_conversion(self, tmp_path):
        """Test conversion of minimal workout using test_minimal.zwo fixture"""
        # Use existing test_minimal.zwo fixture
        test_dir = Path(__file__).parent
        zwo_path = test_dir / "test_minimal.zwo"
        fit_path = tmp_path / "minimal_workout.fit"

        result = convert_zwo_to_fit(str(zwo_path), str(fit_path))

        assert result is True
        assert fit_path.exists()

        workout = parse_zwo_to_workout(str(zwo_path))
        assert len(workout.segments) == 1
        assert workout.segments[0].type == "steady"
        assert workout.segments[0].duration == 1800
        assert workout.segments[0].power == 0.65

    def test_fit_file_structure_validation(self, tmp_path):
        """Test that generated FIT file has correct internal structure"""
        # Use existing test_basic.zwo fixture
        test_dir = Path(__file__).parent
        zwo_path = test_dir / "test_basic.zwo"
        fit_path = tmp_path / "structure_test.fit"

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
        # Use existing test_minimal.zwo fixture
        test_dir = Path(__file__).parent
        zwo_path = test_dir / "test_minimal.zwo"
        fit_path_250 = tmp_path / "ftp_250.fit"
        fit_path_300 = tmp_path / "ftp_300.fit"

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
        """Test handling of workout with no segments using test_empty.zwo fixture"""
        # Use existing test_empty.zwo fixture
        test_dir = Path(__file__).parent
        zwo_path = test_dir / "test_empty.zwo"
        fit_path = tmp_path / "empty_workout.fit"

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
        # Use existing test_basic.zwo fixture
        test_dir = Path(__file__).parent
        zwo_path = test_dir / "test_basic.zwo"
        fit_path = tmp_path / "direct_api_test.fit"

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

        # Use different existing fixtures for multiple conversions
        test_dir = Path(__file__).parent
        fixtures = ["test_basic.zwo", "test_minimal.zwo", "test_intervals.zwo"]
        
        for i, fixture_name in enumerate(fixtures):
            zwo_path = test_dir / fixture_name
            fit_path = tmp_path / f"workout_{i}.fit"

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

    def test_real_world_zwo_file(self, tmp_path):
        """Test conversion of real-world ZWO file using max-oclock fixture"""
        # Use the real Zwift workout file
        project_root = Path(__file__).parent.parent
        zwo_path = project_root / "1-max-oclock.zwo"
        fit_path = tmp_path / "max_oclock_test.fit"

        # Convert using the conversion function
        result = convert_zwo_to_fit(str(zwo_path), str(fit_path), ftp=280)

        # Should succeed with real workout
        assert result is True
        assert fit_path.exists()

        # Verify the converted file has valid structure
        with open(fit_path, "rb") as f:
            header = f.read(14)
            assert header[8:12] == b".FIT"

        # Verify the original file could be parsed
        workout = parse_zwo_to_workout(str(zwo_path))
        assert len(workout.segments) > 0
        assert workout.name == "1 Max Oclock"


if __name__ == "__main__":
    pytest.main([__file__])
