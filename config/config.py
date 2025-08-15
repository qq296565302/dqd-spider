# -*- coding: utf-8 -*-
"""
项目配置文件
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# MongoDB配置
MONGO_CONFIG = {
    'host': 'localhost',
    'port': 27017,
    'database': 'thunderstorm-news',
    'collection': 'dongqiudi_news'
}

# 懂球帝网站配置
DONGQIUDI_CONFIG = {
    'base_url': 'https://www.dongqiudi.com/',
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    },
    'timeout': 30,
    'retry_times': 3,
    'retry_delay': 5
}

# 定时任务配置
SCHEDULER_CONFIG = {
    'interval_minutes': 30,  # 每30分钟执行一次
    'max_workers': 5,
    'timezone': 'Asia/Shanghai'
}

# 日志配置
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_path': BASE_DIR / 'logs' / 'spider.log',
    'max_bytes': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}

# 数据存储配置
DATA_CONFIG = {
    'save_to_file': True,
    'file_path': BASE_DIR / 'data' / 'dongqiudi_data.json',
    'save_to_mongo': True
}