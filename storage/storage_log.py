import logging
import anaconda_log

logger = logging.getLogger("storage")
logger.setLevel(logging.DEBUG)
anaconda_log.logger.addFileHandler("/tmp/storage.log", logger, logging.DEBUG)
anaconda_log.logger.addFileHandler("/dev/tty3", logger, logging.DEBUG)
