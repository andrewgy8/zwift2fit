"""
Tests for the fit_writer module.

This module contains comprehensive tests for FIT file writing functionality,
including testing of message creation, file structure, and edge cases.
"""

import pytest
import struct
from pathlib import Path

# Add parent directory to path to import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from fit_writer import FITFileWriter


class TestFITFileWriter:
    """Test the FITFileWriter class"""
    
    def test_basic_initialization(self):
        """Test basic initialization of FITFileWriter"""
        writer = FITFileWriter()
        assert writer.data_records == []
        assert writer.local_message_types == {}
        assert writer.next_local_type == 0
    
    def test_clear_functionality(self):
        """Test the clear() method"""
        writer = FITFileWriter()
        writer.add_file_id_message()
        writer.add_workout_message("Test", 1)
        
        # Verify data was added
        assert len(writer.data_records) == 2
        
        # Clear and verify reset
        writer.clear()
        assert writer.data_records == []
        assert writer.local_message_types == {}
        assert writer.next_local_type == 0


class TestMessageCreation:
    """Test message creation methods"""
    
    def test_add_file_id_message(self):
        """Test adding file ID message"""
        writer = FITFileWriter()
        writer.add_file_id_message()
        
        assert len(writer.data_records) == 1
        record = writer.data_records[0]
        assert record['global_type'] == 0  # FILE_ID message type
        
        fields = record['fields']
        assert len(fields) == 4
        assert fields[0] == (0, 'enum', 4)  # type = workout
        assert fields[1] == (1, 'uint16', 1)  # manufacturer = Development
        assert fields[2] == (2, 'uint16', 1)  # product = 1
        # fields[3] is timestamp, just check it's a reasonable value
        assert fields[3][0] == 3
        assert fields[3][1] == 'uint32'
        assert isinstance(fields[3][2], int)
        assert fields[3][2] > 1000000000  # Reasonable timestamp
    
    def test_add_workout_message(self):
        """Test adding workout message"""
        writer = FITFileWriter()
        writer.add_workout_message("Test Workout", 5)
        
        assert len(writer.data_records) == 1
        record = writer.data_records[0]
        assert record['global_type'] == 26  # WORKOUT message type
        
        fields = record['fields']
        assert len(fields) == 3
        
        # Check workout name field
        name_field = fields[0]
        assert name_field[0] == 4  # field number
        assert name_field[1] == 'string'  # field type
        name_bytes = name_field[2]
        assert len(name_bytes) == 16  # Padded to 16 bytes
        assert name_bytes.startswith(b'Test Workout')
        assert name_bytes.endswith(b'\x00' * (16 - len('Test Workout')))
        
        # Check sport field
        assert fields[1] == (5, 'enum', 0)  # sport = cycling
        
        # Check num_steps field
        assert fields[2] == (6, 'uint16', 5)  # num_valid_steps
    
    def test_add_workout_message_long_name(self):
        """Test workout message with long name (truncation)"""
        writer = FITFileWriter()
        long_name = "This is a very long workout name that should be truncated"
        writer.add_workout_message(long_name, 1)
        
        record = writer.data_records[0]
        name_field = record['fields'][0]
        name_bytes = name_field[2]
        
        # Should be truncated to 15 chars + null padding
        expected_name = long_name[:15].encode('utf-8')
        assert name_bytes.startswith(expected_name)
        assert len(name_bytes) == 16
    
    def test_add_workout_step(self):
        """Test adding workout step message"""
        writer = FITFileWriter()
        writer.add_workout_step(
            step_index=0,
            step_name="Warmup",
            duration_type=0,
            duration_value=300000,
            target_low=150,
            target_high=200,
            intensity=2
        )
        
        assert len(writer.data_records) == 1
        record = writer.data_records[0]
        assert record['global_type'] == 27  # WORKOUT_STEP message type
        
        fields = record['fields']
        assert len(fields) == 9
        
        assert fields[0] == (254, 'uint16', 0)  # message_index
        
        # Check step name
        name_field = fields[1]
        assert name_field[0] == 0
        assert name_field[1] == 'string'
        name_bytes = name_field[2]
        assert name_bytes.startswith(b'Warmup')
        assert len(name_bytes) == 16
        
        assert fields[2] == (1, 'enum', 0)  # duration_type
        assert fields[3] == (2, 'uint32', 300000)  # duration_value
        assert fields[4] == (3, 'enum', 4)  # target_type (power)
        assert fields[5] == (4, 'uint32', 0)  # target_power_zone
        assert fields[6] == (5, 'uint32', 150)  # target_low
        assert fields[7] == (6, 'uint32', 200)  # target_high
        assert fields[8] == (7, 'enum', 2)  # intensity
    
    def test_add_workout_step_long_name(self):
        """Test workout step with long name (truncation)"""
        writer = FITFileWriter()
        long_name = "This is a very long step name that should be truncated"
        writer.add_workout_step(0, long_name, 0, 1000, 100, 200, 0)
        
        record = writer.data_records[0]
        name_field = record['fields'][1]
        name_bytes = name_field[2]
        
        expected_name = long_name[:15].encode('utf-8')
        assert name_bytes.startswith(expected_name)
        assert len(name_bytes) == 16


