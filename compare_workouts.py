#!/usr/bin/env python3

import matplotlib.pyplot as plt
import numpy as np
from zwo_parser import parse_zwo_to_workout
from fitfile_viewer import GarminFITWorkoutVisualizer
import argparse
import os


class WorkoutComparator:
    """Compare ZWO and FIT workout files side by side"""

    def __init__(self, ftp: int = 280):
        self.ftp = ftp
        self.intensity_colors = {
            # ZWO colors
            "warmup": "#45B7D1",  # Blue
            "cooldown": "#96CEB4",  # Green
            "steady": "#FF6B6B",  # Red
            "interval_work": "#FF6B6B",  # Red
            "interval_rest": "#4ECDC4",  # Teal
            # FIT colors (from fitfile_viewer)
            0: "#FF6B6B",  # Active - Red
            1: "#4ECDC4",  # Rest - Teal
            2: "#45B7D1",  # Warmup - Blue
            3: "#96CEB4",  # Cooldown - Green
            4: "#FFEAA7",  # Recovery - Yellow
        }

    def create_zwo_power_profile(self, segments):
        """Create time series data for ZWO power profile"""
        if not segments:
            return np.array([0]), np.array([0])

        time_points = []
        power_points = []
        current_time = 0

        for segment in segments:
            start_time = current_time
            end_time = current_time + segment.duration

            # Add start and end points
            time_points.extend([start_time, end_time])

            # Determine power value
            if segment.type in ["warmup", "cooldown"]:
                # For warmup/cooldown, show power ramp
                start_power = segment.power_start * self.ftp
                end_power = segment.power_end * self.ftp
                power_points.extend([start_power, end_power])
            else:
                # Steady power
                power = segment.power * self.ftp
                power_points.extend([power, power])

            current_time = end_time

        return np.array(time_points), np.array(power_points)

    def create_fit_power_profile(self, segments):
        """Create time series data for FIT power profile"""
        if not segments:
            return np.array([0]), np.array([0])

        time_points = []
        power_points = []

        for segment in segments:
            start_time = segment["start_time"]
            end_time = start_time + segment["duration"]

            # Add start and end points
            time_points.extend([start_time, end_time])

            # Use average of power range, or single power value
            if segment["power_range"]:
                avg_power = (segment["power_range"][0] + segment["power_range"][1]) / 2
                power_points.extend([avg_power, avg_power])
            elif segment["power_target"]:
                power_points.extend([segment["power_target"], segment["power_target"]])
            else:
                # Default power
                default_power = self.ftp * 0.7
                power_points.extend([default_power, default_power])

        return np.array(time_points), np.array(power_points)

    def compare_workouts(
        self,
        zwo_path: str,
        fit_path: str,
        save_path: str = None,
        show_plot: bool = True,
    ):
        """Create side-by-side comparison of ZWO and FIT workouts"""

        # Parse both files
        print(f"Parsing ZWO file: {zwo_path}")
        zwo_workout = parse_zwo_to_workout(zwo_path)
        zwo_segments = zwo_workout.segments

        print(f"Parsing FIT file: {fit_path}")
        fit_visualizer = GarminFITWorkoutVisualizer(ftp=self.ftp)
        fit_workout = fit_visualizer.parse_fit_workout(fit_path)
        fit_segments = fit_workout["segments"]

        if not zwo_segments or not fit_segments:
            print("Error: One or both files contain no segments")
            return

        # Calculate durations
        zwo_total_duration = sum(seg.duration for seg in zwo_segments)
        fit_total_duration = int(fit_workout["total_duration"])

        # Create figure with 4 subplots: 2 power profiles + 2 timelines
        fig = plt.figure(figsize=(16, 12))
        gs = fig.add_gridspec(4, 2, height_ratios=[2, 1, 2, 1], hspace=0.4, wspace=0.3)

        # ZWO Power Profile (top left)
        ax_zwo_power = fig.add_subplot(gs[0, 0])
        zwo_time_data, zwo_power_data = self.create_zwo_power_profile(zwo_segments)
        ax_zwo_power.plot(
            zwo_time_data / 60,
            zwo_power_data,
            "b-",
            linewidth=2.5,
            label="ZWO Power Profile",
        )

        # Add step blocks for ZWO
        current_time = 0
        for segment in zwo_segments:
            start_min = current_time / 60
            end_min = (current_time + segment.duration) / 60
            segment_color = self.intensity_colors.get(segment.type, "#808080")
            ax_zwo_power.axvspan(
                start_min, end_min, alpha=0.2, color=segment_color, zorder=1
            )
            current_time += segment.duration

        ax_zwo_power.axhline(
            y=self.ftp,
            color="red",
            linestyle="--",
            alpha=0.7,
            label=f"FTP ({self.ftp}W)",
        )
        ax_zwo_power.set_ylabel("Power (W)", fontsize=12)
        ax_zwo_power.set_title(
            f"ZWO: {zwo_workout.name} ({zwo_total_duration // 60}:{zwo_total_duration % 60:02d})",
            fontsize=14,
            fontweight="bold",
        )
        ax_zwo_power.grid(True, alpha=0.3)
        ax_zwo_power.legend()

        # FIT Power Profile (top right)
        ax_fit_power = fig.add_subplot(gs[0, 1])
        fit_time_data, fit_power_data = self.create_fit_power_profile(fit_segments)
        ax_fit_power.plot(
            fit_time_data / 60,
            fit_power_data,
            "g-",
            linewidth=2.5,
            label="FIT Power Profile",
        )

        # Add step blocks for FIT
        for segment in fit_segments:
            start_min = segment["start_time"] / 60
            end_min = (segment["start_time"] + segment["duration"]) / 60
            segment_color = self.intensity_colors.get(segment["intensity"], "#808080")
            ax_fit_power.axvspan(
                start_min, end_min, alpha=0.2, color=segment_color, zorder=1
            )

        ax_fit_power.axhline(
            y=self.ftp,
            color="red",
            linestyle="--",
            alpha=0.7,
            label=f"FTP ({self.ftp}W)",
        )
        ax_fit_power.set_ylabel("Power (W)", fontsize=12)
        ax_fit_power.set_title(
            f"FIT: {fit_workout['name']} ({fit_total_duration // 60}:{fit_total_duration % 60:02d})",
            fontsize=14,
            fontweight="bold",
        )
        ax_fit_power.grid(True, alpha=0.3)
        ax_fit_power.legend()

        # Match y-axis scales
        if len(zwo_power_data) > 0 and len(fit_power_data) > 0:
            max_power = max(max(zwo_power_data), max(fit_power_data))
            ax_zwo_power.set_ylim(0, max_power * 1.1)
            ax_fit_power.set_ylim(0, max_power * 1.1)

        # ZWO Timeline (middle left)
        ax_zwo_timeline = fig.add_subplot(gs[1, 0])
        zwo_colors = []
        zwo_durations = []
        zwo_starts = []

        current_time = 0
        for segment in zwo_segments:
            segment_color = self.intensity_colors.get(segment.type, "#808080")
            zwo_colors.append(segment_color)
            zwo_durations.append(segment.duration / 60)
            zwo_starts.append(current_time / 60)
            current_time += segment.duration

        ax_zwo_timeline.barh(
            range(len(zwo_segments)),
            zwo_durations,
            left=zwo_starts,
            color=zwo_colors,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
        )

        ax_zwo_timeline.set_xlabel("Time (minutes)", fontsize=12)
        ax_zwo_timeline.set_ylabel("Steps", fontsize=12)
        ax_zwo_timeline.set_title(
            f"ZWO Steps ({len(zwo_segments)} segments)", fontsize=12, fontweight="bold"
        )
        ax_zwo_timeline.set_yticks(
            range(0, len(zwo_segments), max(1, len(zwo_segments) // 10))
        )
        ax_zwo_timeline.grid(True, alpha=0.3, axis="x")
        ax_zwo_timeline.invert_yaxis()

        # FIT Timeline (middle right)
        ax_fit_timeline = fig.add_subplot(gs[1, 1])
        fit_colors = []
        fit_durations = []
        fit_starts = []

        for segment in fit_segments:
            segment_color = self.intensity_colors.get(segment["intensity"], "#808080")
            fit_colors.append(segment_color)
            fit_durations.append(segment["duration"] / 60)
            fit_starts.append(segment["start_time"] / 60)

        ax_fit_timeline.barh(
            range(len(fit_segments)),
            fit_durations,
            left=fit_starts,
            color=fit_colors,
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
        )

        ax_fit_timeline.set_xlabel("Time (minutes)", fontsize=12)
        ax_fit_timeline.set_ylabel("Steps", fontsize=12)
        ax_fit_timeline.set_title(
            f"FIT Steps ({len(fit_segments)} segments)", fontsize=12, fontweight="bold"
        )
        ax_fit_timeline.set_yticks(
            range(0, len(fit_segments), max(1, len(fit_segments) // 10))
        )
        ax_fit_timeline.grid(True, alpha=0.3, axis="x")
        ax_fit_timeline.invert_yaxis()

        # Comparison table (bottom)
        ax_comparison = fig.add_subplot(gs[2:, :])
        ax_comparison.axis("off")

        # Create comparison text
        comparison_text = "WORKOUT COMPARISON\n\n"
        comparison_text += f"{'Metric':<20} {'ZWO':<25} {'FIT':<25} {'Match':<10}\n"
        comparison_text += "-" * 80 + "\n"

        # Compare basic metrics
        zwo_duration_str = f"{zwo_total_duration // 60}:{zwo_total_duration % 60:02d}"
        fit_duration_str = f"{fit_total_duration // 60}:{fit_total_duration % 60:02d}"
        duration_match = (
            "✓" if abs(zwo_total_duration - fit_total_duration) <= 60 else "✗"
        )
        comparison_text += f"{'Duration':<20} {zwo_duration_str:<25} {fit_duration_str:<25} {duration_match:<10}\n"

        steps_match = "✓" if len(zwo_segments) == len(fit_segments) else "✗"
        comparison_text += f"{'Steps':<20} {len(zwo_segments):<25} {len(fit_segments):<25} {steps_match:<10}\n"

        comparison_text += f"{'Workout Name':<20} {zwo_workout.name:<25} {fit_workout['name']:<25} {'✓' if zwo_workout.name.strip() == fit_workout['name'].strip() else '✗':<10}\n"

        comparison_text += "\nFIRST 8 STEPS COMPARISON:\n"
        comparison_text += f"{'Step':<5} {'ZWO Type':<12} {'ZWO Duration':<12} {'ZWO Power':<15} {'FIT Duration':<12} {'FIT Power':<15} {'Match':<8}\n"
        comparison_text += "-" * 90 + "\n"

        for i in range(min(8, len(zwo_segments), len(fit_segments))):
            zwo_seg = zwo_segments[i]
            fit_seg = fit_segments[i]

            # ZWO info
            zwo_dur_str = f"{zwo_seg.duration // 60}:{zwo_seg.duration % 60:02d}"
            if zwo_seg.type in ["warmup", "cooldown"]:
                zwo_power_str = (
                    f"{zwo_seg.power_start * 100:.0f}-{zwo_seg.power_end * 100:.0f}%"
                )
            else:
                zwo_power_str = f"{zwo_seg.power * 100:.0f}%"

            # FIT info
            fit_dur_str = (
                f"{int(fit_seg['duration']) // 60}:{int(fit_seg['duration']) % 60:02d}"
            )
            if fit_seg["power_range"]:
                fit_power_str = (
                    f"{fit_seg['power_range'][0]:.0f}-{fit_seg['power_range'][1]:.0f}W"
                )
            else:
                fit_power_str = f"{fit_seg['power_target']:.0f}W"

            # Check if durations match (within 5 seconds)
            duration_match = (
                "✓" if abs(zwo_seg.duration - fit_seg["duration"]) <= 5 else "✗"
            )

            comparison_text += f"{i + 1:<5} {zwo_seg.type:<12} {zwo_dur_str:<12} {zwo_power_str:<15} {fit_dur_str:<12} {fit_power_str:<15} {duration_match:<8}\n"

        if max(len(zwo_segments), len(fit_segments)) > 8:
            comparison_text += (
                f"... and {max(len(zwo_segments), len(fit_segments)) - 8} more steps\n"
            )

        ax_comparison.text(
            0.02,
            0.98,
            comparison_text,
            transform=ax_comparison.transAxes,
            fontsize=9,
            verticalalignment="top",
            fontfamily="monospace",
        )

        # Add file sources
        fig.text(
            0.02,
            0.02,
            f"ZWO: {os.path.basename(zwo_path)} | FIT: {os.path.basename(fit_path)}",
            fontsize=9,
            style="italic",
        )

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            print(f"Workout comparison saved to: {save_path}")

        if show_plot:
            plt.show()

        return fig


def main():
    parser = argparse.ArgumentParser(
        description="Compare ZWO and FIT workout files side by side"
    )
    parser.add_argument("zwo_file", help="ZWO file to compare")
    parser.add_argument("fit_file", help="FIT file to compare")
    parser.add_argument(
        "--ftp",
        type=int,
        default=280,
        help="Functional Threshold Power in watts (default: 280)",
    )
    parser.add_argument("--output", "-o", help="Save comparison to file (PNG/PDF)")
    parser.add_argument("--no-show", action="store_true", help="Don't display the plot")

    args = parser.parse_args()

    if not os.path.exists(args.zwo_file):
        print(f"Error: ZWO file {args.zwo_file} not found")
        return

    if not os.path.exists(args.fit_file):
        print(f"Error: FIT file {args.fit_file} not found")
        return

    comparator = WorkoutComparator(ftp=args.ftp)
    comparator.compare_workouts(
        args.zwo_file, args.fit_file, save_path=args.output, show_plot=not args.no_show
    )


if __name__ == "__main__":
    main()

# Example usage:
# python compare_workouts.py pacing1.zwo pacing1.fit
# python compare_workouts.py pacing1.zwo pacing1.fit --output comparison.png --ftp 280
