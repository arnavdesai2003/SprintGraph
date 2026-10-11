"""Submit an authenticated GitHub demo fixture without third-party dependencies."""
import hashlib
import hmac
import urllib.request
from pathlib import Path
root = Path(__file__).resolve().parents[1]
env = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
body = (root / 'backend/fixtures/github_pr.json').read_bytes()
request = urllib.request.Request('http://localhost:8000/api/webhooks/github', data=body, headers={
    'Content-Type': 'application/json', 'X-GitHub-Event': 'pull_request', 'X-GitHub-Delivery': 'demo-local-pr-43-v1',
    'X-Hub-Signature-256': 'sha256=' + hmac.new(env['GITHUB_WEBHOOK_SECRET'].encode(), body, hashlib.sha256).hexdigest()})
with urllib.request.urlopen(request, timeout=10) as response:
    print(response.read().decode())
