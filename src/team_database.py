# -*- coding: utf-8 -*-
"""
球队数据库管理模块
专门用于存储和管理球队信息
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from config.config import MONGO_CONFIG


class TeamDatabaseManager:
    """
    球队数据库管理器
    专门用于管理球队信息的存储和查询
    """
    
    def __init__(self, collection_name: str = "teams"):
        """
        初始化球队数据库管理器
        
        Args:
            collection_name: 集合名称，默认为"teams"
        """
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database] = None
        self.collection: Optional[Collection] = None
        self.collection_name = collection_name
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
            self.collection = self.database[self.collection_name]
            
            # 创建索引
            self._create_indexes()
            
            self.logger.info(f"成功连接到MongoDB数据库: {MONGO_CONFIG['database']}.{self.collection_name}")
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
            # 获取现有索引列表
            existing_indexes = [index['name'] for index in self.collection.list_indexes()]
            
            # 为team_name和team_id组合创建唯一索引，防止重复数据
            if "team_name_1_team_id_1" not in existing_indexes:
                self.collection.create_index([("team_name", 1), ("team_id", 1)], unique=True, name="team_name_1_team_id_1")
            
            # 为联赛创建索引
            if "league_1" not in existing_indexes:
                self.collection.create_index("league", name="league_1")
            
            # 为球队名称创建索引
            if "team_name_1" not in existing_indexes:
                self.collection.create_index("team_name", name="team_name_1")
            
            # 为team_id创建索引
            if "team_id_1" not in existing_indexes:
                self.collection.create_index("team_id", name="team_id_1")
            
            # 为创建时间创建索引
            if "created_at_1" not in existing_indexes:
                self.collection.create_index("created_at", name="created_at_1")
            
            # 为球队名称创建文本索引，便于搜索
            if "team_name_text" not in existing_indexes:
                self.collection.create_index([("team_name", "text")], name="team_name_text")
            
            self.logger.info("球队数据库索引创建成功")
        except Exception as e:
            self.logger.warning(f"创建索引时出现警告: {e}")
    
    def insert_team(self, team_data: Dict[str, Any]) -> bool:
        """
        插入单个球队数据，如果team_name和team_id组合已存在则更新数据
        
        Args:
            team_data: 球队数据字典，必须包含team_id, team_name, team_logo, scheme字段
            
        Returns:
            bool: 插入或更新是否成功
        """
        try:
            # 验证必需字段
            required_fields = ['team_id', 'team_name', 'team_logo', 'scheme']
            for field in required_fields:
                if field not in team_data:
                    self.logger.error(f"缺少必需字段: {field}")
                    return False
            
            # 检查是否存在相同的team_name和team_id组合
            existing_team = self.find_team_by_name_and_id(team_data['team_name'], team_data['team_id'])
            
            if existing_team:
                # 如果存在，则更新数据
                self.logger.info(f"发现相同球队，更新数据: {team_data['team_name']} (ID: {team_data['team_id']})")
                return self.update_team_by_name_and_id(team_data['team_name'], team_data['team_id'], team_data)
            else:
                # 如果不存在，则插入新数据
                # 添加时间戳
                team_data['created_at'] = datetime.now()
                team_data['updated_at'] = datetime.now()
                
                # 插入数据
                result = self.collection.insert_one(team_data)
                
                if result.inserted_id:
                    self.logger.info(f"成功插入球队数据: {team_data['team_name']} (ID: {team_data['team_id']})")
                    return True
                else:
                    self.logger.error(f"插入球队数据失败: {team_data['team_name']}")
                    return False
                    
        except DuplicateKeyError:
            self.logger.warning(f"球队数据已存在: {team_data['team_name']} (ID: {team_data['team_id']})")
            # 尝试更新现有数据
            return self.update_team_by_name_and_id(team_data['team_name'], team_data['team_id'], team_data)
        except Exception as e:
            self.logger.error(f"插入球队数据异常: {e}")
            return False
    
    def insert_teams_batch(self, teams_data: List[Dict[str, Any]]) -> int:
        """
        批量插入球队数据
        
        Args:
            teams_data: 球队数据列表
            
        Returns:
            int: 成功插入的数量
        """
        success_count = 0
        
        for team_data in teams_data:
            if self.insert_team(team_data):
                success_count += 1
        
        self.logger.info(f"批量插入完成，成功: {success_count}/{len(teams_data)}")
        return success_count
    
    def update_team(self, team_id: str, update_data: Dict[str, Any]) -> bool:
        """
        更新球队数据
        
        Args:
            team_id: 球队ID
            update_data: 更新的数据
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 添加更新时间
            update_data['updated_at'] = datetime.now()
            
            # 更新数据
            result = self.collection.update_one(
                {'team_id': team_id},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                self.logger.info(f"成功更新球队数据: {team_id}")
                return True
            else:
                self.logger.warning(f"未找到要更新的球队: {team_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新球队数据异常: {e}")
            return False
    
    def find_team(self, team_id: str) -> Optional[Dict[str, Any]]:
        """
        根据team_id查找球队
        
        Args:
            team_id: 球队ID
            
        Returns:
            Dict[str, Any]: 球队数据，如果未找到返回None
        """
        try:
            result = self.collection.find_one({'team_id': team_id})
            return result
        except Exception as e:
            self.logger.error(f"查找球队数据异常: {e}")
            return None
    
    def find_team_by_name_and_id(self, team_name: str, team_id: str) -> Optional[Dict[str, Any]]:
        """
        根据team_name和team_id组合查找球队
        
        Args:
            team_name: 球队名称
            team_id: 球队ID
            
        Returns:
            Dict[str, Any]: 球队数据，如果未找到返回None
        """
        try:
            result = self.collection.find_one({
                'team_name': team_name,
                'team_id': team_id
            })
            return result
        except Exception as e:
            self.logger.error(f"查找球队数据异常: {e}")
            return None
    
    def update_team_by_name_and_id(self, team_name: str, team_id: str, update_data: Dict[str, Any]) -> bool:
        """
        根据team_name和team_id组合更新球队数据
        
        Args:
            team_name: 球队名称
            team_id: 球队ID
            update_data: 更新的数据
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 添加更新时间
            update_data['updated_at'] = datetime.now()
            
            # 更新数据
            result = self.collection.update_one(
                {
                    'team_name': team_name,
                    'team_id': team_id
                },
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                self.logger.info(f"成功更新球队数据: {team_name} (ID: {team_id})")
                return True
            else:
                self.logger.warning(f"未找到要更新的球队: {team_name} (ID: {team_id})")
                return False
                
        except Exception as e:
            self.logger.error(f"更新球队数据异常: {e}")
            return False
    
    def find_teams_by_league(self, league: str) -> List[Dict[str, Any]]:
        """
        根据联赛查找球队
        
        Args:
            league: 联赛名称
            
        Returns:
            List[Dict[str, Any]]: 球队数据列表
        """
        try:
            results = list(self.collection.find({'league': league}))
            return results
        except Exception as e:
            self.logger.error(f"查找联赛球队数据异常: {e}")
            return []
    
    def search_teams(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索球队（按名称）
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            List[Dict[str, Any]]: 匹配的球队数据列表
        """
        try:
            # 使用文本搜索
            results = list(self.collection.find(
                {'$text': {'$search': keyword}}
            ))
            
            # 如果文本搜索没有结果，尝试模糊匹配
            if not results:
                results = list(self.collection.find(
                    {'team_name': {'$regex': keyword, '$options': 'i'}}
                ))
            
            return results
        except Exception as e:
            self.logger.error(f"搜索球队数据异常: {e}")
            return []
    
    def count_teams(self, query: Dict[str, Any] = None) -> int:
        """
        统计球队数量
        
        Args:
            query: 查询条件，默认为None（统计所有）
            
        Returns:
            int: 球队数量
        """
        try:
            if query is None:
                query = {}
            return self.collection.count_documents(query)
        except Exception as e:
            self.logger.error(f"统计球队数量异常: {e}")
            return 0
    
    def delete_team(self, team_id: str) -> bool:
        """
        删除球队数据
        
        Args:
            team_id: 球队ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            result = self.collection.delete_one({'team_id': team_id})
            
            if result.deleted_count > 0:
                self.logger.info(f"成功删除球队数据: {team_id}")
                return True
            else:
                self.logger.warning(f"未找到要删除的球队: {team_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除球队数据异常: {e}")
            return False
    
    def close(self):
        """
        关闭数据库连接
        """
        if self.client:
            self.client.close()
            self.logger.info("数据库连接已关闭")
    
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


# 创建全局实例
team_db_manager = TeamDatabaseManager()