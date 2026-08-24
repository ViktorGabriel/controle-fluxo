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
        
        # Classes comuns em frameworks UI (Bootstrap, Tailwind, customizados)
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
            "color-red",
            "badge-red",
            "rgb(255,",
            "rgb(220,",
            "rgb(239,",
            "#ff",
            "#dc3545",
            "#e53e3e",
            "#ef4444",
            "#f87171"
        ]

        return any(indicator in combined for indicator in red_indicators)

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
            # Fluxo zero pode ser falha ou tráfego nulo, se acompanhado de alerta ou valor bruto suspeito
            if is_red_highlighted:
                reasons.append("Fluxo zerado com sinalização de falha")
            else:
                # Caso o fluxo seja 0 sem vermelho, mantemos como alerta/atenção
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