class TestFileWriting:
    """Test file writing functionality"""
    
    def test_write_empty_file_raises_error(self, tmp_path):
        """Test that writing empty file raises ValueError"""
        writer = FITFileWriter()
        
        temp_path = tmp_path / "empty.fit"
        
        with pytest.raises(ValueError, match="No messages to write"):
            writer.write_fit_file(str(temp_path))
    
    def test_write_minimal_file(self, tmp_path):
        """Test writing minimal valid FIT file"""
        writer = FITFileWriter()
        writer.add_file_id_message()
        
        temp_path = tmp_path / "minimal.fit"
        
        crc = writer.write_fit_file(str(temp_path))
        
        # Check file exists and has content
        assert temp_path.exists()
        file_size = temp_path.stat().st_size
        assert file_size > 14  # At least header size
        
        # Check return value
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF
        
        # Verify file structure
        with open(temp_path, 'rb') as f:
            # Check header
            header = f.read(14)
            assert len(header) == 14
            assert header[0] == 14  # header_size
            assert header[1] == 32  # protocol_version
            assert header[8:12] == b'.FIT'  # data_type
            
            # Check that CRC is at the end
            f.seek(-2, 2)  # Seek to last 2 bytes
            crc_bytes = f.read(2)
            file_crc = struct.unpack('<H', crc_bytes)[0]
            assert file_crc == crc
    
    def test_write_complete_workout_file(self, tmp_path):
        """Test writing complete workout file with multiple messages"""
        writer = FITFileWriter()
        writer.add_file_id_message()
        writer.add_workout_message("Test Workout", 2)
        writer.add_workout_step(0, "Warmup", 0, 300000, 150, 200, 2)
        writer.add_workout_step(1, "Main Set", 0, 1200000, 250, 300, 0)
        
        temp_path = tmp_path / "complete.fit"
        
        crc = writer.write_fit_file(str(temp_path))
        
        assert temp_path.exists()
        file_size = temp_path.stat().st_size
        assert file_size > 100  # Should be reasonably sized
        
        # Verify file can be read back
        with open(temp_path, 'rb') as f:
            data = f.read()
            assert len(data) == file_size
            assert data[8:12] == b'.FIT'
    
    def test_write_file_io_error(self):
        """Test handling of IO errors during file writing"""
        writer = FITFileWriter()
        writer.add_file_id_message()
        
        # Try to write to invalid path
        invalid_path = "/invalid/path/that/does/not/exist.fit"
        
        with pytest.raises(IOError):
            writer.write_fit_file(invalid_path)


