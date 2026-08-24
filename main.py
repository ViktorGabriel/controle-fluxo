import io
import logging
import sys
import time
from src.config import settings
from src.scraper import PortalScraper
from src.sheets_service import SheetsService

# Garante suporte completo a UTF-8 no Windows/Linux
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)



def main():
    start_time = time.time()
    logger.info("=" * 65)
    logger.info("🚗 INICIANDO MONITORAMENTO AUTOMATIZADO DE FLUXOS VIÁRIOS")
    logger.info("=" * 65)

    # 1. Execução da extração no portal
    scraper = PortalScraper()
    summary = scraper.run_full_scan()

    logger.info("-" * 65)
    logger.info(f"📊 RESUMO DA EXECUÇÃO ({summary.execution_time}):")
    logger.info(f"   • Total de Equipamentos Verificados: {summary.total_equipments}")
    logger.info(f"   • Total de Faixas Analisadas:       {summary.total_lanes}")
    logger.info(f"   • Total de Falhas/Anomalias:        {summary.total_failures}")
    logger.info("-" * 65)

    # Se houver falhas, lista no log para auditoria rápida
    if summary.total_failures > 0:
        logger.warning("🚨 EQUIPAMENTOS / FAIXAS COM FALHA DETECTADA:")
        for failed in summary.failed_readings:
            logger.warning(
                f"   [FALHA] {failed.equipment_id} | {failed.lane_number} | "
                f"Valor: '{failed.raw_value}' | Motivo: {failed.failure_reason}"
            )
    else:
        logger.info("✅ Todos os equipamentos e faixas operando dentro da normalidade.")

    # 2. Integração e gravação no Google Sheets
    if settings.GOOGLE_SHEET_ID:
        logger.info("-" * 65)
        logger.info("📤 Atualizando planilha do Google Sheets...")
        sheets_svc = SheetsService()
        success = sheets_svc.append_readings(
            all_readings=summary.all_readings,
            failed_readings=summary.failed_readings
        )
        if success:
            logger.info("🎉 Planilha atualizada com sucesso!")
        else:
            logger.error("❌ Ocorreu um erro ao atualizar o Google Sheets.")
    else:
        logger.warning("⚠️ GOOGLE_SHEET_ID não configurado. Dados não gravados no Google Sheets.")

    elapsed = round(time.time() - start_time, 2)
    logger.info("=" * 65)
    logger.info(f"🏁 Execução finalizada com sucesso em {elapsed}s.")
    logger.info("=" * 65)


if __name__ == "__main__":
    main()
