from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class StatusEnum(str, Enum):
    OK = "OK"
    FALHA = "FALHA"
    ALERTA = "ALERTA"
    ERRO_LEITURA = "ERRO_LEITURA"


@dataclass
class LaneReading:
    """Representa a leitura de uma faixa específica de um equipamento/radar."""
    timestamp: str
    equipment_id: str
    lane_number: str
    flow_value: Optional[float] = None
    raw_value: str = ""
    is_red_highlighted: bool = False
    status: StatusEnum = StatusEnum.OK
    failure_reason: str = ""

    def to_history_row(self) -> List[str]:
        """Formata o registro para a linha da aba de Histórico Geral."""
        val_str = str(self.flow_value) if self.flow_value is not None else (self.raw_value or "VAZIO")
        return [
            self.timestamp,
            self.equipment_id,
            self.lane_number,
            val_str,
            self.status.value,
            self.failure_reason or "Operação Normal",
        ]

    def to_pending_row(self) -> List[str]:
        """Formata o registro para a linha da aba de Pendências Técnicas."""
        val_str = str(self.flow_value) if self.flow_value is not None else (self.raw_value or "VAZIO")
        return [
            self.timestamp,
            self.equipment_id,
            self.lane_number,
            val_str,
            self.status.value,
            self.failure_reason or "Anomalia detectada",
            "Pendente Técnico",  # Coluna de ação para acompanhamento da equipe
        ]


@dataclass
class EquipmentReport:
    """Consolida as leituras de todas as faixas de um determinado equipamento."""
    equipment_id: str
    readings: List[LaneReading] = field(default_factory=list)
    has_failures: bool = False
    error_message: Optional[str] = None


@dataclass
class ScanSummary:
    """Sumário geral de uma rodada de execução do monitoramento."""
    execution_time: str
    total_equipments: int = 0
    total_lanes: int = 0
    total_failures: int = 0
    reports: List[EquipmentReport] = field(default_factory=list)

    @property
    def all_readings(self) -> List[LaneReading]:
        result = []
        for rep in self.reports:
            result.extend(rep.readings)
        return result

    @property
    def failed_readings(self) -> List[LaneReading]:
        return [r for r in self.all_readings if r.status in (StatusEnum.FALHA, StatusEnum.ERRO_LEITURA)]

