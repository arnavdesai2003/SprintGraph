import json
from unittest.mock import patch
from app.config import settings
from app.verify_gemini import diagnose, main


def test_diagnostics_are_read_only_and_redact_key(db, monkeypatch, tmp_path, capsys):
    c = settings()
    monkeypatch.setattr(c, 'llm_api_key', 'private-diagnostic-key')
    monkeypatch.setattr(c, 'llm_provider', 'openai-compatible')
    report = tmp_path / 'once.json'
    report.write_text(json.dumps({'status': 'failed', 'inference_requests': 1, 'event_id': 123,
                                  'unexpected_secret': 'never-print-this'}))
    with patch('httpx.AsyncClient.post', side_effect=AssertionError('No inference')), \
            patch('httpx.Client.post', side_effect=AssertionError('No event submission')):
        diagnose(report)
    output = capsys.readouterr().out
    assert 'private-diagnostic-key' not in output and 'never-print-this' not in output
    data = json.loads(output)
    assert data['network_requests'] == 0 and data['report_exists']
    assert data['previous_report']['inference_requests'] == 1


def test_existing_report_error_is_specific_and_safe(monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['verify_gemini', '--project-id', '2', '--pr-number', '2'])
    monkeypatch.setattr('app.verify_gemini.verify', lambda *args: (_ for _ in ()).throw(FileExistsError('private')))
    import pytest
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    output = capsys.readouterr().err
    assert 'report already exists' in output and 'private' not in output
