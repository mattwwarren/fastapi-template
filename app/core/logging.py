import logging
import logging.config

from ecs_logging import StdlibFormatter


def configure_logging(level: str) -> None:
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "ecs": {
                "()": StdlibFormatter,
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "ecs",
                "stream": "ext://sys.stdout",
            }
        },
        "root": {
            "handlers": ["default"],
            "level": level.upper(),
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": level.upper()},
            "uvicorn.error": {"handlers": ["default"], "level": level.upper()},
            "uvicorn.access": {"handlers": ["default"], "level": level.upper()},
        },
    }
    logging.config.dictConfig(logging_config)
