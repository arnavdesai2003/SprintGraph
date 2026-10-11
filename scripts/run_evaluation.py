"""Run a measured synthetic demo batch with the ordinary worker paused safely."""
import argparse
import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(*arguments, capture=False):
    return subprocess.run(['docker', 'compose', *arguments], cwd=ROOT, check=True, text=True,
                          capture_output=capture)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', type=int, default=400)
    parser.add_argument('--output', type=Path, default=ROOT / 'evaluation-report.json')
    args = parser.parse_args()
    if not 1 <= args.events <= 10000:
        parser.error('--events must be between 1 and 10000')
    raw = command('ps', '--all', '--format', 'json', 'worker', capture=True).stdout.strip()
    containers = json.loads(raw) if raw.startswith('[') else [json.loads(line) for line in raw.splitlines() if line]
    was_running = any(container.get('State') == 'running' for container in containers)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    remote = f'/tmp/sprintgraph-evaluation-{uuid.uuid4().hex}.json'
    print(f'Running {args.events} synthetic events. This adds demo records; no real provider calls.', flush=True)
    try:
        if was_running:
            command('stop', 'worker')
        result = subprocess.run(['docker', 'compose', 'exec', '-T', 'backend', 'python', '-m', 'app.evaluate',
                                 '--events', str(args.events), '--output', remote], cwd=ROOT)
        # Save failed-run reports too, when the evaluator produced one.
        copied = subprocess.run(['docker', 'compose', 'cp', f'backend:{remote}', str(output)], cwd=ROOT)
        if result.returncode or copied.returncode:
            raise RuntimeError('Evaluation failed; inspect its output and any saved report')
        report = json.loads(output.read_text())
        if report.get('dataset') != 'synthetic-demo-v1' or report.get('events') != args.events:
            raise RuntimeError('Unexpected evaluation report identity or event count')
        print(f'Report saved to {output}', flush=True)
    finally:
        if was_running:
            command('start', 'worker')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from None
