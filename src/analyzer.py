import re
from typing import Optional, Tuple
from src.models import LaneReading, StatusEnum


class FlowAnalyzer:
    """Responsável por analisar leituras de faixas e detectar anomalias ou falhas de fluxo."""

    # Padrões textuais que indicam valor vazio ou sem fluxo
    EMPTY_PATTERNS = ["", "-", "n/a", "na", "null", "none", "vazio", "sem dados", "sem fluxo", "erro"]

    @classmethod
    def parse_numeric_value(cls, raw_text: str) -> Optional[float]:
        """Tenta converter a string bruta em valor numérico (suportando formatos BR 1.234,56 e US 1,234.56)."""
        if not raw_text:
            return None
        
        cleaned = raw_text.strip().lower()
        if cleaned in cls.EMPTY_PATTERNS:
            return None

        # Remove caracteres que não sejam dígitos, ponto, vírgula ou sinal de menos
        cleaned = re.sub(r"[^\d,\.-]", "", cleaned)
        if not cleaned:
            return None

        try:
            # Tratamento para padrão brasileiro (ex: 1.250,5 -> 1250.5 ou 0,0)
            if "," in cleaned and "." in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            return float(cleaned)
        except ValueError:
            return None

    @classmethod
    def is_red_style(cls, class_names: str = "", style_attr: str = "") -> bool:
        """Verifica se o elemento possui classes CSS ou estilos inline indicativos de cor vermelha/alerta."""
        combined = f"{class_names} {style_attr}".lower()
        
        # Classes comuns em frameworks UI (Bootstrap, Tailwind, customizados do portal)
        red_indicators = [
            "red",
            "danger",
            "text-danger",
            "bg-danger",
            "badge-danger",
            "alert",
            "status-error",
            "status-falha",
            "falha",
            "sem-fluxo",
            "sem-imagem",
            "discrepancia",
            "color-red",
            "badge-red",
            "rgb(255,",
            "rgb(220,",
            "rgb(239,",
            "rgb(248,",
            "rgb(252,",
            "#ff",
            "#dc3545",
            "#e53e3e",
            "#ef4444",
            "#f87171",
            "#f8d7da",
            "#fce8e6",
            "#ffebee"
        ]

        return any(indicator in combined for indicator in red_indicators)

    @classmethod
    def is_reading_failing(cls, raw_value: str, is_red_highlighted: bool) -> bool:
        """Determina se uma leitura individual é considerada em falha (vermelha ou sem dados válidos)."""
        if is_red_highlighted:
            return True
        val = cls.parse_numeric_value(raw_value)
        return val is None

    @classmethod
    def evaluate_consecutive_readings(
        cls,
        timestamp: str,
        equipment_id: str,
        lane_number: str,
        readings_history: list[dict]
    ) -> LaneReading:
        """
        Avalia o histórico de leituras de uma faixa (ex: colunas de períodos).
        
        Regra de Negócio:
        - Se o PENÚLTIMO e o ÚLTIMO registros estiverem em vermelho/falha -> STATUS FALHA (Equipamento/Faixa OFFLINE).
        - Se apenas o ÚLTIMO estiver em vermelho -> STATUS ALERTA (Instabilidade recente).
        - Caso contrário -> STATUS OK.
        """
        if not readings_history:
            return cls.evaluate_reading(
                timestamp=timestamp,
                equipment_id=equipment_id,
                lane_number=lane_number,
                raw_value="",
                is_red_highlighted=True
            )

        # Se houver apenas 1 leitura disponível
        if len(readings_history) == 1:
            last = readings_history[-1]
            return cls.evaluate_reading(
                timestamp=timestamp,
                equipment_id=equipment_id,
                lane_number=lane_number,
                raw_value=last.get("value", ""),
                is_red_highlighted=last.get("is_red", False)
            )

        # Avaliação de 2 ou mais períodos
        penult = readings_history[-2]
        last = readings_history[-1]

        penult_val = penult.get("value", "").strip()
        penult_red = penult.get("is_red", False)
        penult_failed = cls.is_reading_failing(penult_val, penult_red)

        last_val = last.get("value", "").strip()
        last_red = last.get("is_red", False)
        last_failed = cls.is_reading_failing(last_val, last_red)

        last_numeric = cls.parse_numeric_value(last_val)
        display_val = f"Penúltimo: '{penult_val}' | Último: '{last_val}'"

        if penult_failed and last_failed:
            status = StatusEnum.FALHA
            reason = "🚨 OFFLINE: Penúltimo e último períodos consecutivos em vermelho / sem fluxo"
        elif last_failed and not penult_failed:
            status = StatusEnum.ALERTA
            reason = "⚠️ ALERTA: Último período em vermelho (penúltimo operou normalmente)"
        elif penult_failed and not last_failed:
            status = StatusEnum.OK
            reason = "Recuperado: Penúltimo estava em falha, mas o último normalizou"
        else:
            status = StatusEnum.OK
            reason = ""

        return LaneReading(
            timestamp=timestamp,
            equipment_id=equipment_id,
            lane_number=lane_number,
            flow_value=last_numeric,
            raw_value=display_val,
            is_red_highlighted=last_red or penult_red,
            status=status,
            failure_reason=reason
        )

    @classmethod
    def evaluate_reading(
        cls,
        timestamp: str,
        equipment_id: str,
        lane_number: str,
        raw_value: str,
        is_red_highlighted: bool = False
    ) -> LaneReading:
        """
        Avalia os dados extraídos de uma faixa e determina se há falha de fluxo.
        
        Regras de Falha:
        1. Se a célula/faixa estiver com destaque visual em vermelho.
        2. Se o valor estiver vazio, nulo ou preenchido com 'N/A' / '-'.
        3. Se o valor for numérico igual a 0 em conjunto com indicador de alerta.
        """
        flow_value = cls.parse_numeric_value(raw_value)
        status = StatusEnum.OK
        reasons = []

        # Regra 1: Destaque visual vermelho
        if is_red_highlighted:
            status = StatusEnum.FALHA
            reasons.append("Indicador visual de falha (destaque em vermelho)")

        # Regra 2: Valor vazio / ausente
        if flow_value is None:
            status = StatusEnum.FALHA
            reasons.append(f"Fluxo vazio ou não preenchido ('{raw_value.strip()}')")
        elif flow_value == 0:
            if is_red_highlighted:
                reasons.append("Fluxo zerado com sinalização de falha")
            else:
                status = StatusEnum.ALERTA
                reasons.append("Fluxo zerado registrado")

        failure_reason = " | ".join(reasons) if reasons else ""

        return LaneReading(
            timestamp=timestamp,
            equipment_id=equipment_id,
            lane_number=lane_number,
            flow_value=flow_value,
            raw_value=raw_value.strip(),
            is_red_highlighted=is_red_highlighted,
            status=status,
            failure_reason=failure_reason
        )
