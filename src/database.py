# -*- coding: utf-8 -*-
"""
MongoDB数据库连接模块
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from config.config import MONGO_CONFIG


class MongoDBManager:
    """
    MongoDB数据库管理器
    """
    
    def __init__(self):
        """
        初始化MongoDB连接
        """
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database] = None
        self.collection: Optional[Collection] = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """
        连接到MongoDB数据库
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 构建连接字符串
            connection_string = f"mongodb://{MONGO_CONFIG['host']}:{MONGO_CONFIG['port']}/"
            
            # 创建客户端连接
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=5000,  # 5秒超时
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # 测试连接
            self.client.admin.command('ping')
            
            # 获取数据库和集合
            self.database = self.client[MONGO_CONFIG['database']]
            self.collection = self.database[MONGO_CONFIG['collection']]
            
            # 创建索引
            self._create_indexes()
            
            self.logger.info(f"成功连接到MongoDB数据库: {MONGO_CONFIG['database']}")
            return True
            
        except ConnectionFailure as e:
            self.logger.error(f"MongoDB连接失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"MongoDB连接异常: {e}")
            return False
    
    def _create_indexes(self):
        """
        创建数据库索引
        """
        try:
            # 为URL创建唯一索引，防止重复数据
            self.collection.create_index("url", unique=True)
            # 为时间创建索引，便于查询
            self.collection.create_index("created_at")
            # 为标题创建文本索引，便于搜索
            self.collection.create_index([("title", "text"), ("content", "text")])
            
            self.logger.info("数据库索引创建成功")
        except Exception as e:
            self.logger.warning(f"创建索引时出现警告: {e}")
    
    def insert_news(self, news_data: Dict[str, Any]) -> bool:
        """
        插入新闻数据
        
        Args:
            news_data: 新闻数据字典
            
        Returns:
            bool: 插入是否成功
        """
        try:
            # 添加创建时间
            news_data['created_at'] = datetime.now()
            news_data['updated_at'] = datetime.now()
            
            # 插入数据
            result = self.collection.insert_one(news_data)
            
            if result.inserted_id:
                self.logger.info(f"成功插入新闻数据: {news_data.get('title', 'Unknown')}")
                return True
            else:
                self.logger.error("插入新闻数据失败")
                return False
                
        except DuplicateKeyError:
            self.logger.warning(f"新闻数据已存在，跳过插入: {news_data.get('url', 'Unknown')}")
            return False
        except Exception as e:
            self.logger.error(f"插入新闻数据异常: {e}")
            return False
    
    def insert_many_news(self, news_list: List[Dict[str, Any]]) -> int:
        """
        批量插入新闻数据
        
        Args:
            news_list: 新闻数据列表
            
        Returns:
            int: 成功插入的数据条数
        """
        if not news_list:
            return 0
            
        success_count = 0
        current_time = datetime.now()
        
        # 为每条数据添加时间戳
        for news in news_list:
            news['created_at'] = current_time
            news['updated_at'] = current_time
        
        try:
            # 批量插入，忽略重复数据
            result = self.collection.insert_many(news_list, ordered=False)
            success_count = len(result.inserted_ids)
            self.logger.info(f"批量插入成功: {success_count}/{len(news_list)} 条数据")
            
        except Exception as e:
            # 如果批量插入失败，尝试逐条插入
            self.logger.warning(f"批量插入失败，尝试逐条插入: {e}")
            for news in news_list:
                if self.insert_news(news):
                    success_count += 1
        
        return success_count
    
    def find_news(self, query: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        查询新闻数据
        
        Args:
            query: 查询条件
            limit: 返回数据条数限制
            
        Returns:
            List[Dict]: 查询结果列表
        """
        try:
            if query is None:
                query = {}
                
            cursor = self.collection.find(query).limit(limit).sort("created_at", -1)
            return list(cursor)
            
        except Exception as e:
            self.logger.error(f"查询新闻数据异常: {e}")
            return []
    
    def count_news(self, query: Dict[str, Any] = None) -> int:
        """
        统计新闻数据条数
        
        Args:
            query: 查询条件
            
        Returns:
            int: 数据条数
        """
        try:
            if query is None:
                query = {}
            return self.collection.count_documents(query)
        except Exception as e:
            self.logger.error(f"统计新闻数据异常: {e}")
            return 0
    
    def update_news(self, query: Dict[str, Any], update_data: Dict[str, Any]) -> bool:
        """
        更新新闻数据
        
        Args:
            query: 查询条件
            update_data: 更新数据
            
        Returns:
            bool: 更新是否成功
        """
        try:
            update_data['updated_at'] = datetime.now()
            result = self.collection.update_many(query, {'$set': update_data})
            
            if result.modified_count > 0:
                self.logger.info(f"成功更新 {result.modified_count} 条新闻数据")
                return True
            else:
                self.logger.warning("没有找到匹配的数据进行更新")
                return False
                
        except Exception as e:
            self.logger.error(f"更新新闻数据异常: {e}")
            return False
    
    def delete_news(self, query: Dict[str, Any]) -> bool:
        """
        删除新闻数据
        
        Args:
            query: 查询条件
            
        Returns:
            bool: 删除是否成功
        """
        try:
            result = self.collection.delete_many(query)
            
            if result.deleted_count > 0:
                self.logger.info(f"成功删除 {result.deleted_count} 条新闻数据")
                return True
            else:
                self.logger.warning("没有找到匹配的数据进行删除")
                return False
                
        except Exception as e:
            self.logger.error(f"删除新闻数据异常: {e}")
            return False
    
    def close(self):
        """
        关闭数据库连接
        """
        if self.client:
            self.client.close()
            self.logger.info("MongoDB连接已关闭")
    
    def __enter__(self):
        """
        上下文管理器入口
        """
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理器出口
        """
        self.close()


# 创建全局数据库管理器实例
db_manager = MongoDBManager()