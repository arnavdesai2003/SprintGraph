from pathlib import Path
import secrets
root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    raise SystemExit('.env already exists; preserving it')
text = (root / '.env.example').read_text()
for key in ['POSTGRES_PASSWORD', 'JWT_SECRET', 'DEMO_PASSWORD', 'GITHUB_WEBHOOK_SECRET', 'JIRA_WEBHOOK_SECRET']:
    text = text.replace(key + '=\n', key + '=' + secrets.token_hex(24) + '\n')
target.write_text(text)
target.chmod(0o600)
print('Created private .env. Read DEMO_PASSWORD there to sign in.')
