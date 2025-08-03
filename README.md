# Zwift2Fit

A Python script to convert Zwift workout files (.zwo) to FIT workout files (.fit) for use with cycling computers and training platforms.

## Overview

This tool allows you to convert Zwift's proprietary workout format into the industry-standard FIT format, making your Zwift workouts compatible with Garmin, Wahoo, and other cycling computers that support structured workouts.

## Features

- **Batch Processing**: Convert hundreds or thousands of files at once
- **Complete Workout Support**: Handles all Zwift workout segments (Warmup, SteadyState, IntervalsT)
- **Power Zone Conversion**: Converts relative power zones to absolute watts based on your FTP
- **No Dependencies**: Uses only Python standard library
- **Error Handling**: Continues processing even if individual files fail
- **Preserves Metadata**: Maintains workout names and structure

## Supported Workout Elements

| ZWO Element | Description | FIT Conversion |
|-------------|-------------|----------------|
| `Warmup` | Progressive power ramp | Warmup step with average target power |
| `SteadyState` | Fixed power segment | Active step with target power |
| `IntervalsT` | Repeated work/rest intervals | Separate work and rest steps |

## Installation

No additional packages required! The script uses only Python's standard library.

```bash
# Clone or download the script
# No pip install needed
```

## Usage

### Single File Conversion

```python
from zwo_to_fit_converter import convert_zwo_to_fit

# Convert with default 250W FTP
convert_zwo_to_fit("my_workout.zwo")

# Convert with custom FTP and output path
convert_zwo_to_fit("my_workout.zwo", "output/my_workout.fit", ftp=275)
```

### Batch Conversion

```python
from zwo_to_fit_converter import batch_convert_zwo_to_fit

# Convert all .zwo files in current directory
batch_convert_zwo_to_fit(".", ftp=250)

# Convert with specific input/output directories
batch_convert_zwo_to_fit("./zwift_workouts", "./fit_files", ftp=275)
```

### Command Line Usage

```bash
python zwo_to_fit_converter.py
```

## Configuration

### FTP Setting

The script converts relative power zones (e.g., 0.88 = 88% FTP) to absolute watts. Set your FTP appropriately:

```python
# For a cyclist with 250W FTP
batch_convert_zwo_to_fit("./workouts", ftp=250)

# For a cyclist with 300W FTP  
batch_convert_zwo_to_fit("./workouts", ftp=300)
```

### File Paths

```python
# Same directory (overwrites with .fit extension)
convert_zwo_to_fit("workout.zwo")

# Specific output path
convert_zwo_to_fit("workout.zwo", "converted/workout.fit")

# Batch with different directories
batch_convert_zwo_to_fit("./zwo_files", "./fit_files")
```

## Example Workout Structure

**Input (.zwo file):**
```xml
<workout_file>
  <name>Pacing1</name>
  <workout>
    <Warmup Duration="420" PowerLow="0.5" PowerHigh="0.75" />
    <SteadyState Duration="180" Power="0.88" />
    <IntervalsT Repeat="5" OnDuration="60" OffDuration="60" OnPower="0.9" OffPower="0.7"/>
  </workout>
</workout_file>
```

**Output (.fit file):**
- Warmup: 7 minutes ramping from 125W to 188W (avg 156W)
- Steady: 3 minutes at 220W (88% of 250W FTP)
- Intervals: 5x (1 min at 225W / 1 min at 175W)

## File Structure

```
your_project/
├── zwo_to_fit_converter.py    # Main script
├── zwift_workouts/            # Input directory
│   ├── workout1.zwo
│   ├── workout2.zwo
│   └── ...
└── fit_files/                 # Output directory
    ├── workout1.fit
    ├── workout2.fit
    └── ...
```

## Error Handling

The script includes robust error handling:

- **Invalid XML**: Skips corrupted .zwo files and continues
- **Missing Elements**: Uses sensible defaults for missing workout data
- **File I/O Errors**: Reports errors but continues batch processing
- **Progress Reporting**: Shows conversion status for each file

## Troubleshooting

### Common Issues

**"No .zwo files found"**
- Check the input directory path
- Ensure files have .zwo extension
- Verify file permissions

**"Error converting [file]"**
- Check if the .zwo file is valid XML
- Ensure the workout structure follows Zwift format
- Try converting the file individually for detailed error info

**FIT file not recognized by device**
- Verify your FTP setting is reasonable (50-500W typically)
- Check that workout duration isn't too long for your device
- Some older devices may have limited FIT workout support

### Validation

To verify conversion success:

1. Check that .fit files are created with reasonable file sizes
2. Import a test file into your cycling computer or training software
3. Verify power targets match expected values based on your FTP

## Technical Details

### FIT File Structure

The converter creates FIT files with these message types:
- **FILE_ID**: Identifies the file as a workout
- **WORKOUT**: Contains workout metadata (name, sport)
- **WORKOUT_STEP**: Individual workout segments with duration and power targets

### Power Zone Mapping

| Zwift Zone | Typical % FTP | Description |
|------------|---------------|-------------|
| 0.5 | 50% | Recovery |
| 0.7 | 70% | Endurance |
| 0.88 | 88% | Tempo/Sweet Spot |
| 0.9 | 90% | Threshold |
| 1.0+ | 100%+ | VO2 Max/Neuromuscular |

## Contributing

Feel free to submit issues, feature requests, or pull requests. Common enhancement ideas:

- Support for additional ZWO elements (Cooldown, Ramp, etc.)
- Heart rate zone targets
- Cadence targets
- GUI interface
- More sophisticated FIT file validation

## License

This project is provided as-is for personal use. The FIT file format is owned by Garmin/ANT+.

## Compatibility

- **Python**: 3.6+
- **Zwift**: All .zwo workout file versions
- **FIT Devices**: Garmin Edge, Wahoo ELEMNT, and other FIT-compatible cycling computers
- **Platforms**: Windows, macOS, Linux