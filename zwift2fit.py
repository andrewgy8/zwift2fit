import struct
import datetime
import os
import glob
from typing import List, Dict, Any
from zwo_parser import WorkoutSegment
from fit_target_utils import calculate_ftp_targets
from zwo_parser import parse_zwo_to_workout

class FITFileWriter:
    """Improved FIT file writer for workout files"""
    
    def __init__(self):
        self.data_records = []
        self.local_message_types = {}
        self.next_local_type = 0
    
    def add_file_id_message(self):
        """Add file ID message"""
        fields = [
            (0, 'enum', 4),     # type = workout (4)
            (1, 'uint16', 1),   # manufacturer = Development (1)
            (2, 'uint16', 1),   # product = 1
            (3, 'uint32', int(datetime.datetime.now().timestamp())),  # time_created
        ]
        self._add_message(0, fields)  # FILE_ID global message type
    
    def add_workout_message(self, name: str, num_steps: int):
        """Add workout message"""
        name_bytes = name.encode('utf-8')[:15]  # Limit to 15 chars
        # Pad with nulls to make it exactly 16 bytes
        name_bytes = name_bytes + b'\x00' * (16 - len(name_bytes))
        
        fields = [
            (4, 'string', name_bytes),  # wkt_name
            (5, 'enum', 0),            # sport = cycling (0)
            (6, 'uint16', num_steps),  # num_valid_steps
        ]
        self._add_message(26, fields)  # WORKOUT global message type
    
    def add_workout_step(self, step_index: int, step_name: str, duration_type: int, 
                        duration_value: int, target_low: int, target_high: int, intensity: int):
        """Add workout step message"""
        name_bytes = step_name.encode('utf-8')[:15]
        name_bytes = name_bytes + b'\x00' * (16 - len(name_bytes))
        
        fields = [
            (254, 'uint16', step_index),      # message_index
            (0, 'string', name_bytes),        # wkt_step_name
            (1, 'enum', duration_type),       # duration_type (0=time)
            (2, 'uint32', duration_value),    # duration_value (milliseconds)
            (3, 'enum', 4),                   # target_type (4=power, not 1)
            (4, 'uint32', 0),                 # target_power_zone (0 for custom)
            (5, 'uint32', target_low),        # custom_target_power_low
            (6, 'uint32', target_high),       # custom_target_power_high
            (7, 'enum', intensity),           # intensity
        ]
        
        self._add_message(27, fields)  # WORKOUT_STEP global message type
    
    def _add_message(self, global_msg_type: int, fields: list):
        """Add a message to be written"""
        self.data_records.append({
            'global_type': global_msg_type,
            'fields': fields
        })
    
    def write_fit_file(self, output_path: str):
        """Write FIT file to disk with proper structure"""
        try:
            # Step 1: Write header and data without CRC
            with open(output_path, 'wb') as f:
                # Write header placeholder
                header_size = 14
                f.write(b'\x00' * header_size)  # Placeholder header
                
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
            with open(output_path, 'rb') as f:
                file_data = f.read()  # Read header + data (no CRC yet)
                crc = self._calculate_crc(file_data)
            
            # Step 3: Append CRC to file
            with open(output_path, 'ab') as f:
                f.write(struct.pack('<H', crc))
                
            print(f"FIT file written: {data_size} data bytes, CRC: {crc:04X}")
                
        except Exception as e:
            print(f"Error writing FIT file: {e}")
            raise
    
    def _write_header(self, f, data_size: int):
        """Write FIT file header"""
        header = bytearray(14)
        header[0] = 14                                    # header_size
        header[1] = 32                                    # protocol_version (2.0)
        header[2:4] = struct.pack('<H', 2105)            # profile_version
        header[4:8] = struct.pack('<I', data_size)       # data_size
        header[8:12] = b'.FIT'                           # data_type
        
        # Header CRC (optional, set to 0)
        header[12:14] = struct.pack('<H', 0)
        
        f.write(header)
    
    def _write_message_pair(self, f, record):
        """Write definition message followed by data message"""
        global_type = record['global_type']
        fields = record['fields']
        
        # Assign local message type
        if global_type not in self.local_message_types:
            self.local_message_types[global_type] = self.next_local_type
            self.next_local_type += 1
        
        local_type = self.local_message_types[global_type]
        
        # Write definition message
        def_header = 0x40 | local_type  # Definition message bit + local type
        f.write(struct.pack('B', def_header))
        f.write(struct.pack('B', 0))                    # reserved
        f.write(struct.pack('B', 0))                    # architecture (little endian)
        f.write(struct.pack('<H', global_type))         # global message number
        f.write(struct.pack('B', len(fields)))          # number of fields
        
        # Write field definitions
        for field_def_num, field_type, field_value in fields:
            f.write(struct.pack('B', field_def_num))     # field definition number
            
            if field_type == 'string':
                f.write(struct.pack('B', len(field_value)))  # size
                f.write(struct.pack('B', 7))                 # base type (string)
            elif field_type == 'enum':
                f.write(struct.pack('B', 1))                 # size
                f.write(struct.pack('B', 0))                 # base type (enum)
            elif field_type == 'uint8':
                f.write(struct.pack('B', 1))                 # size
                f.write(struct.pack('B', 2))                 # base type (uint8)
            elif field_type == 'uint16':
                f.write(struct.pack('B', 2))                 # size
                f.write(struct.pack('B', 132))               # base type (uint16)
            elif field_type == 'uint32':
                f.write(struct.pack('B', 4))                 # size
                f.write(struct.pack('B', 134))               # base type (uint32)
        
        # Write data message
        data_header = local_type  # Data message (no definition bit)
        f.write(struct.pack('B', data_header))
        
        # Write field data in the same order as definition
        for field_def_num, field_type, field_value in fields:
            if field_type == 'string':
                f.write(field_value)
            elif field_type in ['enum', 'uint8']:
                f.write(struct.pack('B', field_value))
            elif field_type == 'uint16':
                f.write(struct.pack('<H', field_value))
            elif field_type == 'uint32':  
                f.write(struct.pack('<I', field_value))
    
    def _calculate_crc(self, data: bytes) -> int:
        """Calculate CRC-16 for FIT files using correct FIT CRC algorithm"""
        crc_table = [
            0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
            0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400
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

# ZWO parsing is now handled by the zwo_parser module

def create_fit_file(segments: List[WorkoutSegment], output_path: str, workout_name: str = "Workout", ftp: int = 250):
    """Create FIT workout file from segments"""
    
    if not segments:
        print("No segments to convert")
        return
    
    fit_writer = FITFileWriter()
    
    # Add file ID message
    fit_writer.add_file_id_message()
    
    # Add workout message
    fit_writer.add_workout_message(workout_name, len(segments))
    
    # Add workout steps
    for i, segment in enumerate(segments):
        # Duration is always time-based (type 0), value in milliseconds
        duration_type = 0
        duration_value = segment.duration * 1000  # Convert to milliseconds
        
        # Target is always power-based (type 4), value in watts
        
        # Determine target power and intensity using reverse-engineered formula
        if segment.type == 'warmup':
            # For warmup, use power range with correct FIT encoding
            target_low, target_high = calculate_ftp_targets(
                segment.power_start, ftp=ftp, power_high_fraction=segment.power_end
            )
            intensity = 2  # warmup
            step_name = f"Warmup {segment.power_start*100:.0f}-{segment.power_end*100:.0f}%"
        
        elif segment.type == 'cooldown':
            # For cooldown, use power range with correct FIT encoding
            target_low, target_high = calculate_ftp_targets(
                segment.power_start, ftp=ftp, power_high_fraction=segment.power_end
            )
            intensity = 3  # cooldown
            step_name = f"Cooldown {segment.power_start*100:.0f}-{segment.power_end*100:.0f}%"
        
        elif segment.type == 'steady':
            # For steady state, use single power value with correct FIT encoding
            target_low, target_high = calculate_ftp_targets(segment.power, ftp=ftp)
            intensity = 0  # active
            step_name = f"Steady {segment.power*100:.0f}%"
        
        elif segment.type == 'interval_work':
            # For work intervals, use single power value with correct FIT encoding
            target_low, target_high = calculate_ftp_targets(segment.power, ftp=ftp)
            intensity = 0  # active
            step_name = f"Work {segment.power*100:.0f}%"
        
        elif segment.type == 'interval_rest':
            # For rest intervals, use single power value with correct FIT encoding
            target_low, target_high = calculate_ftp_targets(segment.power, ftp=ftp)
            intensity = 1  # rest
            step_name = f"Rest {segment.power*100:.0f}%"
        
        else:
            # Default case - use 50% FTP with correct FIT encoding
            target_low, target_high = calculate_ftp_targets(0.5, ftp=ftp)
            intensity = 0
            step_name = f"Step {i+1}"
        
        # Add the workout step
        fit_writer.add_workout_step(
            step_index=i,
            step_name=step_name,
            duration_type=duration_type,
            duration_value=duration_value,
            target_low=target_low,
            target_high=target_high,
            intensity=intensity
        )
    
    # Write FIT file
    try:
        fit_writer.write_fit_file(output_path)
        print(f"Successfully created FIT file: {output_path}")
    except Exception as e:
        print(f"Error creating FIT file: {e}")
        raise

def convert_zwo_to_fit(zwo_path: str, fit_path: str = None, ftp: int = 250):
    """Convert a single ZWO file to FIT format"""
    if fit_path is None:
        fit_path = zwo_path.replace('.zwo', '.fit')
    
    try:
        workout = parse_zwo_to_workout(zwo_path)
        create_fit_file(workout.segments, fit_path, workout.name, ftp)
        print(f"Converted: {zwo_path} -> {fit_path}")
        return True
    except Exception as e:
        print(f"Error converting {zwo_path}: {str(e)}")
        return False

def batch_convert_zwo_to_fit(input_directory: str, output_directory: str = None, ftp: int = 250):
    """Convert all ZWO files in a directory to FIT format"""
    if output_directory is None:
        output_directory = input_directory
    
    # Create output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)
    
    # Find all ZWO files
    zwo_files = glob.glob(os.path.join(input_directory, "*.zwo"))
    
    if not zwo_files:
        print(f"No .zwo files found in {input_directory}")
        return
    
    print(f"Found {len(zwo_files)} .zwo files to convert...")
    
    success_count = 0
    for zwo_file in zwo_files:
        filename = os.path.basename(zwo_file)
        fit_filename = filename.replace('.zwo', '.fit')
        fit_path = os.path.join(output_directory, fit_filename)
        
        if convert_zwo_to_fit(zwo_file, fit_path, ftp):
            success_count += 1
    
    print(f"Successfully converted {success_count}/{len(zwo_files)} files")

# Example usage
if __name__ == "__main__":
    # Convert single file (modify these paths for your files)
    # convert_zwo_to_fit("pacing1.zwo", "pacing1.fit", ftp=280)
    
    # Batch convert all files in current directory
    batch_convert_zwo_to_fit(".", ftp=280)
    
    # Batch convert with specific input/output directories
    # batch_convert_zwo_to_fit("./zwo_files", "./fit_files", ftp=275)