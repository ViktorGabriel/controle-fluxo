import unittest
from unittest.mock import patch, MagicMock
from src.sheets_service import with_exponential_backoff, SheetsService


class TestSheetsService(unittest.TestCase):

    def test_with_exponential_backoff_success(self):
        call_count = 0

        @with_exponential_backoff(max_retries=3, base_seconds=0.01)
        def dummy_operation():
            nonlocal call_count
            call_count += 1
            return "SUCCESS"

        result = dummy_operation()
        self.assertEqual(result, "SUCCESS")
        self.assertEqual(call_count, 1)

    def test_with_exponential_backoff_retry_and_recover(self):
        call_count = 0

        @with_exponential_backoff(max_retries=3, base_seconds=0.01)
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("API Limit 429")
            return "RECOVERED"

        result = flaky_operation()
        self.assertEqual(result, "RECOVERED")
        self.assertEqual(call_count, 2)

    def test_with_exponential_backoff_max_retries_exceeded(self):
        @with_exponential_backoff(max_retries=2, base_seconds=0.01)
        def failing_operation():
            raise TimeoutError("Socket timeout")

        with self.assertRaises(TimeoutError):
            failing_operation()


if __name__ == "__main__":
    unittest.main()
