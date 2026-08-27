import json
import logging
import smtplib
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List
from src.config import settings
from src.models import ScanSummary

logger = logging.getLogger(__name__)


class FailureNotifier:
    """Gerencia o envio de alertas de falha via Webhooks, Telegram e E-mail (SMTP)."""

    @classmethod
    def format_failure_message(cls, summary: ScanSummary) -> str:
        """Gera uma mensagem em texto formatada com o sumário de falhas."""
        failed = summary.failed_readings
        lines = [
            "🚨 ALERTA: ANOMALIA DETECTADA NO FLUXO VIÁRIO",
            f"📅 Data/Hora: {summary.execution_time}",
            f"📊 Total de Radares Auditados: {summary.total_equipments}",
            f"⚠️ Faixas com Falha/Vermelho: {summary.total_failures}",
            "",
            "Equipamentos e Faixas Afetadas:"
        ]
        for f in failed:
            val = f.raw_value if f.raw_value else "VAZIO"
            lines.append(f"  • {f.equipment_id} ({f.lane_number}) -> Valor: '{val}' | Motivo: {f.failure_reason}")

        lines.append("")
        lines.append("📋 Consulte a planilha na aba 'Pendencias_Tecnicas' para a lista completa.")
        return "\n".join(lines)

    @classmethod
    def send_webhook(cls, summary: ScanSummary) -> bool:
        """Envia alerta para Webhook genérico (compatível com Discord, Teams, Slack)."""
        url = settings.ALERT_WEBHOOK_URL
        if not url:
            return False

        message = cls.format_failure_message(summary)
        payload = {
            "content": message,
            "text": message
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "ControleFluxoViario/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"🔔 Alerta enviado via Webhook com sucesso (Status: {resp.status})")
                return True
        except Exception as e:
            logger.error(f"Erro ao enviar alerta via Webhook: {e}")
            return False

    @classmethod
    def send_telegram(cls, summary: ScanSummary) -> bool:
        """Envia alerta via Bot do Telegram."""
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        if not token or not chat_id:
            return False

        message = cls.format_failure_message(summary)
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"🔔 Alerta enviado via Telegram com sucesso (Status: {resp.status})")
                return True
        except Exception as e:
            logger.error(f"Erro ao enviar alerta via Telegram: {e}")
            return False

    @classmethod
    def send_email(cls, summary: ScanSummary) -> bool:
        """Envia alerta formatado por E-mail via SMTP."""
        host = settings.SMTP_HOST
        port = settings.SMTP_PORT
        user = settings.SMTP_USER
        password = settings.SMTP_PASSWORD
        recipients = settings.get_alert_recipients()

        if not host or not recipients:
            return False

        message_text = cls.format_failure_message(summary)
        msg = MIMEMultipart()
        msg["From"] = user or f"alerta-radares@{host}"
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = f"🚨 [ALERTA] Falha de Fluxo Viário - {summary.total_failures} Ocorrência(s) - {summary.execution_time}"
        msg.attach(MIMEText(message_text, "plain", "utf-8"))

        try:
            server = smtplib.SMTP(host, port, timeout=15)
            if settings.SMTP_USE_TLS:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(msg["From"], recipients, msg.as_string())
            server.quit()
            logger.info(f"🔔 Alerta por e-mail enviado para: {', '.join(recipients)}")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar alerta por e-mail: {e}")
            return False

    @classmethod
    def notify_if_failures(cls, summary: ScanSummary) -> Dict[str, bool]:
        """Dispara todas as notificações configuradas caso haja falhas no sumário."""
        if summary.total_failures == 0:
            return {}

        results = {}
        if settings.ALERT_WEBHOOK_URL:
            results["webhook"] = cls.send_webhook(summary)
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            results["telegram"] = cls.send_telegram(summary)
        if settings.SMTP_HOST and settings.get_alert_recipients():
            results["email"] = cls.send_email(summary)

        if not results:
            logger.info("ℹ️ Nenhuma notificação externa (Webhook/Telegram/Email) configurada. Alerta gravado apenas na planilha.")

        return results
