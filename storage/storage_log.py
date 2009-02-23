import logging


#handler = logging.StreamHandler()
handler = logging.FileHandler("/tmp/storage.log")
formatter = logging.Formatter("[%(asctime)s] %(levelname)8s: %(message)s")
handler.setFormatter(formatter)

logger = logging.getLogger("storage")
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


