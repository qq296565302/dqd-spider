# -*- coding: utf-8 -*-
"""
日志配置模块
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

from config.config import LOG_CONFIG


class LoggerManager:
    """
    日志管理器
    """
    
    def __init__(self):
        """
        初始化日志管理器
        """
        self._loggers = {}
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """
        设置根日志记录器
        """
        # 确保日志目录存在
        log_file_path = Path(LOG_CONFIG['file_path'])
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, LOG_CONFIG['level']))
        
        # 清除现有的处理器
        root_logger.handlers.clear()
        
        # 创建格式化器
        formatter = logging.Formatter(
            fmt=LOG_CONFIG['format'],
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 创建文件处理器（带轮转）
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file_path,
            maxBytes=LOG_CONFIG['max_bytes'],
            backupCount=LOG_CONFIG['backup_count'],
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, LOG_CONFIG['level']))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 创建错误日志文件处理器
        error_log_path = log_file_path.parent / 'error.log'
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_path,
            maxBytes=LOG_CONFIG['max_bytes'],
            backupCount=LOG_CONFIG['backup_count'],
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        获取指定名称的日志记录器
        
        Args:
            name: 日志记录器名称
            
        Returns:
            logging.Logger: 日志记录器实例
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        
        return self._loggers[name]
    
    def set_level(self, level: str, logger_name: Optional[str] = None):
        """
        设置日志级别
        
        Args:
            level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
            logger_name: 日志记录器名称，None表示根记录器
        """
        log_level = getattr(logging, level.upper())
        
        if logger_name:
            logger = self.get_logger(logger_name)
            logger.setLevel(log_level)
        else:
            logging.getLogger().setLevel(log_level)
    
    def add_file_handler(self, 
                        logger_name: str, 
                        file_path: str, 
                        level: str = 'INFO',
                        max_bytes: int = None,
                        backup_count: int = None):
        """
        为指定日志记录器添加文件处理器
        
        Args:
            logger_name: 日志记录器名称
            file_path: 日志文件路径
            level: 日志级别
            max_bytes: 文件最大字节数
            backup_count: 备份文件数量
        """
        logger = self.get_logger(logger_name)
        
        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 创建文件处理器
        if max_bytes and backup_count:
            handler = logging.handlers.RotatingFileHandler(
                filename=file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
        else:
            handler = logging.FileHandler(file_path, encoding='utf-8')
        
        handler.setLevel(getattr(logging, level.upper()))
        
        # 创建格式化器
        formatter = logging.Formatter(
            fmt=LOG_CONFIG['format'],
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
    
    def disable_logger(self, logger_name: str):
        """
        禁用指定的日志记录器
        
        Args:
            logger_name: 日志记录器名称
        """
        logger = self.get_logger(logger_name)
        logger.disabled = True
    
    def enable_logger(self, logger_name: str):
        """
        启用指定的日志记录器
        
        Args:
            logger_name: 日志记录器名称
        """
        logger = self.get_logger(logger_name)
        logger.disabled = False
    
    def log_exception(self, logger_name: str, message: str = "发生异常"):
        """
        记录异常信息
        
        Args:
            logger_name: 日志记录器名称
            message: 异常消息
        """
        logger = self.get_logger(logger_name)
        logger.exception(message)
    
    def create_module_logger(self, module_name: str) -> logging.Logger:
        """
        为模块创建专用的日志记录器
        
        Args:
            module_name: 模块名称
            
        Returns:
            logging.Logger: 模块日志记录器
        """
        logger_name = f"spider.{module_name}"
        logger = self.get_logger(logger_name)
        
        # 为模块创建专用的日志文件
        module_log_path = Path(LOG_CONFIG['file_path']).parent / f"{module_name}.log"
        self.add_file_handler(
            logger_name=logger_name,
            file_path=str(module_log_path),
            level=LOG_CONFIG['level'],
            max_bytes=LOG_CONFIG['max_bytes'],
            backup_count=LOG_CONFIG['backup_count']
        )
        
        return logger


# 创建全局日志管理器实例
logger_manager = LoggerManager()


# 便捷函数
def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称，默认为调用模块名
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return logger_manager.get_logger(name)


def setup_spider_logging():
    """
    设置爬虫项目的日志配置
    """
    # 为主要模块创建专用日志记录器
    modules = ['spider', 'database', 'scheduler']
    
    for module in modules:
        logger_manager.create_module_logger(module)
    
    # 设置第三方库的日志级别
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.INFO)
    logging.getLogger('pymongo').setLevel(logging.WARNING)


# 初始化爬虫日志配置
setup_spider_logging()