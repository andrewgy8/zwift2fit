#!/usr/bin/env python3

import argparse
import subprocess
import os
from workout_db import WorkoutDatabase

def view_workout_by_id(workout_id: int, db_path: str = "workouts.db", show_plot: bool = True):
    """View a workout by database ID"""
    db = WorkoutDatabase(db_path)
    workout = db.get_workout_details(workout_id)
    
    if not workout:
        print(f"Workout ID {workout_id} not found")
        return
    
    print(f"Viewing workout: {workout['name']} by {workout['author']}")
    
    if workout['fit_file_name'] and os.path.exists(workout['fit_file_name']):
        # Use FIT file if available
        fit_path = workout['fit_file_name']
        print(f"Using FIT file: {fit_path}")
        
        cmd = ['python', 'fitfile_viewer.py', fit_path]
        if not show_plot:
            cmd.append('--no-show')
        
        subprocess.run(cmd)
    
    elif os.path.exists(workout['file_path']):
        # Fall back to ZWO file
        zwo_path = workout['file_path']
        print(f"Using ZWO file: {zwo_path}")
        
        cmd = ['python', 'zwo_viewer.py', zwo_path]
        if workout['ftp_used']:
            cmd.extend(['--ftp', str(workout['ftp_used'])])
        if not show_plot:
            cmd.append('--no-show')
        
        subprocess.run(cmd)
    else:
        print("Neither FIT nor ZWO file found")

def view_workout_by_name(workout_name: str, db_path: str = "workouts.db", show_plot: bool = True):
    """View a workout by name (searches for partial matches)"""
    db = WorkoutDatabase(db_path)
    results = db.search_workouts(name=workout_name)
    
    if not results:
        print(f"No workouts found matching '{workout_name}'")
        return
    
    if len(results) == 1:
        # Single match, view it
        view_workout_by_id(results[0]['id'], db_path, show_plot)
    else:
        # Multiple matches, let user choose
        print(f"Found {len(results)} workouts matching '{workout_name}':")
        for workout in results:
            duration_str = f"{workout['total_duration']//60}:{workout['total_duration']%60:02d}"
            fit_indicator = " [FIT]" if workout['fit_file_name'] else ""
            print(f"  {workout['id']:3d}: {workout['name']:<30} ({duration_str}) by {workout['author']}{fit_indicator}")
        
        try:
            choice = int(input("\nEnter workout ID to view: "))
            view_workout_by_id(choice, db_path, show_plot)
        except (ValueError, KeyboardInterrupt):
            print("Cancelled")

def compare_workout_files(workout_id: int, db_path: str = "workouts.db", show_plot: bool = True):
    """Compare ZWO and FIT files for a workout"""
    db = WorkoutDatabase(db_path)
    workout = db.get_workout_details(workout_id)
    
    if not workout:
        print(f"Workout ID {workout_id} not found")
        return
    
    if not workout['fit_file_name'] or not os.path.exists(workout['fit_file_name']):
        print("FIT file not found for comparison")
        return
    
    if not os.path.exists(workout['file_path']):
        print("ZWO file not found for comparison")
        return
    
    print(f"Comparing ZWO and FIT files for: {workout['name']}")
    
    cmd = ['python', 'compare_workouts.py', workout['file_path'], workout['fit_file_name']]
    if workout['ftp_used']:
        cmd.extend(['--ftp', str(workout['ftp_used'])])
    if not show_plot:
        cmd.append('--no-show')
    
    subprocess.run(cmd)

def main():
    parser = argparse.ArgumentParser(description='View workouts from the database')
    parser.add_argument('--db', default='workouts.db', help='Database file path (default: workouts.db)')
    parser.add_argument('--id', type=int, help='View workout by ID')
    parser.add_argument('--name', help='View workout by name (partial match)')
    parser.add_argument('--compare', type=int, help='Compare ZWO and FIT files for workout ID')
    parser.add_argument('--list', action='store_true', help='List all workouts')
    parser.add_argument('--no-show', action='store_true', help='Don\'t display plots')
    
    args = parser.parse_args()
    
    if args.id:
        view_workout_by_id(args.id, args.db, not args.no_show)
    elif args.name:
        view_workout_by_name(args.name, args.db, not args.no_show)
    elif args.compare:
        compare_workout_files(args.compare, args.db, not args.no_show)
    elif args.list:
        db = WorkoutDatabase(args.db)
        results = db.search_workouts()
        if results:
            print(f"All workouts ({len(results)}):")
            for workout in results:
                duration_str = f"{workout['total_duration']//60}:{workout['total_duration']%60:02d}"
                tags_str = ", ".join(workout['tags'][:3]) + ("..." if len(workout['tags']) > 3 else "")
                fit_indicator = " [FIT]" if workout['fit_file_name'] else ""
                print(f"  {workout['id']:3d}: {workout['name']:<30} ({duration_str}) by {workout['author']} [{tags_str}]{fit_indicator}")
        else:
            print("No workouts found in database")
    else:
        print("No action specified. Use --help for usage information.")

if __name__ == "__main__":
    main()

# Example usage:
# python view_workout.py --id 2
# python view_workout.py --name "pacing"
# python view_workout.py --compare 2
# python view_workout.py --list