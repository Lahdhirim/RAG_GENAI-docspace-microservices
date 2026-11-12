import logging
import os


def create_logger(name: str, log_file: str, propagate: bool = True) -> logging.Logger:
    """Create and configure a logger writing to a specific file.

    Args:
        name: Logger name used to find or create the instance.
        log_file: Output file used when the logger has no handlers.
        propagate: Whether records propagate to parent loggers on initial setup.

    Returns:
        The named logger with its existing or newly configured handlers.
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:

        # Ensure log directory exists
        os.makedirs("logs", exist_ok=True)

        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        logger.propagate = propagate

    return logger
