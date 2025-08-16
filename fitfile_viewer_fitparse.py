import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Any, Tuple
import argparse
import os

try:
    from fitparse import FitFile

    FITPARSE_AVAILABLE = True
except ImportError:
    FITPARSE_AVAILABLE = False
    print("Warning: fitparse not installed. Install with: pip install fitparse")


class FITWorkoutVisualizer:
    """Visualize FIT workout files with power profiles and step analysis"""

    def __init__(self, ftp: int = 250):
        self.ftp = ftp
        self.intensity_colors = {
            0: "#FF6B6B",  # Active - Red
            1: "#4ECDC4",  # Rest - Teal
            2: "#45B7D1",  # Warmup - Blue
            3: "#96CEB4",  # Cooldown - Green
            4: "#FFEAA7",  # Recovery - Yellow
        }
        self.intensity_names = {
            0: "Active",
            1: "Rest",
            2: "Warmup",
            3: "Cooldown",
            4: "Recovery",
        }

    def parse_fit_workout(self, fit_path: str) -> Dict[str, Any]:
        """Parse FIT workout file and extract workout information"""
        if not FITPARSE_AVAILABLE:
            raise ImportError(
                "fitparse library is required. Install with: pip install fitparse"
            )

        try:
            fitfile = FitFile(fit_path)

            workout_info = {
                "name": "FIT Workout",
                "sport": "cycling",
                "steps": [],
                "total_duration": 0,
                "source_file": os.path.basename(fit_path),
            }

            # Parse workout messages
            for record in fitfile.get_messages(["workout", "workout_step"]):
                if record.name == "workout":
                    for field in record.fields:
                        if field.name == "wkt_name" and field.value:
                            workout_info["name"] = (
                                field.value.decode("utf-8")
                                if isinstance(field.value, bytes)
                                else str(field.value)
                            )
                        elif field.name == "sport":
                            workout_info["sport"] = field.value

                elif record.name == "workout_step":
                    step_info = {
                        "step_index": None,
                        "step_name": None,
                        "duration_type": None,
                        "duration_value": None,
                        "target_type": None,
                        "target_value": None,
                        "custom_target_low": None,
                        "custom_target_high": None,
                        "intensity": 0,
                    }

                    for field in record.fields:
                        if field.name == "message_index":
                            step_info["step_index"] = field.value
                        elif field.name == "wkt_step_name" and field.value:
                            name = (
                                field.value.decode("utf-8")
                                if isinstance(field.value, bytes)
                                else str(field.value)
                            )
                            step_info["step_name"] = name
                        elif field.name == "duration_type":
                            step_info["duration_type"] = field.value
                        elif field.name == "duration_time":  # Correct field name
                            step_info["duration_value"] = field.value
                        elif field.name == "target_type":
                            step_info["target_type"] = field.value
                        elif field.name == "target_value":
                            step_info["target_value"] = field.value
                        elif (
                            field.name == "custom_target_power_low"
                        ):  # Correct field name
                            step_info["custom_target_low"] = field.value
                        elif (
                            field.name == "custom_target_power_high"
                        ):  # Correct field name
                            step_info["custom_target_high"] = field.value
                        elif field.name == "intensity":
                            step_info["intensity"] = (
                                field.value if field.value is not None else 0
                            )

                    workout_info["steps"].append(step_info)

            # Sort steps by index and process
            workout_info["steps"].sort(key=lambda x: x.get("step_index", 0))

            # Calculate segments for visualization
            segments = []
            current_time = 0

            for i, step in enumerate(workout_info["steps"]):
                # Determine duration
                duration = 0
                if (
                    step["duration_type"] == "time" or step["duration_type"] == 0
                ):  # Time-based
                    duration = step["duration_value"] if step["duration_value"] else 60
                elif (
                    step["duration_type"] == "distance" or step["duration_type"] == 1
                ):  # Distance-based
                    duration = 300  # Default 5 minutes for distance-based steps
                else:
                    duration = 60  # Default 1 minute for unknown types

                # Determine power target
                power_target = None
                power_range = None

                if (
                    step["target_type"] == "power" or step["target_type"] == 1
                ):  # Power target
                    if step["custom_target_low"] and step["custom_target_high"]:
                        # Power range - use values directly (no scaling needed)
                        power_range = (
                            step["custom_target_low"],
                            step["custom_target_high"],
                        )
                        power_target = (
                            step["custom_target_low"] + step["custom_target_high"]
                        ) / 2
                    elif step["target_value"]:
                        power_target = step["target_value"]
                    else:
                        # Default to moderate effort if no power target
                        power_target = self.ftp * 0.7
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
                    "intensity": step["intensity"],
                    "target_type": step["target_type"],
                }

                segments.append(segment)
                current_time += duration

            workout_info["segments"] = segments
            workout_info["total_duration"] = current_time

            return workout_info

        except Exception as e:
            print(f"Error parsing FIT file {fit_path}: {str(e)}")
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
        print(f"\n{workout_info['name']} (FIT)")
        total_duration = int(workout_info["total_duration"])
        print(f"Duration: {total_duration // 60}:{total_duration % 60:02d}")
        print(f"Steps: {len(workout_info['segments'])}")
        print(f"Source: {workout_info['source_file']}")

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
                f"{workout_info['name']} - Power Profile Over Time",
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
        print("-" * 60)

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

            print(
                f"{i + 1:2d}. {segment['name']:<20} | {duration_str} | {power_str:<12} | {intensity_name}"
            )

        print("-" * 60)

    def compare_zwo_and_fit(
        self,
        zwo_file: str,
        fit_file: str,
        zwo_visualizer=None,
        save_path: str = None,
        show_plot: bool = True,
    ):
        """Compare ZWO and FIT versions of the same workout"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))

        # Parse FIT file
        fit_workout = self.parse_fit_workout(fit_file)

        # Parse ZWO file (need to import or pass ZWO visualizer)
        if zwo_visualizer is None:
            print("Warning: No ZWO visualizer provided for comparison")
            return

        zwo_workout = zwo_visualizer.parse_zwo_file(zwo_file)

        # Plot FIT workout
        if fit_workout["segments"]:
            time_data, power_data, range_info = self.create_power_profile(
                fit_workout["segments"]
            )
            ax1.plot(
                time_data / 60,
                power_data,
                "b-",
                linewidth=2,
                label="FIT Workout",
                alpha=0.8,
            )

            # Add power ranges
            for range_data in range_info:
                ax1.fill_between(
                    [range_data["start_time"] / 60, range_data["end_time"] / 60],
                    [range_data["low_power"], range_data["low_power"]],
                    [range_data["high_power"], range_data["high_power"]],
                    alpha=0.2,
                    color="blue",
                )

        # Plot ZWO workout
        if zwo_workout["segments"]:
            time_data, power_data = zwo_visualizer.create_power_profile(
                zwo_workout["segments"]
            )
            power_watts = power_data * self.ftp
            ax1.plot(
                time_data / 60,
                power_watts,
                "r-",
                linewidth=2,
                label="ZWO Workout",
                alpha=0.8,
            )

        ax1.set_xlabel("Time (minutes)", fontsize=12)
        ax1.set_ylabel("Power (watts)", fontsize=12)
        ax1.set_title("Workout Comparison: ZWO vs FIT", fontsize=14, fontweight="bold")
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        ax1.axhline(
            y=self.ftp,
            color="red",
            linestyle="--",
            alpha=0.7,
            label=f"FTP ({self.ftp}W)",
        )

        # Comparison statistics
        ax2.axis("off")

        fit_stats = f"""FIT WORKOUT:
