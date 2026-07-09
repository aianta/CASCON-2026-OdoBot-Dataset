#!/usr/bin/env python3
"""
Task selection and formatting script for OdoBotNL and WebVoyager.
Selects training instances (one per task) and writes them to a '|' delimited CSV,
then selects random evaluation instances while excluding training instances.

Usage:
    python task_selection.py --input <path> [--format <format>] [--random-sample <n>] \
        [--odobot-output <path>] [--webvoyager-output <path>] [--training-csv <path>] [--csv]

See `--help` for more details.
"""

import json
import csv
import random
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional


class TaskFormatter:
    """Handles formatting of tasks for different platforms and selection logic."""
    def __init__(self, tasks_data: List[Dict[str, Any]]):
        self.tasks = tasks_data
        self._selected_instances = {}  # Cache for pre-selected instances
        self.training_instances = {}   # task_id -> instance dict
        self.training_instance_ids = set()

    @staticmethod
    def _build_task_text(instance: Dict[str, Any], task_type: str,
                         answer_type: Optional[str] = None) -> str:
        prefix = f"Use the username: {instance['instance_username']} and password: {instance['instance_password']} to login to Canvas.\n"
        suffix = ""

        if task_type == "Information Seeking":
            if answer_type == 'Date Time':
                suffix = '''\nWrite your answer in the following format:\n\nAnswer: YYYY-MM-DD HH:mm'''
            elif answer_type == 'Numeric':
                suffix = '''\nWrite your answer in the following format:\n\nAnswer: [Number]'''
            elif answer_type == 'Text':
                suffix = """\nWrite your answer in the following format:\n\nAnswer: '[Text]'"""

        return f"{prefix}{instance['instance_text']}{suffix}"

    def _filter_out_training(self, instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.training_instance_ids:
            return instances
        return [inst for inst in instances if str(inst.get('id')) not in self.training_instance_ids]

    def _select_instances(self, task_id: str, task: Dict[str, Any], num_samples: Optional[int] = None) -> List[Dict[str, Any]]:
        # Use cached pre-selections when available
        if task_id in self._selected_instances:
            return self._selected_instances[task_id]

        instances = task.get('instances', [])
        instances = self._filter_out_training(instances)

        if num_samples is None:
            return instances

        num_available = len(instances)
        if num_samples >= num_available:
            return instances

        return random.sample(instances, num_samples)

    def select_training_instances(self) -> None:
        """Select one random instance per task (excluding Information Seeking) as training.

        Stores the selection in `self.training_instances` and `self.training_instance_ids`.
        """
        self.training_instances = {}
        self.training_instance_ids = set()

        for task_index, task in enumerate(self.tasks):
            if task.get('type') == 'Information Seeking':
                continue

            task_id = task.get('id', str(task_index))
            instances = task.get('instances', [])
            if not instances:
                continue

            chosen = random.choice(instances)
            self.training_instances[str(task_id)] = chosen
            self.training_instance_ids.add(str(chosen.get('id')))

    def preselect_instances(self, num_samples: Optional[int] = None) -> None:
        """Pre-select instances for all tasks, respecting training exclusions."""
        self._selected_instances = {}

        for task_index, task in enumerate(self.tasks):
            if task.get('type') == 'Information Seeking':
                continue

            task_id = task.get('id', str(task_index))
            selected = self._select_instances(task_id, task, num_samples)
            self._selected_instances[task_id] = selected

    def format_odobot_tasks(self, num_samples: Optional[int] = None) -> List[Dict[str, Any]]:
        odobot_tasks = []

        for task_index, task in enumerate(self.tasks):
            if task.get('type') == 'Information Seeking':
                continue

            task_id = task.get('id', str(task_index))
            selected_instances = self._select_instances(task_id, task, num_samples)

            for instance in selected_instances:
                task_text = self._build_task_text(instance, task.get('type'), task.get('answer_type'))
                odobot_task = {
                    'odoBotNL': {
                        'id': str(instance['id']),
                        '_evalId': f"{task_index + 1}|OdoBotNL|{instance['id']}",
                        'userLocation': 'http://localhost:8088/login/canvas',
                        'task': task_text
                    }
                }
                odobot_tasks.append(odobot_task)

        return odobot_tasks

    def format_webvoyager_tasks(self, num_samples: Optional[int] = None) -> List[Dict[str, Any]]:
        webvoyager_tasks = []

        for task_index, task in enumerate(self.tasks):
            if task.get('type') == 'Information Seeking':
                continue

            task_id = task.get('id', str(task_index))
            selected_instances = self._select_instances(task_id, task, num_samples)

            for instance in selected_instances:
                task_text = self._build_task_text(instance, task.get('type'), task.get('answer_type'))
                webvoyager_task = {
                    'web': 'http://localhost:8088',
                    'web_name': 'Canvas LMS',
                    'description': f"Instance of task {task['id']}",
                    'id': str(instance['id']),
                    'ques': task_text
                }
                webvoyager_tasks.append(webvoyager_task)

        return webvoyager_tasks


class TaskWriter:
    """Handles writing formatted tasks and training CSV to output files."""

    @staticmethod
    def write_odobot_json(tasks: List[Dict[str, Any]], output_path: str) -> None:
        with open(output_path, 'w') as f:
            json.dump(tasks, f, indent=2)
        print(f"✓ Written {len(tasks)} OdoBotNL tasks to {output_path}")

    @staticmethod
    def write_odobot_csv(tasks: List[Dict[str, Any]], output_path: str) -> None:
        rows = [["Task ID", "Eval ID", "Task"]]
        for task in tasks:
            odobot_info = task['odoBotNL']
            rows.append([odobot_info['id'], odobot_info['_evalId'], odobot_info['task']])

        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)
        print(f"✓ Written {len(tasks)} OdoBotNL tasks to {output_path}")

    @staticmethod
    def write_webvoyager_jsonl(tasks: List[Dict[str, Any]], output_path: str) -> None:
        with open(output_path, 'w') as f:
            for task in tasks:
                f.write(json.dumps(task) + '\n')
        print(f"✓ Written {len(tasks)} WebVoyager tasks to {output_path}")

    @staticmethod
    def write_training_csv(training_map: Dict[str, Dict[str, Any]], output_path: str) -> None:
        # Writes a '|' delimited CSV with header and rows: row|task_id|instance_id
        rows = [["row", "task_id", "instance_id"]]
        i = 1
        for task_id, instance in sorted(training_map.items(), key=lambda x: str(x[0])):
            rows.append([str(i), str(task_id), str(instance.get('id'))])
            i += 1

        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter='|')
            writer.writerows(rows)

        print(f"✓ Written {len(training_map)} training instances to {output_path}")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Select training instances and format task definitions for OdoBotNL and/or WebVoyager.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('-i', '--input', required=True, help='Path to input tasks JSON file')
    parser.add_argument('-f', '--format', choices=['odobot', 'webvoyager', 'both'], default='both', help='Output format (default: both)')
    parser.add_argument('-r', '--random-sample', type=int, default=None, help='Number of random instances per task (default: all instances)')
    parser.add_argument('-o', '--odobot-output', default='odobot_tasks.json', help='Output path for OdoBotNL JSON (default: odobot_tasks.json)')
    parser.add_argument('-w', '--webvoyager-output', default='webvoyager_tasks.jsonl', help='Output path for WebVoyager JSONL (default: webvoyager_tasks.jsonl)')
    parser.add_argument('--training-csv', default='training_instances.csv', help="Output path for training instances CSV (default: training_instances.csv)")
    parser.add_argument('--csv', action='store_true', help='Also generate CSV output for OdoBotNL tasks')

    return parser.parse_args()