class TestCRCCalculation:
    """Test CRC calculation functionality"""
    
    def test_crc_empty_data(self):
        """Test CRC calculation with empty data"""
        writer = FITFileWriter()
        crc = writer._calculate_crc(b'')
        assert crc == 0
    
    def test_crc_known_values(self):
        """Test CRC calculation with known values"""
        writer = FITFileWriter()
        
        # Test with simple data
        crc1 = writer._calculate_crc(b'\x00')
        assert isinstance(crc1, int)
        assert 0 <= crc1 <= 0xFFFF
        
        crc2 = writer._calculate_crc(b'\xFF')
        assert isinstance(crc2, int)
        assert 0 <= crc2 <= 0xFFFF
        assert crc1 != crc2  # Different input should give different CRC
    
    def test_crc_consistency(self):
        """Test that CRC calculation is consistent"""
        writer = FITFileWriter()
        test_data = b'Hello, World!'
        
        crc1 = writer._calculate_crc(test_data)
        crc2 = writer._calculate_crc(test_data)
        assert crc1 == crc2
    
    def test_crc_different_data(self):
        """Test that different data produces different CRCs"""
        writer = FITFileWriter()
        
        crc1 = writer._calculate_crc(b'test data 1')
        crc2 = writer._calculate_crc(b'test data 2')
        assert crc1 != crc2


class TestMessageTypes:
    """Test message type handling"""
    
    def test_local_message_type_assignment(self, tmp_path):
        """Test local message type assignment during file writing"""
        writer = FITFileWriter()
        
        # Add different global message types
        writer.add_file_id_message()  # global type 0
        writer.add_workout_message("Test", 1)  # global type 26
        writer.add_workout_step(0, "Step", 0, 1000, 100, 200, 0)  # global type 27
        
        # Local message types are assigned during write_fit_file
        temp_path = tmp_path / "message_types.fit"
        
        writer.write_fit_file(str(temp_path))
        
        # Check that local message types were assigned
        assert 0 in writer.local_message_types
        assert 26 in writer.local_message_types
        assert 27 in writer.local_message_types
        
        # Should have assigned sequential local types
        assert writer.local_message_types[0] == 0
        assert writer.local_message_types[26] == 1
        assert writer.local_message_types[27] == 2
        assert writer.next_local_type == 3
    
    def test_duplicate_global_types(self, tmp_path):
        """Test handling of duplicate global message types"""
        writer = FITFileWriter()
        
        # Add file ID and multiple workout steps (same global type)
        writer.add_file_id_message()
        writer.add_workout_step(0, "Step 1", 0, 1000, 100, 200, 0)
        writer.add_workout_step(1, "Step 2", 0, 2000, 150, 250, 0)
        
        temp_path = tmp_path / "duplicates.fit"
        
        writer.write_fit_file(str(temp_path))
        
        # Should reuse the same local message type for workout steps
        assert len(writer.local_message_types) == 2  # FILE_ID and WORKOUT_STEP
        assert 0 in writer.local_message_types  # FILE_ID
        assert 27 in writer.local_message_types  # WORKOUT_STEP
        assert writer.local_message_types[27] == 1  # Second local type assigned


