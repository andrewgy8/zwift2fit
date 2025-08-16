"""
ZWO (Zwift Workout) file parser module.

This module provides functionality to parse Zwift workout files (.zwo) and convert them
into structured Python data objects representing workout segments.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class WorkoutSegment:
    """Represents a single workout segment"""
    type: str  # 'warmup', 'steady', 'cooldown', 'interval_work', 'interval_rest', 'repeat_interval'
    duration: int  # Duration in seconds
    power: Optional[float] = None  # Single power value as fraction of FTP
    power_start: Optional[float] = None  # Start power for ramps (fraction of FTP)
    power_end: Optional[float] = None  # End power for ramps (fraction of FTP)
    repeat_count: Optional[int] = None  # Number of repetitions for repeat segments
    target_type: Optional[int] = None  # FIT target type (4=power, 8=open)
    repeat_until_step: Optional[int] = None  # Step index to repeat until


@dataclass
class Workout:
    """Represents a complete workout"""
    name: str
    description: str
    segments: List[WorkoutSegment]
    
    @property
    def total_duration(self) -> int:
        """Calculate total workout duration in seconds"""
        return sum(segment.duration for segment in self.segments if segment.duration)
    
    @property
    def segment_count(self) -> int:
        """Get number of segments in the workout"""
        return len(self.segments)


def _get_text_or_default(element: Optional[ET.Element], default: str) -> str:
    """Get text content of an element or return default"""
    return element.text if element is not None and element.text else default


def _parse_warmup(element: ET.Element) -> WorkoutSegment:
    """Parse a Warmup element"""
    duration = int(element.get('Duration', 0))
    power_low = float(element.get('PowerLow', 0.5))
    power_high = float(element.get('PowerHigh', 0.75))
    
    return WorkoutSegment(
        type='warmup',
        duration=duration,
        power_start=power_low,
        power_end=power_high
    )


def _parse_steady_state(element: ET.Element) -> WorkoutSegment:
    """Parse a SteadyState element"""
    duration = int(element.get('Duration', 0))
    power = float(element.get('Power', 0.5))
    
    return WorkoutSegment(
        type='steady',
        duration=duration,
        power=power
    )


def _parse_cooldown(element: ET.Element) -> WorkoutSegment:
    """Parse a Cooldown element"""
    duration = int(element.get('Duration', 0))
    power_low = float(element.get('PowerLow', 0.5))
    power_high = float(element.get('PowerHigh', 0.45))
    
    return WorkoutSegment(
        type='cooldown',
        duration=duration,
        power_start=power_low,
        power_end=power_high
    )


def _parse_intervals_t(element: ET.Element) -> List[WorkoutSegment]:
    """Parse an IntervalsT element into individual work/rest segments"""
    repeat = int(element.get('Repeat', 1))
    on_duration = int(element.get('OnDuration', 60))
    off_duration = int(element.get('OffDuration', 60))
    on_power = float(element.get('OnPower', 0.9))
    off_power = float(element.get('OffPower', 0.5))
    
    segments = []
    
    # Create individual work and rest segments for each repetition
    for i in range(repeat):
        # Add work interval
        segments.append(WorkoutSegment(
            type='interval_work',
            duration=on_duration,
            power=on_power
        ))
        
        # Add rest interval (except after last repeat if off_duration is 0)
        if i < repeat - 1 or off_duration > 0:
            segments.append(WorkoutSegment(
                type='interval_rest',
                duration=off_duration,
                power=off_power
            ))
    
    return segments


def _parse_workout_elements(root: ET.Element) -> List[WorkoutSegment]:
    """Parse workout elements from the XML root"""
    segments = []
    
    workout_element = root.find('workout')
    if workout_element is None:
        return segments
    
    for element in workout_element:
        if element.tag == 'Warmup':
            segments.append(_parse_warmup(element))
        elif element.tag == 'SteadyState':
            segments.append(_parse_steady_state(element))
        elif element.tag == 'Cooldown':
            segments.append(_parse_cooldown(element))
        elif element.tag == 'IntervalsT':
            segments.extend(_parse_intervals_t(element))
    
    return segments


def parse_zwo_to_workout(zwo_path: str) -> Workout:
    """
    Parse a ZWO file and return a Workout object.
    
    Args:
        zwo_path: Path to the .zwo file
        
    Returns:
        Workout object containing parsed segments
        
    Raises:
        FileNotFoundError: If the ZWO file doesn't exist
        ET.ParseError: If the XML is malformed
        ValueError: If required elements are missing
    """
    try:
        tree = ET.parse(zwo_path)
        root = tree.getroot()
        
        # Extract workout metadata
        name = _get_text_or_default(root.find('name'), 'Workout')
        description = _get_text_or_default(root.find('description'), '')
        
        # Parse workout segments
        segments = _parse_workout_elements(root)
        
        return Workout(
            name=name,
            description=description,
            segments=segments
        )
        
    except ET.ParseError as e:
        raise ET.ParseError(f"Invalid XML in ZWO file {zwo_path}: {e}")
    except FileNotFoundError:
        raise FileNotFoundError(f"ZWO file not found: {zwo_path}")


def parse_zwo_to_segments(zwo_path: str) -> List[WorkoutSegment]:
    """
    Parse a ZWO file and return a list of WorkoutSegment objects.
    
    Args:
        zwo_path: Path to the .zwo file
        
    Returns:
        List of WorkoutSegment objects
    """
    workout = parse_zwo_to_workout(zwo_path)
    return workout.segments


