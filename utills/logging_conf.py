# utills/logging_conf.py
"""
统一的日志配置模块，适用于生产环境和开发环境。

特性：
- 通过环境变量控制日志级别和输出方式
- 支持控制台彩色输出（兼容不支持颜色的终端）
- 文件输出同时支持按时间（每天）和按大小（默认10MB）轮转
- 自动清理超过保留天数（默认21天）的历史日志
- 使用 QueueHandler + QueueListener 实现非阻塞日志写入
- 集成 uvicorn 和 SQLAlchemy 等第三方库的日志
- 提供便捷的模块日志获取函数

用法:
    from utills.logging_conf import setup_logging, get_logger

    # 在应用启动时调用一次
    setup_logging()
    logger = get_logger(__name__)
    logger.info("App started")
"""

import logging
import logging.handlers
import os
import sys
import glob
import time
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# --------------------------- 配置常量 ---------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

CONSOLE_FORMAT = (
    "%(asctime)s | %(levelcolor)s%(levelname)-8s%(reset)s | "
    "%(name)s:%(lineno)d | %(message)s"
)
FILE_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
)

LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() in ("1", "true", "yes")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/vitalis.log")
LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", "10485760"))  # 10MB
LOG_FILE_RETENTION_DAYS = int(os.getenv("LOG_FILE_RETENTION_DAYS", "21"))

# 时间轮转配置（每天凌晨轮转）
LOG_TIME_ROTATE_WHEN = os.getenv("LOG_TIME_ROTATE_WHEN", "midnight")
LOG_TIME_ROTATE_INTERVAL = int(os.getenv("LOG_TIME_ROTATE_INTERVAL", "1"))

LOG_JSON = os.getenv("LOG_JSON", "false").lower() in ("1", "true", "yes")

SQLALCHEMY_LOG_LEVEL = os.getenv("SQLALCHEMY_LOG_LEVEL", "WARNING").upper()
UVICORN_LOG_LEVEL = os.getenv("UVICORN_LOG_LEVEL", LOG_LEVEL)


# --------------------------- 复合轮转处理器 ---------------------------
class TimedSizeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    同时支持按时间（每天）和按文件大小轮转的处理器。
    每次写入前检查文件大小，超过 max_bytes 则立即滚动。
    滚动时自动删除超过保留天数的历史日志文件。
    """

    def __init__(self, filename, when='midnight', interval=1, max_bytes=0,
                 retention_days=30, encoding='utf-8'):
        # 不自动按备份文件数量保留（设为0），由清理函数管理
        super().__init__(filename, when=when, interval=interval,
                         backupCount=0, encoding=encoding)
        self.max_bytes = max_bytes
        self.retention_days = retention_days
        self.suffix = "%Y-%m-%d_%H-%M-%S"  # 滚动时追加的时间戳格式

    def shouldRollover(self, record):
        # 时间条件
        if super().shouldRollover(record):
            return True
        # 大小条件
        if self.max_bytes > 0 and self.stream is not None:
            try:
                if self.stream.tell() >= self.max_bytes:
                    return True
            except (OSError, AttributeError):
                pass
        return False

    def doRollover(self):
        """自定义滚动：父类滚动完毕后，清理过期日志"""
        super().doRollover()
        self._delete_old_logs()

    def _delete_old_logs(self):
        """删除所有超过 retention_days 天的历史日志文件"""
        now = time.time()
        cutoff = now - self.retention_days * 86400
        base_dir = os.path.dirname(self.baseFilename)
        # 匹配以当前 baseFilename 衍生出的所有文件（含滚动备份）
        pattern = os.path.join(base_dir, os.path.basename(self.baseFilename) + ".*")
        for fpath in glob.glob(pattern):
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
            except OSError:
                pass


# --------------------------- 控制台彩色格式化 ---------------------------
class ColoredFormatter(logging.Formatter):
    COLOR_CODES = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
        'RESET': '\033[0m',
    }

    def format(self, record):
        record = logging.makeLogRecord(record.__dict__)
        levelname = record.levelname
        record.levelcolor = self.COLOR_CODES.get(levelname, '')
        record.reset = self.COLOR_CODES['RESET']
        return super().format(record)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        import json
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


# --------------------------- 队列配置（非阻塞） ---------------------------
import queue
import atexit

_log_queue: Optional[queue.Queue] = None
_queue_listener: Optional[logging.handlers.QueueListener] = None


def setup_logging():
    global _log_queue, _queue_listener

    handlers = []

    # 1. 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = JsonFormatter() if LOG_JSON else ColoredFormatter(CONSOLE_FORMAT)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    # 2. 文件处理器（复合轮转）
    if LOG_TO_FILE:
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = TimedSizeRotatingFileHandler(
            filename=LOG_FILE_PATH,
            when=LOG_TIME_ROTATE_WHEN,
            interval=LOG_TIME_ROTATE_INTERVAL,
            max_bytes=LOG_FILE_MAX_BYTES,
            retention_days=LOG_FILE_RETENTION_DAYS,
            encoding="utf-8",
        )
        file_handler.setLevel(LOG_LEVEL)
        file_formatter = JsonFormatter() if LOG_JSON else logging.Formatter(FILE_FORMAT)
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # 3. 创建队列与监听器
    _log_queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(_log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.addHandler(queue_handler)

    _queue_listener = logging.handlers.QueueListener(
        _log_queue, *handlers, respect_handler_level=True
    )
    _queue_listener.start()
    atexit.register(_queue_listener.stop)

    # 4. 第三方库日志
    logging.getLogger("sqlalchemy.engine").setLevel(SQLALCHEMY_LOG_LEVEL)
    logging.getLogger("sqlalchemy.pool").setLevel(SQLALCHEMY_LOG_LEVEL)
    _configure_uvicorn_logging()


def _configure_uvicorn_logging():
    for name in ("uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
        logger.setLevel(UVICORN_LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def reload_logging():
    global _queue_listener
    if _queue_listener:
        _queue_listener.stop()
    setup_logging()