import unittest
from unittest.mock import patch, MagicMock
from src.models import ScanSummary, EquipmentReport, LaneReading, StatusEnum
from src.notifier import FailureNotifier
from src.config import settings


class TestFailureNotifier(unittest.TestCase):

    def _create_mock_summary(self, failures: int = 2) -> ScanSummary:
        summary = ScanSummary(
            execution_time="27/08/2026 15:30:00",
            total_equipments=3,
            total_lanes=6,
            total_failures=failures,
            success=True
        )
        report = EquipmentReport(equipment_id="SBR402", has_failures=(failures > 0))
        if failures > 0:
            report.readings.append(
                LaneReading(
                    timestamp="27/08/2026 15:30:00",
                    equipment_id="SBR402",
                    lane_number="SBR402 - 1",
                    flow_value=None,
                    raw_value="",
                    is_red_highlighted=True,
                    status=StatusEnum.FALHA,
                    failure_reason="Fluxo vazio com destaque em vermelho"
                )
            )
        else:
            report.readings.append(
                LaneReading(
                    timestamp="27/08/2026 15:30:00",
                    equipment_id="SBR402",
                    lane_number="SBR402 - 1",
                    flow_value=1250.0,
                    raw_value="1250",
                    is_red_highlighted=False,
                    status=StatusEnum.OK,
                    failure_reason="Operação Normal"
                )
            )
        summary.reports.append(report)
        return summary

    def test_format_failure_message(self):
        summary = self._create_mock_summary(failures=1)
        msg = FailureNotifier.format_failure_message(summary)
        self.assertIn("ALERTA: ANOMALIA DETECTADA", msg)
        self.assertIn("SBR402", msg)
        self.assertIn("SBR402 - 1", msg)
        self.assertIn("Pendencias_Tecnicas", msg)

    def test_notify_if_no_failures(self):
        summary = self._create_mock_summary(failures=0)
        res = FailureNotifier.notify_if_failures(summary)
        self.assertEqual(res, {})

    @patch("urllib.request.urlopen")
    def test_send_webhook_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 204
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with patch.object(settings, "ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/test"):
            summary = self._create_mock_summary(failures=1)
            success = FailureNotifier.send_webhook(summary)
            self.assertTrue(success)
            mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_send_telegram_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with patch.object(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC"), \
             patch.object(settings, "TELEGRAM_CHAT_ID", "999888"):
            summary = self._create_mock_summary(failures=1)
            success = FailureNotifier.send_telegram(summary)
            self.assertTrue(success)
            mock_urlopen.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_success(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        with patch.object(settings, "SMTP_HOST", "smtp.test.com"), \
             patch.object(settings, "ALERT_EMAILS_TO", "test1@empresa.com,test2@empresa.com"):
            summary = self._create_mock_summary(failures=1)
            success = FailureNotifier.send_email(summary)
            self.assertTrue(success)
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
