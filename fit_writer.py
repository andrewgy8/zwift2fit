"""
FIT file writer module.

This module provides functionality to write FIT (Flexible and Interoperable Data Transfer)
workout files that are compatible with Garmin devices and other fitness applications.
"""

import struct
import datetime
from typing import List, Dict, Any, BinaryIO

from zwo_parser import WorkoutSegment


def calculate_ftp_targets(power_low_fraction, ftp, power_high_fraction=None):
    """
    Calculate target_low and target_high values for FIT files using reverse-engineered formula.

    The formula was reverse-engineered from analyzing pacing1.fit, which was created with FTP=280.
    The FIT format stores actual power values, not normalized percentages, so we need the FTP
    to calculate the correct targets.

    Reverse-engineered formula:
        midpoint = 1000 + ftp * power_fraction
        range = 0.2 * ftp * power_fraction  (approximately)
        target_low = midpoint - range/2
        target_high = midpoint + range/2

    Args:
        power_low_fraction: Power as fraction of FTP (e.g., 0.5 for 50% FTP)
        power_high_fraction: Optional high power fraction for ranges (e.g., warmup/cooldown)
        ftp: Functional Threshold Power in watts (required)

    Returns:
        tuple: (target_low, target_high) - integer values for FIT file

    Examples:
        calculate_ftp_targets(0.5, ftp=280)        -> (1126, 1154)  # 50% of 280W FTP
        calculate_ftp_targets(0.5, ftp=250)        -> (1097, 1123)  # 50% of 250W FTP
        calculate_ftp_targets(0.5, 0.75, ftp=280)  -> (1126, 1231)  # 50-75% range
    """

    if power_high_fraction is None:
        power_high_fraction = power_low_fraction

    if power_low_fraction == power_high_fraction:
        # Single power value (steady state, intervals)
        midpoint = 1000 + ftp * power_low_fraction
        half_range = int(0.2 * ftp * power_low_fraction / 2)
        target_low = int(midpoint - half_range)
        target_high = int(midpoint + half_range)
    else:
        # Power range (warmup, cooldown)
        # Calculate endpoints separately for better accuracy
        low_midpoint = 1000 + ftp * power_low_fraction
        low_half_range = int(0.2 * ftp * power_low_fraction / 2)
        target_low = int(low_midpoint - low_half_range)

        high_midpoint = 1000 + ftp * power_high_fraction
        high_half_range = int(0.2 * ftp * power_high_fraction / 2)
        target_high = int(high_midpoint + high_half_range)

    return target_low, target_high