Name: {fit_workout["name"]}
Duration: {fit_workout["total_duration"] // 60}:{fit_workout["total_duration"] % 60:02d}
Steps: {len(fit_workout["segments"])}
Source: {fit_workout["source_file"]}"""

        zwo_stats = f"""ZWO WORKOUT:
Name: {zwo_workout["name"]}
Duration: {zwo_workout["total_duration"] // 60}:{zwo_workout["total_duration"] % 60:02d}
Segments: {len(zwo_workout["segments"])}
Source: {os.path.basename(zwo_file)}"""

        ax2.text(
            0.05,
            0.95,
            fit_stats,
            transform=ax2.transAxes,
            fontsize=10,
            verticalalignment="top",
            fontfamily="monospace",
        )
        ax2.text(
            0.55,
            0.95,
            zwo_stats,
            transform=ax2.transAxes,
            fontsize=10,
            verticalalignment="top",
            fontfamily="monospace",
        )

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            print(f"Workout comparison saved to: {save_path}")

        if show_plot:
            plt.show()

        return fig


def main():
    if not FITPARSE_AVAILABLE:
        print("Error: fitparse library is required. Install with: pip install fitparse")
        return

    parser = argparse.ArgumentParser(description="Visualize FIT workout files")
    parser.add_argument("files", nargs="+", help="FIT file(s) to visualize")
    parser.add_argument(
        "--ftp",
        type=int,
        default=250,
        help="Functional Threshold Power in watts (default: 250)",
    )
    parser.add_argument("--output", "-o", help="Save visualization to file (PNG/PDF)")
    parser.add_argument("--no-show", action="store_true", help="Don't display the plot")

    args = parser.parse_args()

    visualizer = FITWorkoutVisualizer(ftp=args.ftp)

    for fit_file in args.files:
        print(f"Visualizing: {fit_file}")
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
# python fit_visualizer.py workout.fit --ftp 275
# python fit_visualizer.py converted_workout.fit --output fit_viz.png
