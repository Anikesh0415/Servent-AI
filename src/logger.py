import os
import json
import logging
import time
import traceback

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


class StructuredLogger:
    """
    Structured Logger for Forge.
    Writes Human-Readable console logs and JSON file logs for failure analysis.
    """

    def __init__(self, name: str = "Forge"):
        os.makedirs(LOGS_DIR, exist_ok=True)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Human readable log file
        log_file = os.path.join(LOGS_DIR, f"agent_{time.strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # JSON lines log file for structured data and metrics
        json_log_file = os.path.join(
            LOGS_DIR, f"agent_metrics_{time.strftime('%Y%m%d')}.jsonl"
        )
        self.json_handler = logging.FileHandler(json_log_file, encoding="utf-8")
        self.json_handler.setLevel(logging.DEBUG)

        # Formatter for human readable
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
        )
        file_handler.setFormatter(formatter)

        if not self.logger.handlers:
            self.logger.addHandler(file_handler)

    def info(self, msg: str, context: dict = None):
        self._log("INFO", msg, context)

    def warning(self, msg: str, context: dict = None):
        self._log("WARNING", msg, context)

    def error(self, msg: str, context: dict = None, exc: Exception = None):
        if exc:
            if context is None:
                context = {}
            context["exception"] = str(exc)
            context["traceback"] = traceback.format_exc()
        self._log("ERROR", msg, context)

    def log_action_execution(
        self,
        step_id: int,
        action_type: str,
        target: str,
        success: bool,
        duration: float,
        extra: dict = None,
    ):
        ctx = {
            "step_id": step_id,
            "action": action_type,
            "target": target,
            "success": success,
            "duration_sec": round(duration, 3),
        }
        if extra:
            ctx.update(extra)

        level = "INFO" if success else "WARNING"
        self._log(
            level,
            f"Action [{step_id}] {action_type} -> {'SUCCESS' if success else 'FAILED'}",
            ctx,
        )

    def _log(self, level: str, msg: str, context: dict = None):
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": msg,
        }
        if context:
            # Secret masking helper
            sanitized = self._sanitize_dict(context)
            log_entry["context"] = sanitized

        full_msg = (
            f"{msg} | Context: {json.dumps(self._sanitize_dict(context))}"
            if context
            else msg
        )

        if level == "INFO":
            self.logger.info(full_msg)
        elif level == "WARNING":
            self.logger.warning(full_msg)
        elif level == "ERROR":
            self.logger.error(full_msg)
        else:
            self.logger.debug(full_msg)

        # Write structured JSON to the json lines file
        try:
            json_record = logging.LogRecord(
                name=self.logger.name,
                level=logging.getLevelName(level),
                pathname="",
                lineno=0,
                msg=json.dumps(log_entry),
                args=(),
                exc_info=None,
            )
            self.json_handler.emit(json_record)
        except Exception:
            pass

    def _sanitize_dict(self, data: dict) -> dict:
        """Masks sensitive keys like passwords, tokens, API keys."""
        if not isinstance(data, dict):
            return data

        sanitized = {}
        sensitive_keywords = [
            "api_key",
            "token",
            "password",
            "secret",
            "auth",
            "credential",
        ]

        for k, v in data.items():
            if any(kw in k.lower() for kw in sensitive_keywords):
                sanitized[k] = "***MASKED***"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_dict(v)
            else:
                sanitized[k] = v
        return sanitized


# Global Logger Singleton
logger = StructuredLogger()

if __name__ == "__main__":
    logger.info("Structured Logger initialized.")
    logger.log_action_execution(1, "open_browser", "https://google.com", True, 0.45)
