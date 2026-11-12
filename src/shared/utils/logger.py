import logging
import os


def create_logger(name: str, log_file: str, propagate: bool = True) -> logging.Logger:
    """Configure a named file logger once, reusing its handlers on later calls.

    The first setup opens the file in write mode; later calls for the same logger
    retain its existing handlers and propagation setting.
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:

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
