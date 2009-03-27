import logging


#handler = logging.StreamHandler()
file_handler = logging.FileHandler("/tmp/storage.log")
formatter = logging.Formatter("[%(asctime)s] %(levelname)8s: %(message)s")
file_handler.setFormatter(formatter)

tty3_handler = logging.FileHandler("/dev/tty3")
tty3_handler.setFormatter(formatter)

logger = logging.getLogger("storage")
logger.addHandler(file_handler)
logger.addHandler(tty3_handler)
logger.setLevel(logging.DEBUG)


