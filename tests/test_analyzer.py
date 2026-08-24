import unittest
from src.analyzer import FlowAnalyzer
from src.models import StatusEnum


class TestFlowAnalyzer(unittest.TestCase):

    def test_parse_numeric_value_valid(self):
        self.assertEqual(FlowAnalyzer.parse_numeric_value("1250"), 1250.0)
        self.assertEqual(FlowAnalyzer.parse_numeric_value("1.250,50"), 1250.50)
        self.assertEqual(FlowAnalyzer.parse_numeric_value("1250.75"), 1250.75)
        self.assertEqual(FlowAnalyzer.parse_numeric_value(" 450 "), 450.0)
        self.assertEqual(FlowAnalyzer.parse_numeric_value("0"), 0.0)

    def test_parse_numeric_value_empty_and_null(self):
        self.assertIsNone(FlowAnalyzer.parse_numeric_value(""))
        self.assertIsNone(FlowAnalyzer.parse_numeric_value("-"))
        self.assertIsNone(FlowAnalyzer.parse_numeric_value("N/A"))
        self.assertIsNone(FlowAnalyzer.parse_numeric_value("sem dados"))
        self.assertIsNone(FlowAnalyzer.parse_numeric_value("None"))

    def test_is_red_style_detection(self):
        # Classes CSS
        self.assertTrue(FlowAnalyzer.is_red_style(class_names="status-danger", style_attr=""))
        self.assertTrue(FlowAnalyzer.is_red_style(class_names="text-red-500 font-bold", style_attr=""))
        self.assertTrue(FlowAnalyzer.is_red_style(class_names="badge badge-falha", style_attr=""))
        
        # Inline styles
        self.assertTrue(FlowAnalyzer.is_red_style(class_names="", style_attr="color: #ff0000;"))
        self.assertTrue(FlowAnalyzer.is_red_style(class_names="", style_attr="background-color: rgb(220, 53, 69);"))
        
        # Não vermelho
        self.assertFalse(FlowAnalyzer.is_red_style(class_names="status-ok text-success", style_attr="color: green;"))
        self.assertFalse(FlowAnalyzer.is_red_style(class_names="", style_attr=""))

    def test_evaluate_reading_normal(self):
        reading = FlowAnalyzer.evaluate_reading(
            timestamp="24/08/2026 07:50:00",
            equipment_id="RADAR-01",
            lane_number="Faixa 1",
            raw_value="1420",
            is_red_highlighted=False
        )
        self.assertEqual(reading.status, StatusEnum.OK)
        self.assertEqual(reading.flow_value, 1420.0)
        self.assertEqual(reading.failure_reason, "")

    def test_evaluate_reading_empty_failure(self):
        reading = FlowAnalyzer.evaluate_reading(
            timestamp="24/08/2026 07:50:00",
            equipment_id="RADAR-01",
            lane_number="Faixa 1",
            raw_value="",
            is_red_highlighted=False
        )
        self.assertEqual(reading.status, StatusEnum.FALHA)
        self.assertIn("vazio ou não preenchido", reading.failure_reason)

    def test_evaluate_reading_red_highlighted_failure(self):
        reading = FlowAnalyzer.evaluate_reading(
            timestamp="24/08/2026 07:50:00",
            equipment_id="RADAR-02",
            lane_number="Faixa 2",
            raw_value="0",
            is_red_highlighted=True
        )
        self.assertEqual(reading.status, StatusEnum.FALHA)
        self.assertIn("vermelho", reading.failure_reason.lower())

    def test_evaluate_consecutive_readings_offline_failure(self):
        # Cenário: Penúltimo e Último Vermelhos -> FALHA / OFFLINE
        history = [
            {"value": "1200", "is_red": False},
            {"value": "0", "is_red": True},
            {"value": "", "is_red": True}
        ]
        reading = FlowAnalyzer.evaluate_consecutive_readings(
            timestamp="24/08/2026 07:50:00",
            equipment_id="RADAR-01",
            lane_number="Faixa 1",
            readings_history=history
        )
        self.assertEqual(reading.status, StatusEnum.FALHA)
        self.assertIn("OFFLINE", reading.failure_reason)

    def test_evaluate_consecutive_readings_single_alert(self):
        # Cenário: Apenas o último vermelho -> ALERTA
        history = [
            {"value": "1200", "is_red": False},
            {"value": "1150", "is_red": False},
            {"value": "0", "is_red": True}
        ]
        reading = FlowAnalyzer.evaluate_consecutive_readings(
            timestamp="24/08/2026 07:50:00",
            equipment_id="RADAR-01",
            lane_number="Faixa 1",
            readings_history=history
        )
        self.assertEqual(reading.status, StatusEnum.ALERTA)
        self.assertIn("ALERTA", reading.failure_reason)

    def test_evaluate_consecutive_readings_ok(self):
        # Cenário: Todos normais -> OK
        history = [
            {"value": "1200", "is_red": False},
            {"value": "1150", "is_red": False},
            {"value": "1300", "is_red": False}
        ]
        reading = FlowAnalyzer.evaluate_consecutive_readings(
            timestamp="24/08/2026 07:50:00",
            equipment_id="RADAR-01",
            lane_number="Faixa 1",
            readings_history=history
        )
        self.assertEqual(reading.status, StatusEnum.OK)
        self.assertEqual(reading.failure_reason, "")

    def test_to_history_and_pending_rows(self):
        reading = FlowAnalyzer.evaluate_reading(
            timestamp="24/08/2026 07:50:00",
            equipment_id="RADAR-02",
            lane_number="Faixa 2",
            raw_value="",
            is_red_highlighted=True
        )
        hist_row = reading.to_history_row()
        self.assertEqual(hist_row[0], "24/08/2026 07:50:00")
        self.assertEqual(hist_row[1], "RADAR-02")
        self.assertEqual(hist_row[4], StatusEnum.FALHA.value)

        pending_row = reading.to_pending_row()
        self.assertEqual(pending_row[6], "Pendente Técnico")


if __name__ == "__main__":
    unittest.main()

