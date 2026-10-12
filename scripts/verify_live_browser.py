"""Check persisted live workflow results in Chromium; no workflow submission or paid calls."""
import argparse
import os
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--pr-number', type=int, required=True)
    parser.add_argument('--sprint-id', type=int, required=True)
    parser.add_argument('--gemini-result-id', type=int)
    args = parser.parse_args()
    if min(args.project_id, args.pr_number, args.sprint_id) < 1:
        parser.error('IDs must be positive')
    session = subprocess.run(['docker', 'compose', 'exec', '-T', 'backend', 'python', '-m',
                             'app.verify_live', '--project-id', str(args.project_id), '--session-only'],
                             capture_output=True, text=True)
    if session.returncode:
        raise SystemExit('Cannot obtain trusted local browser session; inspect backend configuration.')
    credential = session.stdout.strip()
    if credential.count('.') != 2 or '\n' in credential:
        raise SystemExit('Invalid local session response; no browser test started.')
    env = {**os.environ, 'SPRINTGRAPH_TEST_TOKEN': credential, 'SPRINTGRAPH_PROJECT_ID': str(args.project_id),
           'SPRINTGRAPH_PR_NUMBER': str(args.pr_number), 'SPRINTGRAPH_SPRINT_ID': str(args.sprint_id)}
    if args.gemini_result_id:
        env['SPRINTGRAPH_GEMINI_RESULT_ID'] = str(args.gemini_result_id)
    # Token is inherited via environment, never placed in command arguments or printed.
    result = subprocess.run(['docker', 'compose', '--profile', 'live-test', 'run', *(['--no-deps'] if args.gemini_result_id else []), '--build', '--rm',
                             '-e', 'SPRINTGRAPH_TEST_TOKEN', '-e', 'SPRINTGRAPH_PROJECT_ID',
                             '-e', 'SPRINTGRAPH_PR_NUMBER', '-e', 'SPRINTGRAPH_SPRINT_ID',
                             '-e', 'SPRINTGRAPH_GEMINI_RESULT_ID', 'e2e-live'], env=env)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
