import os
import glob
from zwo_parser import parse_zwo_to_workout
from fit_writer import FITFileWriter

# FIT file writing is now handled by the fit_writer module


def create_fit_file(
    segments, output_path: str, workout_name: str = "Workout", ftp: int = 250
):
    """Create FIT workout file from segments (legacy wrapper)"""

    if not segments:
        print("No segments to convert")
        return

    fit_writer = FITFileWriter()

    try:
        crc = fit_writer.create_workout_file(segments, output_path, workout_name, ftp)
        print(f"Successfully created FIT file: {output_path}")
        print(f"FIT file written: CRC: {crc:04X}")
    except Exception as e:
        print(f"Error creating FIT file: {e}")
        raise


def convert_zwo_to_fit(zwo_path: str, fit_path: str = None, ftp: int = 250):
    """Convert a single ZWO file to FIT format"""
    if fit_path is None:
        fit_path = zwo_path.replace(".zwo", ".fit")

    try:
        workout = parse_zwo_to_workout(zwo_path)
        if not workout.segments:
            print(f"Error converting {zwo_path}: No segments to convert")
            return False
        create_fit_file(workout.segments, fit_path, workout.name, ftp)
        print(f"Converted: {zwo_path} -> {fit_path}")
        return True
    except Exception as e:
        print(f"Error converting {zwo_path}: {str(e)}")
        return False


def batch_convert_zwo_to_fit(
    input_directory: str, output_directory: str = None, ftp: int = 250
):
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
        fit_filename = filename.replace(".zwo", ".fit")
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