def load_tasks(input_path: str) -> List[Dict[str, Any]]:
    try:
        with open(input_path, 'r') as f:
            tasks = json.load(f)
        print(f"✓ Loaded {len(tasks)} tasks from {input_path}")
        return tasks
    except FileNotFoundError:
        print(f"✗ Error: Input file '{input_path}' not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"✗ Error: Invalid JSON in '{input_path}'", file=sys.stderr)
        sys.exit(1)


def validate_arguments(args):
    if args.random_sample is not None and args.random_sample <= 0:
        print("✗ Error: --random-sample must be a positive integer", file=sys.stderr)
        sys.exit(1)


def main():
    args = parse_arguments()
    validate_arguments(args)

    tasks = load_tasks(args.input)
    formatter = TaskFormatter(tasks)
    writer = TaskWriter()

    print(f"\nSelecting training instances and formatting tasks (random sample: {args.random_sample or 'all'})...")

    # Select one training instance per task and write CSV
    formatter.select_training_instances()
    writer.write_training_csv(formatter.training_instances, args.training_csv)

    # Pre-select instances for both formats (ensures same samples) while respecting training exclusion
    if args.format == 'both':
        formatter.preselect_instances(args.random_sample)

    # Generate OdoBotNL format if requested
    if args.format in ['odobot', 'both']:
        odobot_tasks = formatter.format_odobot_tasks(args.random_sample)
        writer.write_odobot_json(odobot_tasks, args.odobot_output)

        if args.csv:
            csv_output = args.odobot_output.replace('.json', '.csv')
            writer.write_odobot_csv(odobot_tasks, csv_output)

    # Generate WebVoyager format if requested
    if args.format in ['webvoyager', 'both']:
        webvoyager_tasks = formatter.format_webvoyager_tasks(args.random_sample)
        writer.write_webvoyager_jsonl(webvoyager_tasks, args.webvoyager_output)

    print("\n✓ Task selection and formatting complete!")


if __name__ == '__main__':
    main()
