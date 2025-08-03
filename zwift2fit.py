import xml.etree.ElementTree as ET
import struct
import datetime
import os
import glob
from typing import List, Dict, Any

class FITFileWriter:
    """Simple FIT file writer for workout files"""
    
    def __init__(self):
        self.messages = []
        self.local_message_types = {}
        self.next_local_type = 0
    
    def add_file_id_message(self):
        """Add file ID message"""
        message = {
            'global_type': 0,  # FILE_ID
            'fields': {
                0: 4,  # type = activity
                1: 2,  # manufacturer = Garmin (arbitrary)
                2: 1,  # product = 1
                3: int(datetime.datetime.now().timestamp()),  # time_created
            }
        }
        self.messages.append(message)
    
    def add_workout_message(self, name: str):
        """Add workout message"""
        message = {
            'global_type': 26,  # WORKOUT
            'fields': {
                4: name.encode('utf-8')[:15],  # wkt_name (max 16 bytes)
                5: 0,  # sport = cycling
                6: len(self.messages),  # num_valid_steps will be updated
            }
        }
        self.messages.append(message)
        return len(self.messages) - 1  # Return index for updating num_valid_steps
    
    def add_workout_step(self, duration_type: int, duration_value: int, 
                        target_type: int, target_value: int, intensity: int = 1):
        """Add workout step message"""
        message = {
            'global_type': 27,  # WORKOUT_STEP
            'fields': {
                0: len([m for m in self.messages if m['global_type'] == 27]),  # message_index
                1: f"Step {len([m for m in self.messages if m['global_type'] == 27]) + 1}".encode('utf-8')[:15],  # wkt_step_name
                2: duration_type,  # duration_type
                3: duration_value,  # duration_value
                4: target_type,  # target_type
                5: target_value,  # target_value
                6: intensity,  # intensity (0=active, 1=rest, 2=warmup, 3=cooldown)
            }
        }
        self.messages.append(message)
    
    def write_fit_file(self, output_path: str):
        """Write FIT file to disk"""
        with open(output_path, 'wb') as f:
            # Write FIT header
            header = bytearray(14)
            header[0] = 14  # header_size
            header[1] = 16  # protocol_version
            header[2:4] = struct.pack('<H', 2132)  # profile_version
            header[8:12] = b'.FIT'  # data_type
            
            # Calculate data size (will update later)
            data_start = f.tell() + 14
            f.write(header)
            
            data_start_pos = f.tell()
            
            # Write definition and data messages
            for message in self.messages:
                self._write_message(f, message)
            
            # Calculate and write data size and CRC
            data_end_pos = f.tell()
            data_size = data_end_pos - data_start_pos
            
            # Update data size in header
            f.seek(4)
            f.write(struct.pack('<I', data_size))
            
            # Write CRC (simplified - just write 0x0000 for now)
            f.seek(data_end_pos)
            f.write(struct.pack('<H', 0x0000))
    
    def _write_message(self, f, message):
        """Write a single message to the FIT file"""
        global_type = message['global_type']
        fields = message['fields']
        
        # Use a simple local message type assignment
        if global_type not in self.local_message_types:
            self.local_message_types[global_type] = self.next_local_type
            self.next_local_type += 1
            
            # Write definition message
            local_type = self.local_message_types[global_type]
            definition_header = 0x40 | local_type  # Definition message
            f.write(struct.pack('B', definition_header))
            f.write(struct.pack('B', 0))  # reserved
            f.write(struct.pack('B', 0))  # architecture (little endian)
            f.write(struct.pack('<H', global_type))  # global message number
            f.write(struct.pack('B', len(fields)))  # number of fields
            
            # Write field definitions
            for field_num, value in fields.items():
                f.write(struct.pack('B', field_num))  # field definition number
                if isinstance(value, bytes):
                    f.write(struct.pack('B', len(value)))  # size
                    f.write(struct.pack('B', 7))  # base type (string)
                elif isinstance(value, int):
                    if value < 256:
                        f.write(struct.pack('B', 1))  # size
                        f.write(struct.pack('B', 2))  # base type (uint8)
                    elif value < 65536:
                        f.write(struct.pack('B', 2))  # size
                        f.write(struct.pack('B', 132))  # base type (uint16)
                    else:
                        f.write(struct.pack('B', 4))  # size
                        f.write(struct.pack('B', 134))  # base type (uint32)
        
        # Write data message
        local_type = self.local_message_types[global_type]
        data_header = local_type  # Data message
        f.write(struct.pack('B', data_header))
        
        # Write field data
        for field_num, value in fields.items():
            if isinstance(value, bytes):
                f.write(value)
            elif isinstance(value, int):
                if value < 256:
                    f.write(struct.pack('B', value))
                elif value < 65536:
                    f.write(struct.pack('<H', value))
                else:
                    f.write(struct.pack('<I', value))

