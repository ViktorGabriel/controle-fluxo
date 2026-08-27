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
        self.assertTrue(hasattr(s, "SELECTOR_EQUIPMENT_FILTER"))

    def test_safe_converters(self):
        os.environ["TEST_INT_VALID"] = "45000"
        os.environ["TEST_INT_INVALID"] = "invalid_number"
        os.environ["TEST_INT_EMPTY"] = ""
        os.environ["TEST_BOOL_TRUE"] = "yes"
        os.environ["TEST_BOOL_FALSE"] = "0"
        
        try:
            self.assertEqual(Settings._safe_int("TEST_INT_VALID", 100), 45000)
            self.assertEqual(Settings._safe_int("TEST_INT_INVALID", 100), 100)
            self.assertEqual(Settings._safe_int("TEST_INT_EMPTY", 100), 100)
            self.assertEqual(Settings._safe_int("TEST_INT_NONEXISTENT", 100), 100)
            
            self.assertTrue(Settings._safe_bool("TEST_BOOL_TRUE", False))
            self.assertFalse(Settings._safe_bool("TEST_BOOL_FALSE", True))
        finally:
            for k in ["TEST_INT_VALID", "TEST_INT_INVALID", "TEST_INT_EMPTY", "TEST_BOOL_TRUE", "TEST_BOOL_FALSE"]:
                os.environ.pop(k, None)

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

