"""
FIT workout visualizer using official Garmin FIT Python SDK
Updated to use garmin-fit-sdk instead of fitparse for better compatibility and official support
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Any, Tuple
import argparse
import os

try:
    from garmin_fit_sdk import Decoder, Stream

    GARMIN_SDK_AVAILABLE = True
except ImportError:
    GARMIN_SDK_AVAILABLE = False
    print(
        "Warning: garmin-fit-sdk not installed. Install with: pip install garmin-fit-sdk"
    )


class GarminFITWorkoutVisualizer:
    """Visualize FIT workout files using official Garmin SDK with power profiles and step analysis"""

    def __init__(self, ftp: int = 250):
        self.ftp = ftp
        self.intensity_colors = {
            0: "#FF6B6B",  # Active - Red
            1: "#4ECDC4",  # Rest - Teal
            2: "#45B7D1",  # Warmup - Blue
            3: "#96CEB4",  # Cooldown - Green
            4: "#FFEAA7",  # Recovery - Yellow
            "active": "#FF6B6B",  # Active - Red
            "rest": "#4ECDC4",  # Rest - Teal
            "warmup": "#45B7D1",  # Warmup - Blue
            "cooldown": "#96CEB4",  # Cooldown - Green
            "recovery": "#FFEAA7",  # Recovery - Yellow
        }
        self.intensity_names = {
            0: "Active",
            1: "Rest",
            2: "Warmup",
            3: "Cooldown",
            4: "Recovery",
            "active": "Active",
            "rest": "Rest",
            "warmup": "Warmup",
            "cooldown": "Cooldown",
            "recovery": "Recovery",
        }

    def parse_fit_workout(self, fit_path: str) -> Dict[str, Any]:
        """Parse FIT workout file using Garmin SDK and extract workout information"""
        if not GARMIN_SDK_AVAILABLE:
            raise ImportError(
                "garmin-fit-sdk library is required. Install with: pip install garmin-fit-sdk"
            )

        try:
            # Create stream and decoder
            stream = Stream.from_file(fit_path)
            decoder = Decoder(stream)

            # Read all messages
            messages, errors = decoder.read()

            # Handle any errors
            if errors:
                print(f"Decoder errors: {errors}")

            workout_info = {
                "name": "FIT Workout",
                "sport": "cycling",
                "steps": [],
                "total_duration": 0,
                "source_file": os.path.basename(fit_path),
                "file_id": None,
                "capabilities": None,
            }

            # Process messages by type
            # Note: Garmin SDK returns messages with plural names (e.g., 'workout_mesgs')
            for message_type, message_list in messages.items():
                if message_type == "workout_mesgs":
                    for msg in message_list:
                        # Messages are dicts, not objects with attributes
                        if "wkt_name" in msg and msg["wkt_name"]:
                            workout_info["name"] = msg["wkt_name"]
                        if "sport" in msg:
                            workout_info["sport"] = msg["sport"]
                        if "capabilities" in msg:
                            workout_info["capabilities"] = msg["capabilities"]
                        if "num_valid_steps" in msg:
                            expected_steps = msg["num_valid_steps"]
                            print(f"Expected workout steps: {expected_steps}")

                elif message_type == "workout_step_mesgs":
                    for msg in message_list:
                        step_info = {
                            "step_index": msg.get("message_index"),
                            "step_name": msg.get("wkt_step_name"),
                            "duration_type": msg.get("duration_type"),
                            "duration_value": msg.get(
                                "duration_time"
                            ),  # Note: duration_time for time-based
                            "target_type": msg.get("target_type"),
                            "target_value": msg.get("target_value"),
                            "custom_target_low": msg.get("custom_target_power_low"),
                            "custom_target_high": msg.get("custom_target_power_high"),
                            "intensity": msg.get("intensity", 0),
                            "target_power_zone": msg.get("target_power_zone"),
                        }

                        # Clean up string values
                        if step_info["step_name"] and isinstance(
                            step_info["step_name"], str
                        ):
                            step_info["step_name"] = step_info["step_name"].strip(
                                "\x00"
                            )

                        workout_info["steps"].append(step_info)

                elif message_type == "file_id_mesgs":
                    for msg in message_list:
                        workout_info["file_id"] = {
                            "type": msg.get("type"),
                            "manufacturer": msg.get("manufacturer"),
                            "product": msg.get("product"),
                            "serial_number": msg.get("serial_number"),
                            "time_created": msg.get("time_created"),
                        }

            # Sort steps by index and process
            workout_info["steps"].sort(
                key=lambda x: x.get("step_index", 0)
                if x.get("step_index") is not None
                else 999
            )

            # Calculate segments for visualization
            segments = []
            current_time = 0

            for i, step in enumerate(workout_info["steps"]):
                # Determine duration - use duration_time field which is already in seconds
                duration = 0
                if step["duration_type"] == "repeat_until_steps_cmplt":
                    # Skip repeat markers - these don't represent actual workout segments
                    continue
                elif step.get("duration_time") is not None:
                    # duration_time is already in seconds
                    duration = step["duration_time"]
                elif step.get("duration_value") is not None:
                    # duration_value is already in seconds for Garmin SDK
                    duration = step["duration_value"]
                else:
                    duration = 60  # Default 1 minute

                # Skip invalid duration steps
                if duration <= 0:
                    continue

                # Determine power target
                power_target = None
                power_range = None

                # Check for custom power targets first (most specific)
                if (
                    step["custom_target_low"] is not None
                    and step["custom_target_high"] is not None
                ):
                    power_range = (
                        step["custom_target_low"],
                        step["custom_target_high"],
                    )
                    power_target = (
                        step["custom_target_low"] + step["custom_target_high"]
                    ) / 2
                elif step["target_value"] is not None:
                    power_target = step["target_value"]
                else:
                    # Default to moderate effort if no power target
                    power_target = self.ftp * 0.7

                # Create segment info
                segment = {
                    "step_index": i + 1,
                    "name": step["step_name"] or f"Step {i + 1}",
                    "start_time": current_time,
                    "duration": duration,
                    "power_target": power_target,
                    "power_range": power_range,
                    "intensity": step["intensity"]
                    if step["intensity"] is not None
                    else 0,
                    "target_type": step["target_type"],
                    "duration_type": step["duration_type"],
                }

                segments.append(segment)
                current_time += duration

            workout_info["segments"] = segments
            workout_info["total_duration"] = current_time

            print(
                f"Parsed {len(segments)} valid segments from {len(workout_info['steps'])} total steps"
            )

            return workout_info

        except Exception as e:
            print(f"Error parsing FIT file {fit_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            return {
                "name": "Error",
                "sport": "cycling",
                "steps": [],
                "segments": [],
                "total_duration": 0,
                "source_file": os.path.basename(fit_path),
            }

    def create_power_profile(
        self, segments: List[Dict]
    ) -> Tuple[np.ndarray, np.ndarray, List[Dict]]:
        """Create time series data for power profile with range information"""
        if not segments:
            return np.array([0]), np.array([0]), []

        time_points = []
        power_points = []
        range_info = []

        for segment in segments:
            start_time = segment["start_time"]
            end_time = start_time + segment["duration"]

            # Add start and end points
            time_points.extend([start_time, end_time])

            if segment["power_target"]:
                power_points.extend([segment["power_target"], segment["power_target"]])
            else:
                # Default power if no target specified
                default_power = self.ftp * 0.5
                power_points.extend([default_power, default_power])

            # Store range information for visualization
            if segment["power_range"]:
                range_info.append(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "low_power": segment["power_range"][0],
                        "high_power": segment["power_range"][1],
                        "intensity": segment["intensity"],
                    }
                )

        return np.array(time_points), np.array(power_points), range_info

    def plot_fit_workout(
        self,
        workout_info: Dict[str, Any],
        save_path: str = None,
        show_plot: bool = True,
    ):
        """Display FIT workout visualization and details"""
        if not workout_info["segments"]:
            print("No segments found")
            return

        # Print workout summary
        print(f"\n{workout_info['name']} (FIT - Garmin SDK)")
        total_duration = int(workout_info["total_duration"])
        print(f"Duration: {total_duration // 60}:{total_duration % 60:02d}")
        print(f"Steps: {len(workout_info['segments'])}")
        print(f"Source: {workout_info['source_file']}")

        # Print file ID info if available
        if workout_info.get("file_id"):
            file_id = workout_info["file_id"]
            print(f"File Type: {file_id.get('type', 'unknown')}")
            print(f"Manufacturer: {file_id.get('manufacturer', 'unknown')}")
            if file_id.get("time_created"):
                print(f"Created: {file_id['time_created']}")

        if show_plot:
            # Create figure with power profile and step timeline
            fig, (ax_power, ax_steps) = plt.subplots(
                2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2, 1]}
            )

            # Create power profile data
            time_data, power_data, range_info = self.create_power_profile(
                workout_info["segments"]
            )
            time_minutes = time_data / 60

            # Plot power profile
            ax_power.plot(
                time_minutes,
                power_data,
                "k-",
                linewidth=2.5,
                label="Target Power",
                zorder=3,
            )

            # Add power ranges as shaded areas with intensity colors
            for range_data in range_info:
                start_min = range_data["start_time"] / 60
                end_min = range_data["end_time"] / 60
                intensity_color = self.intensity_colors.get(
                    range_data["intensity"], "#808080"
                )

                ax_power.fill_between(
                    [start_min, end_min],
                    [range_data["low_power"], range_data["low_power"]],
                    [range_data["high_power"], range_data["high_power"]],
                    alpha=0.3,
                    color=intensity_color,
                    zorder=2,
                )

            # Add step blocks with different colors based on intensity
            for segment in workout_info["segments"]:
                start_min = segment["start_time"] / 60
                end_min = (segment["start_time"] + segment["duration"]) / 60
                intensity_color = self.intensity_colors.get(
                    segment["intensity"], "#808080"
                )

                if segment["power_target"]:
                    segment["power_target"]
                else:
                    self.ftp * 0.5

                ax_power.axvspan(
                    start_min, end_min, alpha=0.2, color=intensity_color, zorder=1
                )

            # Add FTP reference line
            ax_power.axhline(
                y=self.ftp,
                color="red",
                linestyle="--",
                alpha=0.7,
                label=f"FTP ({self.ftp}W)",
                zorder=1,
            )

            # Format power chart
            ax_power.set_ylabel("Power (watts)", fontsize=12)
            ax_power.set_title(
                f"{workout_info['name']} - Power Profile (Garmin SDK)",
                fontsize=14,
                fontweight="bold",
            )
            ax_power.grid(True, alpha=0.3)
            ax_power.legend()

            if len(power_data) > 0:
                max_power = max(power_data)
                if range_info:
                    max_power = max(
                        max_power, max([r["high_power"] for r in range_info])
                    )
                ax_power.set_ylim(0, max_power * 1.1)

            # Create step timeline
            colors = []
            labels = []
            durations = []
            starts = []

            for segment in workout_info["segments"]:
                intensity_color = self.intensity_colors.get(
                    segment["intensity"], "#808080"
                )
                colors.append(intensity_color)

                # Create informative labels
                label = segment["name"]
                if segment["power_target"]:
                    label += f" ({segment['power_target']:.0f}W)"

                labels.append(label)
                durations.append(segment["duration"] / 60)
                starts.append(segment["start_time"] / 60)

            # Plot step timeline
            bars = ax_steps.barh(
                range(len(workout_info["segments"])),
                durations,
                left=starts,
                color=colors,
                alpha=0.8,
                edgecolor="black",
                linewidth=0.5,
            )

            # Add step labels
            for i, (bar, label) in enumerate(zip(bars, labels)):
                width = bar.get_width()
                if width > 1:  # Only show label if segment is wide enough (1 minute)
                    ax_steps.text(
                        bar.get_x() + width / 2,
                        bar.get_y() + bar.get_height() / 2,
                        f"Step {i + 1}",
                        ha="center",
                        va="center",
                        fontsize=8,
                        fontweight="bold",
                        color="white",
                    )

            ax_steps.set_xlabel("Time (minutes)", fontsize=12)
            ax_steps.set_ylabel("Steps", fontsize=12)
            ax_steps.set_title("Workout Steps Timeline", fontsize=12, fontweight="bold")
            ax_steps.set_yticks(range(len(workout_info["segments"])))
            ax_steps.set_yticklabels(
                [f"Step {i + 1}" for i in range(len(workout_info["segments"]))],
                fontsize=8,
            )
            ax_steps.grid(True, alpha=0.3, axis="x")
            ax_steps.invert_yaxis()  # Top to bottom ordering

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches="tight")
                print(f"FIT workout visualization saved to: {save_path}")

            plt.show()

        # Print detailed step information
        print("\nSTEP DETAILS:")
        print("-" * 80)

        for i, segment in enumerate(workout_info["segments"]):
            intensity_name = self.intensity_names.get(segment["intensity"], "Unknown")
            duration = int(segment["duration"])
            duration_str = f"{duration // 60}:{duration % 60:02d}"

            if segment["power_range"]:
                power_str = (
                    f"{segment['power_range'][0]:.0f}-{segment['power_range'][1]:.0f}W"
                )
            elif segment["power_target"]:
                power_str = f"{segment['power_target']:.0f}W"
            else:
                power_str = "No target"

            duration_type = segment.get("duration_type", "time")
            print(
                f"{i + 1:2d}. {segment['name']:<20} | {duration_str} | {power_str:<12} | {intensity_name:<8} | {duration_type}"
            )

        print("-" * 80)

    def debug_fit_messages(self, fit_path: str):
        """Debug function to print all messages in a FIT file"""
        if not GARMIN_SDK_AVAILABLE:
            print("Garmin SDK not available")
            return

        try:
            stream = Stream.from_file(fit_path)
            decoder = Decoder(stream)
            messages, errors = decoder.read()

            print(f"=== DEBUG: {fit_path} ===")
            print(f"Errors: {errors}")
            print(f"Message types found: {list(messages.keys())}")

            for message_type, message_list in messages.items():
                print(f"\n{message_type} ({len(message_list)} messages):")
                for i, msg in enumerate(message_list):
                    print(f"  Message {i}:")
                    if isinstance(msg, dict):
                        for key, value in msg.items():
                            if value is not None:
                                print(f"    {key}: {value}")
                    else:
                        # Fallback for non-dict messages
                        for attr in dir(msg):
                            if not attr.startswith("_") and not callable(
                                getattr(msg, attr)
                            ):
                                value = getattr(msg, attr)
                                if value is not None:
                                    print(f"    {attr}: {value}")

        except Exception as e:
            print(f"Debug error: {e}")
            import traceback

            traceback.print_exc()


def main():
    if not GARMIN_SDK_AVAILABLE:
        print(
            "Error: garmin-fit-sdk library is required. Install with: pip install garmin-fit-sdk"
        )
        return

    parser = argparse.ArgumentParser(
        description="Visualize FIT workout files using Garmin SDK"
    )
    parser.add_argument("files", nargs="+", help="FIT file(s) to visualize")
    parser.add_argument(
        "--ftp",
        type=int,
        default=250,
        help="Functional Threshold Power in watts (default: 250)",
    )
    parser.add_argument("--output", "-o", help="Save visualization to file (PNG/PDF)")
    parser.add_argument("--no-show", action="store_true", help="Don't display the plot")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug information about FIT messages",
    )

    args = parser.parse_args()

    visualizer = GarminFITWorkoutVisualizer(ftp=args.ftp)

    for fit_file in args.files:
        if not os.path.exists(fit_file):
            print(f"File not found: {fit_file}")
            continue

        print(f"Analyzing: {fit_file}")

        if args.debug:
            visualizer.debug_fit_messages(fit_file)
            continue

        workout_info = visualizer.parse_fit_workout(fit_file)

        if workout_info["segments"]:
            save_path = args.output
            if len(args.files) > 1 and args.output:
                # Multiple files, modify output name
                base, ext = os.path.splitext(args.output)
                save_path = (
                    f"{base}_{os.path.basename(fit_file).replace('.fit', '')}{ext}"
                )

            visualizer.plot_fit_workout(
                workout_info, save_path=save_path, show_plot=not args.no_show
            )
        else:
            print(f"No valid segments found in {fit_file}")


if __name__ == "__main__":
    main()


# Example usage:
# python fitfile_viewer_garmin.py workout.fit --ftp 275
# python fitfile_viewer_garmin.py converted_workout.fit --output fit_viz.png --debug
# python fitfile_viewer_garmin.py pacing1.fit --debug