class TestFieldTypes:
    """Test field type handling"""
    
    def test_unsupported_field_type(self, tmp_path):
        """Test handling of unsupported field types"""
        writer = FITFileWriter()
        
        # Manually add a message with unsupported field type
        writer._add_message(999, [(0, 'unsupported_type', 123)])
        
        temp_path = tmp_path / "unsupported.fit"
        
        with pytest.raises(IOError, match="Error writing FIT file.*Unsupported field type"):
            writer.write_fit_file(str(temp_path))
    
    def test_field_type_encoding(self, tmp_path):
        """Test that different field types are encoded correctly"""
        writer = FITFileWriter()
        
        # Add message with various field types
        fields = [
            (0, 'enum', 5),
            (1, 'uint8', 255),
            (2, 'uint16', 65535),
            (3, 'uint32', 4294967295),
            (4, 'string', b'test\x00\x00\x00\x00')
        ]
        writer._add_message(999, fields)
        
        # Should not raise any errors during encoding
        temp_path = tmp_path / "field_types.fit"
        
        writer.write_fit_file(str(temp_path))
        assert temp_path.exists()


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_very_long_workout_name(self):
        """Test with extremely long workout name"""
        writer = FITFileWriter()
        very_long_name = "x" * 1000  # Much longer than 15 chars
        writer.add_workout_message(very_long_name, 1)
        
        record = writer.data_records[0]
        name_field = record['fields'][0]
        name_bytes = name_field[2]
        
        # Should be truncated to 15 chars
        assert len(name_bytes) == 16
        assert name_bytes[:15] == b'x' * 15
        assert name_bytes[15] == 0  # Null terminator
    
    def test_zero_duration_step(self):
        """Test workout step with zero duration"""
        writer = FITFileWriter()
        writer.add_workout_step(0, "Zero Duration", 0, 0, 100, 200, 0)
        
        record = writer.data_records[0]
        duration_field = record['fields'][3]
        assert duration_field == (2, 'uint32', 0)
    
    def test_maximum_values(self):
        """Test with maximum allowed values"""
        writer = FITFileWriter()
        
        # Test with maximum uint32 value
        max_uint32 = 2**32 - 1
        writer.add_workout_step(0, "Max Values", 0, max_uint32, max_uint32, max_uint32, 255)
        
        record = writer.data_records[0]
        fields = record['fields']
        
        # Check that large values are handled correctly
        duration_field = fields[3]
        assert duration_field[2] == max_uint32
        
        target_low_field = fields[6]
        assert target_low_field[2] == max_uint32
    
    def test_empty_workout_name(self):
        """Test with empty workout name"""
        writer = FITFileWriter()
        writer.add_workout_message("", 0)
        
        record = writer.data_records[0]
        name_field = record['fields'][0]
        name_bytes = name_field[2]
        
        # Should be all nulls
        assert name_bytes == b'\x00' * 16
    
    def test_unicode_workout_name(self):
        """Test with Unicode characters in workout name"""
        writer = FITFileWriter()
        unicode_name = "Тест 测试"  # Cyrillic and Chinese characters
        writer.add_workout_message(unicode_name, 1)
        
        record = writer.data_records[0]
        name_field = record['fields'][0]
        name_bytes = name_field[2]
        
        # Should be UTF-8 encoded and properly truncated/padded
        assert len(name_bytes) == 16
        # The exact content depends on UTF-8 encoding of the Unicode string


class TestIntegration:
    """Integration tests"""
    
    def test_realistic_workout_file(self, tmp_path):
        """Test creating a realistic workout file"""
        writer = FITFileWriter()
        
        # Create a realistic workout structure
        writer.add_file_id_message()
        writer.add_workout_message("5x4min@FTP", 7)
        
        # Warmup
        writer.add_workout_step(0, "Warmup", 0, 600000, 100, 150, 2)
        
        # Main set - 5 intervals
        for i in range(5):
            # Work interval
            writer.add_workout_step(i*2+1, f"Interval {i+1}", 0, 240000, 250, 280, 0)
            # Rest interval
            writer.add_workout_step(i*2+2, f"Recovery {i+1}", 0, 120000, 80, 120, 1)
        
        # Cooldown
        writer.add_workout_step(11, "Cooldown", 0, 300000, 80, 100, 3)
        
        temp_path = tmp_path / "realistic.fit"
        
        crc = writer.write_fit_file(str(temp_path))
        
        # Verify file
        assert temp_path.exists()
        file_size = temp_path.stat().st_size
        assert file_size > 500  # Should be substantial
        
        # File should be readable as binary
        with open(temp_path, 'rb') as f:
            data = f.read()
            assert data[8:12] == b'.FIT'
    
    def test_multiple_files_same_writer(self, tmp_path):
        """Test writing multiple files with the same writer instance"""
        writer = FITFileWriter()
        
        for i in range(3):
            writer.clear()  # Reset for each file
            writer.add_file_id_message()
            writer.add_workout_message(f"Workout {i}", 1)
            writer.add_workout_step(0, f"Step {i}", 0, 60000, 100, 200, 0)
            
            temp_path = tmp_path / f"workout_{i}.fit"
            
            crc = writer.write_fit_file(str(temp_path))
            assert temp_path.exists()
            assert temp_path.stat().st_size > 50


