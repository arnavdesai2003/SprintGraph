import hashlib
import hmac
import unittest
from app.security.webhooks import github_signature_valid, shared_secret_valid

class WebhookSecurityTests(unittest.TestCase):
    def test_valid_signature(self):
        raw = b'{"number":42}'
        signature = 'sha256=' + hmac.new(b'secret', raw, hashlib.sha256).hexdigest()
        self.assertTrue(github_signature_valid(raw, 'secret', signature))
        self.assertFalse(github_signature_valid(raw + b' ', 'secret', signature))
    def test_missing_secret_and_invalid_signature(self):
        self.assertFalse(github_signature_valid(b'{}', '', ''))
        self.assertFalse(github_signature_valid(b'{}', 'secret', 'sha256=bad'))
        self.assertFalse(github_signature_valid(b'{}', 'secret', '☃'))
    def test_authenticated_jira_secret(self):
        self.assertTrue(shared_secret_valid('private', 'private'))
        self.assertFalse(shared_secret_valid('private', 'wrong'))
        self.assertFalse(shared_secret_valid('', ''))

if __name__ == '__main__':
    unittest.main()
