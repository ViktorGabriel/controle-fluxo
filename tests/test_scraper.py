import unittest
from unittest.mock import MagicMock
from src.scraper import PortalScraper
from src.models import StatusEnum


class TestPortalScraper(unittest.TestCase):

    def test_get_current_timestamp(self):
        scraper = PortalScraper()
        ts = scraper._get_current_timestamp()
        self.assertTrue(isinstance(ts, str))
        self.assertRegex(ts, r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$")

    def test_is_authenticated(self):
        scraper = PortalScraper()
        self.assertFalse(scraper.is_authenticated())

        scraper.page = MagicMock()
        scraper.page.url = "https://bh.etransito.com.br/contratada/#/auth/login"
        self.assertFalse(scraper.is_authenticated())

        scraper.page.url = "https://bh.etransito.com.br/contratada/#/mapas/mapa-unificado"
        self.assertTrue(scraper.is_authenticated())

    def test_close_browser_resilience(self):
        scraper = PortalScraper()
        # Testa fechar sem ter inicializado (não deve lançar exceção)
        scraper.close_browser()

        # Testa com mocks que levantam exceção
        mock_page = MagicMock()
        mock_page.close.side_effect = Exception("Page already closed")
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_pw = MagicMock()

        scraper.page = mock_page
        scraper.context = mock_context
        scraper.browser = mock_browser
        scraper.playwright = mock_pw

        scraper.close_browser()
        self.assertIsNone(scraper.page)
        self.assertIsNone(scraper.context)
        self.assertIsNone(scraper.browser)
        self.assertIsNone(scraper.playwright)
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()

    def test_generate_mock_data(self):
        scraper = PortalScraper()
        summary = scraper.generate_mock_data()
        self.assertTrue(summary.success)
        self.assertGreater(summary.total_equipments, 0)
        self.assertGreater(summary.total_lanes, 0)
        self.assertGreater(summary.total_failures, 0)
        self.assertTrue(any(r.status == StatusEnum.FALHA for r in summary.failed_readings))


if __name__ == "__main__":
    unittest.main()
