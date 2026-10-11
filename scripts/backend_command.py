"""Launch a backend command using the private root environment and current venv."""
import os
from pathlib import Path
import sys
from dotenv import dotenv_values
root = Path(__file__).resolve().parents[1]
values = {k: v for k, v in dotenv_values(root / '.env').items() if v is not None}
command = sys.argv[1:]
if not command:
    raise SystemExit('Usage: python scripts/backend_command.py <command> [args]')
if command[0] == 'python':
    command[0] = sys.executable
else:
    executable = Path(sys.executable).parent / command[0]
    if executable.exists():
        command[0] = str(executable)
os.chdir(root / 'backend')
os.execvpe(command[0], command, {**os.environ, **values})
