import os
import json
import unittest
from src.config import Settings


class TestConfig(unittest.TestCase):

    def test_settings_default_values(self):
        s = Settings()
        self.assertEqual(s.SHEET_TAB_HISTORY, "Historico_Geral")
        self.assertEqual(s.SHEET_TAB_PENDING, "Pendencias_Tecnicas")
        self.assertIsInstance(s.HEADLESS, bool)

    def test_get_google_credentials_from_json(self):
        mock_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com"
        }
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = json.dumps(mock_creds)
        
        try:
            creds = Settings.get_google_credentials_dict()
            self.assertIsNotNone(creds)
            self.assertEqual(creds["client_email"], "test@test-project.iam.gserviceaccount.com")
        finally:
            del os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]


if __name__ == "__main__":
    unittest.main()