class TestCreateWorkoutFile:
    """Test the create_workout_file method"""
    
    def test_create_workout_file_empty_segments(self, tmp_path):
        """Test create_workout_file with empty segments raises error"""
        writer = FITFileWriter()
        temp_path = tmp_path / "empty.fit"
        
        with pytest.raises(ValueError, match="No segments provided"):
            writer.create_workout_file([], str(temp_path))
    
    def test_create_workout_file_single_segment(self, tmp_path):
        """Test create_workout_file with single segment"""
        from zwo_parser import WorkoutSegment
        
        writer = FITFileWriter()
        segments = [
            WorkoutSegment(type='steady', duration=300, power=0.75)
        ]
        temp_path = tmp_path / "single.fit"
        
        crc = writer.create_workout_file(segments, str(temp_path), "Single Test", ftp=250)
        
        assert temp_path.exists()
        assert isinstance(crc, int)
        
        # Verify the file contains expected messages
        assert len(writer.data_records) == 3  # File ID + Workout + 1 Step
        assert writer.data_records[1]['global_type'] == 26  # WORKOUT
        assert writer.data_records[2]['global_type'] == 27  # WORKOUT_STEP
    
    def test_create_workout_file_warmup_segment(self, tmp_path):
        """Test create_workout_file with warmup segment"""
        from zwo_parser import WorkoutSegment
        
        writer = FITFileWriter()
        segments = [
            WorkoutSegment(type='warmup', duration=600, power_start=0.5, power_end=0.75)
        ]
        temp_path = tmp_path / "warmup.fit"
        
        crc = writer.create_workout_file(segments, str(temp_path), "Warmup Test", ftp=280)
        
        assert temp_path.exists()
        
        # Check workout step details
        step_record = writer.data_records[2]
        fields = step_record['fields']
        
        # Check step name contains warmup percentage range
        step_name_field = fields[1]
        step_name_bytes = step_name_field[2]
        step_name = step_name_bytes.decode('utf-8').rstrip('\x00')
        assert "Warmup 50-75%" == step_name
        
        # Check intensity is warmup (2)
        intensity_field = fields[8]
        assert intensity_field[2] == 2
    
    def test_create_workout_file_cooldown_segment(self, tmp_path):
        """Test create_workout_file with cooldown segment"""
        from zwo_parser import WorkoutSegment
        
        writer = FITFileWriter()
        segments = [
            WorkoutSegment(type='cooldown', duration=600, power_start=0.7, power_end=0.4)
        ]
        temp_path = tmp_path / "cooldown.fit"
        
        crc = writer.create_workout_file(segments, str(temp_path), "Cooldown Test")
        
        assert temp_path.exists()
        
        # Check workout step details
        step_record = writer.data_records[2]
        fields = step_record['fields']
        
        # Check step name contains cooldown percentage range
        step_name_field = fields[1]
        step_name_bytes = step_name_field[2]
        step_name = step_name_bytes.decode('utf-8').rstrip('\x00')
        assert "Cooldown 70-40%" == step_name
        
        # Check intensity is cooldown (3)
        intensity_field = fields[8]
        assert intensity_field[2] == 3
    
    def test_create_workout_file_interval_segments(self, tmp_path):
        """Test create_workout_file with work and rest intervals"""
        from zwo_parser import WorkoutSegment
        
        writer = FITFileWriter()
        segments = [
            WorkoutSegment(type='interval_work', duration=240, power=1.2),
            WorkoutSegment(type='interval_rest', duration=120, power=0.5)
        ]
        temp_path = tmp_path / "intervals.fit"
        
        crc = writer.create_workout_file(segments, str(temp_path), "Interval Test")
        
        assert temp_path.exists()
        
        # Check work interval
        work_step = writer.data_records[2]
        work_fields = work_step['fields']
        work_name = work_fields[1][2].decode('utf-8').rstrip('\x00')
        work_intensity = work_fields[8][2]
        
        assert "Work 120%" == work_name
        assert work_intensity == 0  # active
        
        # Check rest interval
        rest_step = writer.data_records[3]
        rest_fields = rest_step['fields']
        rest_name = rest_fields[1][2].decode('utf-8').rstrip('\x00')
        rest_intensity = rest_fields[8][2]
        
        assert "Rest 50%" == rest_name
        assert rest_intensity == 1  # rest
    
    def test_create_workout_file_unknown_segment_type(self, tmp_path):
        """Test create_workout_file with unknown segment type"""
        from zwo_parser import WorkoutSegment
        
        writer = FITFileWriter()
        segments = [
            WorkoutSegment(type='unknown_type', duration=300, power=0.8)
        ]
        temp_path = tmp_path / "unknown.fit"
        
        crc = writer.create_workout_file(segments, str(temp_path), "Unknown Test")
        
        assert temp_path.exists()
        
        # Check default handling
        step_record = writer.data_records[2]
        fields = step_record['fields']
        
        # Should use default step name
        step_name = fields[1][2].decode('utf-8').rstrip('\x00')
        assert "Step 1" == step_name
        
        # Should use active intensity (0)
        intensity = fields[8][2]
        assert intensity == 0
    
    def test_create_workout_file_complex_workout(self, tmp_path):
        """Test create_workout_file with complex multi-segment workout"""
        from zwo_parser import WorkoutSegment
        
        writer = FITFileWriter()
        segments = [
            WorkoutSegment(type='warmup', duration=600, power_start=0.5, power_end=0.75),
            WorkoutSegment(type='steady', duration=300, power=0.8),
            WorkoutSegment(type='interval_work', duration=240, power=1.1),
            WorkoutSegment(type='interval_rest', duration=120, power=0.5),
            WorkoutSegment(type='interval_work', duration=240, power=1.1),
            WorkoutSegment(type='cooldown', duration=600, power_start=0.7, power_end=0.4)
        ]
        temp_path = tmp_path / "complex.fit"
        
        crc = writer.create_workout_file(segments, str(temp_path), "Complex Workout", ftp=300)
        
        assert temp_path.exists()
        
        # Should have file ID + workout + 6 steps = 8 total records
        assert len(writer.data_records) == 8
        
        # Check workout message
        workout_record = writer.data_records[1]
        workout_fields = workout_record['fields']
        workout_name = workout_fields[0][2].decode('utf-8').rstrip('\x00')
        num_steps = workout_fields[2][2]
        
        assert "Complex Workout" == workout_name
        assert num_steps == 6
        
        # Verify all steps have correct durations (in milliseconds)
        expected_durations = [600000, 300000, 240000, 120000, 240000, 600000]
        for i, expected_duration in enumerate(expected_durations):
            step_record = writer.data_records[i + 2]  # Skip file ID and workout
            duration_field = step_record['fields'][3]  # duration_value field
            assert duration_field[2] == expected_duration
    
    def test_create_workout_file_custom_ftp(self, tmp_path):
        """Test create_workout_file with custom FTP value"""
        from zwo_parser import WorkoutSegment
        
        writer = FITFileWriter()
        segments = [
            WorkoutSegment(type='steady', duration=300, power=1.0)  # 100% FTP
        ]
        temp_path = tmp_path / "custom_ftp.fit"
        
        # Use custom FTP of 400W
        crc = writer.create_workout_file(segments, str(temp_path), "FTP Test", ftp=400)
        
        assert temp_path.exists()
        
        # The actual power targets are calculated by calculate_ftp_targets
        # We just verify the method completed successfully
        assert isinstance(crc, int)
    
    def test_create_workout_file_clears_existing_data(self, tmp_path):
        """Test that create_workout_file clears existing data"""
        from zwo_parser import WorkoutSegment
        
        writer = FITFileWriter()
        
        # Add some initial data
        writer.add_file_id_message()
        writer.add_workout_message("Initial", 1)
        assert len(writer.data_records) == 2
        
        # Create new workout - should clear existing data
        segments = [
            WorkoutSegment(type='steady', duration=300, power=0.75)
        ]
        temp_path = tmp_path / "cleared.fit"
        
        crc = writer.create_workout_file(segments, str(temp_path), "New Workout")
        
        assert temp_path.exists()
        
        # Should have exactly 3 records: file ID + workout + 1 step
        assert len(writer.data_records) == 3
        
        # Check that it's the new workout name
        workout_record = writer.data_records[1]
        workout_name = workout_record['fields'][0][2].decode('utf-8').rstrip('\x00')
        assert "New Workout" == workout_name


if __name__ == '__main__':
    pytest.main([__file__])