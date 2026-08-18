# taken from https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
import logging


class SciQlopFormatter(logging.Formatter):
    blue = "\x1b[38;5;33;48;5;236m"
    grey = "\x1b[38;5;245;48;5;236m"
    yellow = "\x1b[38;5;220;48;5;236m"
    orange = "\x1b[38;5;208;48;5;236m"
    red = "\x1b[38;5;196;48;5;236m"
    bold_red = "\x1b[1;38;5;196;48;5;236m"
    reset = "\x1b[0m"
    format = "%(asctime)s %(module)-25s %(levelname)-8s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: blue + format + reset,
        logging.INFO: yellow + format + reset,
        logging.WARNING: orange + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
