"""Capture dependency versions from validated Docker environments, without re-resolution."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def run(arguments):
    result = subprocess.run(arguments, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f'Docker command failed: {arguments[:4]}; verify Docker access and built images')
    return result.stdout


def validate_npm(raw, manifest_path):
    lock = json.loads(raw)
    manifest = json.loads(manifest_path.read_text())
    if lock.get('lockfileVersion', 0) < 2 or lock.get('name') != manifest['name']:
        raise ValueError(f'Invalid or mismatched lockfile for {manifest_path.parent.name}')
    packages = lock.get('packages', {})
    root = packages.get('', {})
    for group in ['dependencies', 'devDependencies']:
        if root.get(group, {}) != manifest.get(group, {}):
            raise ValueError(f'Image dependencies do not match current {manifest_path}; rebuild its image')
    for name, package in packages.items():
        if not name:
            continue
        resolved = urlparse(package.get('resolved', ''))
        if resolved.username or resolved.password or resolved.query or resolved.fragment:
            raise ValueError('Lockfile contains a credential-bearing or parameterized URL; refusing to write it')
        if resolved.scheme != 'https' or not package.get('integrity'):
            raise ValueError('Expected integrity-checked HTTPS registry dependencies')
    return json.dumps(lock, indent=2) + '\n'


def validate_python(raw):
    lines = sorted(line.strip() for line in raw.splitlines() if line.strip())
    if not lines or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9.!+_-]*', line) for line in lines):
        raise ValueError('Expected pinned registry packages only; local/editable/URL requirements are not written')
    return '# Captured from validated Python 3.12 Linux Docker environment.\n' + '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true', help='Explicitly replace existing locks with captured versions')
    args = parser.parse_args()
    captures = [
        (ROOT / 'frontend/package-lock.json', validate_npm(run([
            'docker', 'run', '--rm', 'sprintgraph-frontend-check', 'cat', '/app/package-lock.json']), ROOT / 'frontend/package.json')),
        (ROOT / 'e2e/package-lock.json', validate_npm(run([
            'docker', 'compose', '--profile', 'demo', '--profile', 'test', 'run', '--no-deps', '--rm',
            '--entrypoint', 'cat', 'e2e', '/tests/package-lock.json']), ROOT / 'e2e/package.json')),
        (ROOT / 'backend/requirements.lock', validate_python(run([
            'docker', 'compose', 'exec', '-T', 'backend', 'python', '-m', 'pip', 'freeze', '--exclude', 'sprintgraph']))),
    ]
    # Validate all captures and existing files before writing any result.
    for path, content in captures:
        if path.exists() and path.read_text() != content and not args.refresh:
            raise RuntimeError(f'{path.relative_to(ROOT)} already differs; use --refresh to intentionally update it')
    for path, content in captures:
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(content)
        temporary.replace(path)
        print('Captured', path.relative_to(ROOT))
    print('Rebuild and rerun checks to validate the captured locks. No dependency versions were re-resolved.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