def parse_zwo_file(zwo_path: str) -> Dict[str, Any]:
    """Parse ZWO file and extract workout information"""
    tree = ET.parse(zwo_path)
    root = tree.getroot()
    
    workout_info = {
        'name': root.find('name').text if root.find('name') is not None else 'Workout',
        'description': root.find('description').text if root.find('description') is not None else '',
        'segments': []
    }
    
    workout_element = root.find('workout')
    if workout_element is None:
        return workout_info
    
    for element in workout_element:
        if element.tag == 'Warmup':
            duration = int(element.get('Duration', 0))
            power_low = float(element.get('PowerLow', 0.5))
            power_high = float(element.get('PowerHigh', 0.75))
            workout_info['segments'].append({
                'type': 'warmup',
                'duration': duration,
                'power_start': power_low,
                'power_end': power_high
            })
        
        elif element.tag == 'SteadyState':
            duration = int(element.get('Duration', 0))
            power = float(element.get('Power', 0.5))
            workout_info['segments'].append({
                'type': 'steady',
                'duration': duration,
                'power': power
            })
        
        elif element.tag == 'Cooldown':
            duration = int(element.get('Duration', 0))
            power_low = float(element.get('PowerLow', 0.5))
            power_high = float(element.get('PowerHigh', 0.45))
            workout_info['segments'].append({
                'type': 'cooldown',
                'duration': duration,
                'power_start': power_low,
                'power_end': power_high
            })
        elif element.tag == 'IntervalsT':
            repeat = int(element.get('Repeat', 1))
            on_duration = int(element.get('OnDuration', 60))
            off_duration = int(element.get('OffDuration', 60))
            on_power = float(element.get('OnPower', 0.9))
            off_power = float(element.get('OffPower', 0.5))
            
            for i in range(repeat):
                # Add work interval
                workout_info['segments'].append({
                    'type': 'interval_work',
                    'duration': on_duration,
                    'power': on_power
                })
                # Add rest interval (except after last repeat)
                if i < repeat - 1 or off_duration > 0:
                    workout_info['segments'].append({
                        'type': 'interval_rest',
                        'duration': off_duration,
                        'power': off_power
                    })
    
    return workout_info

def create_fit_file(segments: List[Dict], output_path: str, workout_name: str = "Workout", ftp: int = 250):
    """Create FIT workout file from segments"""
    
    fit_writer = FITFileWriter()
    
    # Add file ID message
    fit_writer.add_file_id_message()
    
    # Add workout message
    workout_idx = fit_writer.add_workout_message(workout_name)
    
    # Add workout steps
    step_count = 0
    for segment in segments:
        duration_type = 0  # time-based
        duration_value = segment['duration']  # in seconds
        
        # Determine target type and value
        if segment['type'] == 'warmup':
            # For warmup, use average power
            avg_power = int((segment['power_start'] + segment['power_end']) / 2 * ftp)
            target_type = 1  # power target
            target_value = avg_power
            intensity = 2  # warmup
        
        elif segment['type'] == 'steady':
            power = int(segment['power'] * ftp)
            target_type = 1  # power target
            target_value = power
            intensity = 0  # active
        
        elif segment['type'] == 'interval_work':
            power = int(segment['power'] * ftp)
            target_type = 1  # power target
            target_value = power
            intensity = 0  # active
        
        elif segment['type'] == 'interval_rest':
            power = int(segment['power'] * ftp)
            target_type = 1  # power target
            target_value = power
            intensity = 1  # rest
        
        else:
            continue
        
        fit_writer.add_workout_step(duration_type, duration_value, target_type, target_value, intensity)
        step_count += 1
    
    # Update number of valid steps
    if workout_idx < len(fit_writer.messages):
        fit_writer.messages[workout_idx]['fields'][6] = step_count
    
    # Write FIT file
    fit_writer.write_fit_file(output_path)

def convert_zwo_to_fit(zwo_path: str, fit_path: str = None, ftp: int = 250):
    """Convert a single ZWO file to FIT format"""
    if fit_path is None:
        fit_path = zwo_path.replace('.zwo', '.fit')
    
    try:
        workout_info = parse_zwo_file(zwo_path)
        create_fit_file(workout_info['segments'], fit_path, workout_info['name'], ftp)
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
    # Convert single file
    # convert_zwo_to_fit("pacing1.zwo", "pacing1.fit", ftp=250)
    
    # Batch convert all files in current directory
    batch_convert_zwo_to_fit(".", ftp=250)
    
    # Batch convert with specific input/output directories
    # batch_convert_zwo_to_fit("./zwo_files", "./fit_files", ftp=250)