class FITFileWriter:
    """
    A writer for FIT workout files.

    This class handles the creation of FIT files containing workout definitions
    with proper message structure, CRC calculation, and binary encoding.
    """

    def __init__(self):
        """Initialize the FIT file writer."""
        self.data_records = []
        self.local_message_types = {}
        self.next_local_type = 0

    def add_file_id_message(self):
        """
        Add file ID message to identify this as a workout file.

        This message must be the first message in any FIT file and identifies
        the file type, manufacturer, and creation time.
        """
        fields = [
            (0, "enum", 4),  # type = workout (4)
            (1, "uint16", 1),  # manufacturer = Development (1)
            (2, "uint16", 1),  # product = 1
            (3, "uint32", int(datetime.datetime.now().timestamp())),  # time_created
        ]
        self._add_message(0, fields)  # FILE_ID global message type

    def add_workout_message(self, name: str, num_steps: int):
        """
        Add workout message containing workout metadata.

        Args:
            name: Workout name (will be truncated to 15 characters)
            num_steps: Number of workout steps that will follow
        """
        name_bytes = name.encode("utf-8")[:15]  # Limit to 15 chars
        # Pad with nulls to make it exactly 16 bytes
        name_bytes = name_bytes + b"\x00" * (16 - len(name_bytes))

        fields = [
            (4, "string", name_bytes),  # wkt_name
            (5, "enum", 0),  # sport = cycling (0)
            (6, "uint16", num_steps),  # num_valid_steps
        ]
        self._add_message(26, fields)  # WORKOUT global message type

    def add_workout_step(
        self,
        step_index: int,
        step_name: str,
        duration_type: int,
        duration_value: int,
        target_low: int,
        target_high: int,
        intensity: int,
    ):
        """
        Add a workout step message.

        Args:
            step_index: Zero-based index of this step
            step_name: Name/description of this step (will be truncated to 15 characters)
            duration_type: Type of duration (0=time, 28=repeatUntilStepsCmplt, etc.)
            duration_value: Duration value (milliseconds for time, step index for repeat)
            target_low: Lower bound of target power range (in device-specific units)
            target_high: Upper bound of target power range (in device-specific units)
            intensity: Intensity level (0=active, 1=rest, 2=warmup, 3=cooldown)
        """
        name_bytes = step_name.encode("utf-8")[:15]
        name_bytes = name_bytes + b"\x00" * (16 - len(name_bytes))

        fields = [
            (254, "uint16", step_index),  # message_index
            (0, "string", name_bytes),  # wkt_step_name
            (1, "enum", duration_type),  # duration_type (0=time)
            (2, "uint32", duration_value),  # duration_value (milliseconds)
            (3, "enum", 4),  # target_type (4=power)
            (4, "uint32", 0),  # target_power_zone (0 for custom)
            (5, "uint32", target_low),  # custom_target_power_low
            (6, "uint32", target_high),  # custom_target_power_high
            (7, "enum", intensity),  # intensity
        ]

        self._add_message(27, fields)  # WORKOUT_STEP global message type

    def _add_message(self, global_msg_type: int, fields: List[tuple]):
        """
        Add a message to be written to the FIT file.

        Args:
            global_msg_type: FIT global message type number
            fields: List of (field_number, field_type, field_value) tuples
        """
        self.data_records.append({"global_type": global_msg_type, "fields": fields})

    def write_fit_file(self, output_path: str) -> int:
        """
        Write the FIT file to disk.

        Args:
            output_path: Path where the FIT file should be written

        Returns:
            CRC value of the written file

        Raises:
            IOError: If file cannot be written
            ValueError: If no messages have been added
        """
        if not self.data_records:
            raise ValueError("No messages to write. Add at least a file ID message.")

        try:
            # Step 1: Write header and data without CRC
            with open(output_path, "wb") as f:
                # Write header placeholder
                header_size = 14
                f.write(b"\x00" * header_size)  # Placeholder header

                data_start_pos = f.tell()

                # Write all messages (definition + data)
                for record in self.data_records:
                    self._write_message_pair(f, record)

                data_end_pos = f.tell()
                data_size = data_end_pos - data_start_pos

                # Write real header
                f.seek(0)
                self._write_header(f, data_size)

            # Step 2: Calculate CRC over the entire file (header + data)
            with open(output_path, "rb") as f:
                file_data = f.read()  # Read header + data (no CRC yet)
                crc = self._calculate_crc(file_data)

            # Step 3: Append CRC to file
            with open(output_path, "ab") as f:
                f.write(struct.pack("<H", crc))

            return crc

        except Exception as e:
            raise IOError(f"Error writing FIT file: {e}")

    def _write_header(self, f: BinaryIO, data_size: int):
        """
        Write FIT file header.

        Args:
            f: File object to write to
            data_size: Size of data section in bytes
        """
        header = bytearray(14)
        header[0] = 14  # header_size
        header[1] = 32  # protocol_version (2.0)
        header[2:4] = struct.pack("<H", 2105)  # profile_version
        header[4:8] = struct.pack("<I", data_size)  # data_size
        header[8:12] = b".FIT"  # data_type

        # Header CRC (optional, set to 0)
        header[12:14] = struct.pack("<H", 0)

        f.write(header)

    def _write_message_pair(self, f: BinaryIO, record: Dict[str, Any]):
        """
        Write definition message followed by data message.

        Args:
            f: File object to write to
            record: Message record containing global_type and fields
        """
        global_type = record["global_type"]
        fields = record["fields"]

        # Assign local message type
        if global_type not in self.local_message_types:
            self.local_message_types[global_type] = self.next_local_type
            self.next_local_type += 1

        local_type = self.local_message_types[global_type]

        # Write definition message
        def_header = 0x40 | local_type  # Definition message bit + local type
        f.write(struct.pack("B", def_header))
        f.write(struct.pack("B", 0))  # reserved
        f.write(struct.pack("B", 0))  # architecture (little endian)
        f.write(struct.pack("<H", global_type))  # global message number
        f.write(struct.pack("B", len(fields)))  # number of fields

        # Write field definitions
        for field_def_num, field_type, field_value in fields:
            f.write(struct.pack("B", field_def_num))  # field definition number

            if field_type == "string":
                f.write(struct.pack("B", len(field_value)))  # size
                f.write(struct.pack("B", 7))  # base type (string)
            elif field_type == "enum":
                f.write(struct.pack("B", 1))  # size
                f.write(struct.pack("B", 0))  # base type (enum)
            elif field_type == "uint8":
                f.write(struct.pack("B", 1))  # size
                f.write(struct.pack("B", 2))  # base type (uint8)
            elif field_type == "uint16":
                f.write(struct.pack("B", 2))  # size
                f.write(struct.pack("B", 132))  # base type (uint16)
            elif field_type == "uint32":
                f.write(struct.pack("B", 4))  # size
                f.write(struct.pack("B", 134))  # base type (uint32)
            else:
                raise ValueError(f"Unsupported field type: {field_type}")

        # Write data message
        data_header = local_type  # Data message (no definition bit)
        f.write(struct.pack("B", data_header))

        # Write field data in the same order as definition
        for field_def_num, field_type, field_value in fields:
            if field_type == "string":
                f.write(field_value)
            elif field_type in ["enum", "uint8"]:
                f.write(struct.pack("B", field_value))
            elif field_type == "uint16":
                f.write(struct.pack("<H", field_value))
            elif field_type == "uint32":
                f.write(struct.pack("<I", field_value))

    def _calculate_crc(self, data: bytes) -> int:
        """
        Calculate CRC-16 for FIT files using the correct FIT CRC algorithm.

        Args:
            data: Bytes to calculate CRC for

        Returns:
            16-bit CRC value
        """
        crc_table = [
            0x0000,
            0xCC01,
            0xD801,
            0x1400,
            0xF001,
            0x3C00,
            0x2800,
            0xE401,
            0xA001,
            0x6C00,
            0x7800,
            0xB401,
            0x5000,
            0x9C01,
            0x8801,
            0x4400,
        ]

        crc = 0
        for byte in data:
            # Process lower nibble
            tmp = crc_table[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ crc_table[byte & 0xF]

            # Process upper nibble
            tmp = crc_table[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ crc_table[(byte >> 4) & 0xF]

        return crc & 0xFFFF

    def clear(self):
        """Clear all messages and reset the writer state."""
        self.data_records.clear()
        self.local_message_types.clear()
        self.next_local_type = 0

    def create_workout_file(
        self,
        segments: List["WorkoutSegment"],
        output_path: str,
        workout_name: str = "Workout",
        ftp: int = 250,
    ) -> int:
        """
        Create a complete FIT workout file from workout segments.

        Args:
            segments: List of WorkoutSegment objects defining the workout
            output_path: Path where the FIT file should be written
            workout_name: Name of the workout (default: "Workout")
            ftp: Functional Threshold Power in watts for target calculations (default: 250)

        Returns:
            CRC value of the written file

        Raises:
            ValueError: If segments list is empty
            IOError: If file cannot be written
        """
        if not segments:
            raise ValueError("No segments provided. Cannot create empty workout.")

        # Use the calculate_ftp_targets function from this module

        # Clear any existing data
        self.clear()

        # Add file ID message
        self.add_file_id_message()

        # Add workout message
        self.add_workout_message(workout_name, len(segments))

        # Add workout steps
        for i, segment in enumerate(segments):
            # Duration is always time-based (type 0), value in milliseconds
            duration_type = 0
            duration_value = segment.duration * 1000  # Convert to milliseconds

            # Determine target power and intensity using reverse-engineered formula
            if segment.type == "warmup":
                # For warmup, use power range with correct FIT encoding
                target_low, target_high = calculate_ftp_targets(
                    segment.power_start, ftp=ftp, power_high_fraction=segment.power_end
                )
                intensity = 2  # warmup
                step_name = f"Warmup {segment.power_start * 100:.0f}-{segment.power_end * 100:.0f}%"

            elif segment.type == "cooldown":
                # For cooldown, use power range with correct FIT encoding
                target_low, target_high = calculate_ftp_targets(
                    segment.power_start, ftp=ftp, power_high_fraction=segment.power_end
                )
                intensity = 3  # cooldown
                step_name = f"Cooldown {segment.power_start * 100:.0f}-{segment.power_end * 100:.0f}%"

            elif segment.type == "steady":
                # For steady state, use single power value with correct FIT encoding
                target_low, target_high = calculate_ftp_targets(segment.power, ftp=ftp)
                intensity = 0  # active
                step_name = f"Steady {segment.power * 100:.0f}%"

            elif segment.type == "interval_work":
                # For work intervals, use single power value with correct FIT encoding
                target_low, target_high = calculate_ftp_targets(segment.power, ftp=ftp)
                intensity = 0  # active
                step_name = f"Work {segment.power * 100:.0f}%"

            elif segment.type == "interval_rest":
                # For rest intervals, use single power value with correct FIT encoding
                target_low, target_high = calculate_ftp_targets(segment.power, ftp=ftp)
                intensity = 1  # rest
                step_name = f"Rest {segment.power * 100:.0f}%"

            else:
                # Default case - use 50% FTP with correct FIT encoding
                target_low, target_high = calculate_ftp_targets(0.5, ftp=ftp)
                intensity = 0
                step_name = f"Step {i + 1}"

            # Add the workout step
            self.add_workout_step(
                step_index=i,
                step_name=step_name,
                duration_type=duration_type,
                duration_value=duration_value,
                target_low=target_low,
                target_high=target_high,
                intensity=intensity,
            )

        # Write FIT file
        return self.write_fit_file(output_path)
