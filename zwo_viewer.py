#!/usr/bin/env python3

import matplotlib.pyplot as plt
import numpy as np
from zwift2fit import parse_zwo_file
import argparse
import os


class ZWOWorkoutVisualizer:
    """Visualize ZWO workout files with power profiles and step analysis"""

    def __init__(self, ftp: int = 250):
        self.ftp = ftp
        self.intensity_colors = {
            "warmup": "#45B7D1",  # Blue
            "cooldown": "#96CEB4",  # Green
            "steady": "#FF6B6B",  # Red
            "interval_work": "#FF6B6B",  # Red
            "interval_rest": "#4ECDC4",  # Teal
        }
        self.intensity_names = {
            "warmup": "Warmup",
            "cooldown": "Cooldown",
            "steady": "Steady",
            "interval_work": "Work",
            "interval_rest": "Rest",
        }

    def create_power_profile(self, segments):
        """Create time series data for power profile"""
        if not segments:
            return np.array([0]), np.array([0])

        time_points = []
        power_points = []

        current_time = 0

        for segment in segments:
            start_time = current_time
            end_time = current_time + segment["duration"]

            # Add start and end points
            time_points.extend([start_time, end_time])

            # Determine power value
            if segment["type"] == "warmup":
                # For warmup, use average power
                (
                    (segment["power_start"] + segment["power_end"]) / 2 * self.ftp
                )
                power_points.extend(
                    [segment["power_start"] * self.ftp, segment["power_end"] * self.ftp]
                )
            elif segment["type"] == "cooldown":
                # For cooldown, use average power
                (
                    (segment["power_start"] + segment["power_end"]) / 2 * self.ftp
                )
                power_points.extend(
                    [segment["power_start"] * self.ftp, segment["power_end"] * self.ftp]
                )
            else:
                # Steady power
                power = segment["power"] * self.ftp
                power_points.extend([power, power])

            current_time = end_time

        return np.array(time_points), np.array(power_points)

    def plot_zwo_workout(
        self, zwo_path: str, save_path: str = None, show_plot: bool = True
    ):
        """Display ZWO workout visualization and details"""

        # Parse ZWO file
        workout_info = parse_zwo_file(zwo_path)
        segments = workout_info["segments"]

        if not segments:
            print("No segments found")
            return

        # Calculate total duration
        total_duration = sum(seg["duration"] for seg in segments)

        # Print workout summary
        print(f"\n{workout_info['name']} (ZWO)")
        print(f"Duration: {total_duration // 60}:{total_duration % 60:02d}")
        print(f"Steps: {len(segments)}")
        print(f"Source: {os.path.basename(zwo_path)}")

        if show_plot:
            # Create figure with power profile and step timeline
            fig, (ax_power, ax_steps) = plt.subplots(
                2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2, 1]}
            )

            # Create power profile data
            time_data, power_data = self.create_power_profile(segments)
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

            # Add step blocks with different colors based on type
            current_time = 0
            for segment in segments:
                start_min = current_time / 60
                end_min = (current_time + segment["duration"]) / 60
                segment_color = self.intensity_colors.get(segment["type"], "#808080")

                ax_power.axvspan(
                    start_min, end_min, alpha=0.2, color=segment_color, zorder=1
                )
                current_time += segment["duration"]

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
                ax_power.set_ylim(0, max_power * 1.1)

            # Create step timeline
            colors = []
            durations = []
            starts = []

            current_time = 0
            for segment in segments:
                segment_color = self.intensity_colors.get(segment["type"], "#808080")
                colors.append(segment_color)
                durations.append(segment["duration"] / 60)
                starts.append(current_time / 60)
                current_time += segment["duration"]

            # Plot step timeline
            bars = ax_steps.barh(
                range(len(segments)),
                durations,
                left=starts,
                color=colors,
                alpha=0.8,
                edgecolor="black",
                linewidth=0.5,
            )

            # Add step labels
            for i, bar in enumerate(bars):
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
            ax_steps.set_yticks(range(len(segments)))
            ax_steps.set_yticklabels(
                [f"Step {i + 1}" for i in range(len(segments))], fontsize=8
            )
            ax_steps.grid(True, alpha=0.3, axis="x")
            ax_steps.invert_yaxis()  # Top to bottom ordering

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches="tight")
                print(f"ZWO workout visualization saved to: {save_path}")

            plt.show()

        # Print detailed step information
        print("\nSTEP DETAILS:")
        print("-" * 80)

        for i, segment in enumerate(segments):
            segment_type = self.intensity_names.get(
                segment["type"], segment["type"].title()
            )
            duration_str = f"{segment['duration'] // 60}:{segment['duration'] % 60:02d}"

            if segment["type"] in ["warmup", "cooldown"]:
                power_str = f"{segment['power_start'] * 100:.0f}-{segment['power_end'] * 100:.0f}% FTP ({segment['power_start'] * self.ftp:.0f}-{segment['power_end'] * self.ftp:.0f}W)"
            else:
                power_str = f"{segment['power'] * 100:.0f}% FTP ({segment['power'] * self.ftp:.0f}W)"

            print(f"{i + 1:2d}. {segment_type:<8} | {duration_str} | {power_str}")

        print("-" * 80)
        print(f"Total Duration: {total_duration // 60}:{total_duration % 60:02d}")


def main():
    parser = argparse.ArgumentParser(description="Visualize ZWO workout files")
    parser.add_argument("file", help="ZWO file to visualize")
    parser.add_argument(
        "--ftp",
        type=int,
        default=250,
        help="Functional Threshold Power in watts (default: 250)",
    )
    parser.add_argument("--output", "-o", help="Save visualization to file (PNG/PDF)")
    parser.add_argument("--no-show", action="store_true", help="Don't display the plot")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File {args.file} not found")
        return

    visualizer = ZWOWorkoutVisualizer(ftp=args.ftp)
    visualizer.plot_zwo_workout(
        args.file, save_path=args.output, show_plot=not args.no_show
    )


if __name__ == "__main__":
    main()
