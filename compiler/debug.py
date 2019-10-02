import inspect
import os
import logging
from logging.handlers import RotatingFileHandler


# the debug levels:
# 0 = minimum output (default)
# 1 = major stages
# 2 = verbose
# n = custom setting

ERROR_CODE = -1

logger = logging.getLogger("debug-logger")
logger.setLevel(logging.DEBUG)  # always log messages

# messages will be pre-formatted
formatter = logging.Formatter("%(message)s")
# add a default console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = None

def check(check,str):
    if not check:
        (frame, filename, line_number, function_name, lines,
         index) = inspect.getouterframes(inspect.currentframe())[1]
        logger.debug("ERROR: file {0}: line {1}: {2}".format(os.path.basename(filename),line_number,str))
        assert 0

def error(str,return_value=0):
    (frame, filename, line_number, function_name, lines,
     index) = inspect.getouterframes(inspect.currentframe())[1]
    logger.debug("ERROR: file {0}: line {1}: {2}".format(os.path.basename(filename),line_number,str))
    assert return_value==0

def warning(str):
    (frame, filename, line_number, function_name, lines,
     index) = inspect.getouterframes(inspect.currentframe())[1]
    logger.debug("WARNING: file {0}: line {1}: {2}".format(os.path.basename(filename),line_number,str))


def info(lev, str):
    from globals import OPTS
    if (OPTS.debug_level >= lev):
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        #classname = frm.f_globals['__name__']
        if mod.__name__ == None:
            class_name=""
        else:
            class_name=mod.__name__
            logger.debug("[{0}/{1}]: {2}".format(class_name,frm[0].f_code.co_name,str))


def print_str(str):
    logger.debug(str)


class RotateOnOpenHandler(RotatingFileHandler):
    def shouldRollover(self, record):
        if self.stream is None:                 # delay was set...
            return 1
        return 0


def setup_file_log(filename):
    global file_handler
    # create directory if it doesn't exist
    directory = os.path.dirname(filename)
    if not os.path.exists(directory):
        os.makedirs(directory)
    if file_handler is not None:
        file_handler.close()
        logger.removeHandler(file_handler)
    file_handler = RotateOnOpenHandler(filename, mode='w', backupCount=5, delay=True)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

