#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用联赛爬虫脚本
支持爬取懂球帝不同联赛的积分榜数据并存储到数据库
"""

import requests
import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from src.team_database import TeamDatabaseManager
from config.config import DONGQIUDI_CONFIG


class UniversalLeagueSpider:
    """
    通用联赛爬虫类
    支持爬取不同联赛的积分榜数据
    """
    
    def __init__(self, league_name: str = "unknown"):
        """
        初始化爬虫
        
        Args:
            league_name: 联赛名称
        """
        self.league_name = league_name
        self.logger = logging.getLogger(__name__)
        self.db_manager = TeamDatabaseManager()
        
        # 设置请求头
        self.headers = DONGQIUDI_CONFIG['headers'].copy()
        self.timeout = DONGQIUDI_CONFIG['timeout']
        
    def extract_standing_data(self, url: str) -> Optional[str]:
        """
        从指定URL提取积分榜数据
        
        Args:
            url: 联赛数据页面URL
            
        Returns:
            提取到的原始数据字符串，如果失败返回None
        """
        try:
            self.logger.info(f"正在请求: {url}")
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            self.logger.info(f"响应状态码: {response.status_code}")
            self.logger.info(f"响应内容长度: {len(response.text)}")
            
            # 多种搜索模式，提高数据提取成功率
            standing_patterns = [
                # 模式1: 搜索包含积分榜关键字段的完整数据块
                r'data:\s*\[\{[^\]]*(?:desc|goals_against|goals_pro|matches_draw|matches_lost|matches_total|matches_won|points|rank|team_id|team_name)[^\]]*\}\]',
                
                # 模式2: 搜索包含team_name和其他关键字段的数据
                r'\[\{[^\]]*team_name[^\]]*team_id[^\]]*team_logo[^\]]*scheme[^\]]*\}[^\]]*\]',
                
                # 模式3: 更宽泛的搜索，寻找包含多个球队数据的数组
                r'\[(?:\{[^\}]*team_name[^\}]*\}[,\s]*){3,}\]',
                
                # 模式4: 搜索JavaScript变量赋值中的数据
                r'(?:data|teams|standing)\s*[:=]\s*\[\{[^\]]*team_name[^\]]*\}[^\]]*\]',
                
                # 模式5: 搜索包含积分榜核心字段的区域
                r'(?=.*team_name)(?=.*team_id)(?=.*points)(?=.*rank).{100,3000}',
            ]
            
            extracted_data = None
            for i, pattern in enumerate(standing_patterns):
                self.logger.info(f"尝试模式 {i+1}: {pattern[:50]}...")
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)
                
                if matches:
                    self.logger.info(f"✅ 模式 {i+1} 找到 {len(matches)} 个匹配")
                    # 选择最长的匹配作为最可能的数据
                    extracted_data = max(matches, key=len)
                    self.logger.info(f"选择数据长度: {len(extracted_data)}")
                    break
                else:
                    self.logger.info(f"❌ 模式 {i+1} 未找到匹配")
            
            if extracted_data:
                self.logger.info(f"成功提取数据，长度: {len(extracted_data)}")
                return extracted_data
            else:
                self.logger.warning("所有模式都未能提取到数据")
                return None
                
        except requests.RequestException as e:
            self.logger.error(f"请求异常: {e}")
            return None
        except Exception as e:
            self.logger.error(f"提取数据异常: {e}")
            return None
    
    def parse_javascript_object(self, js_data: str) -> Optional[List[Dict[str, Any]]]:
        """
        解析JavaScript对象格式的数据
        
        Args:
            js_data: JavaScript对象字符串
            
        Returns:
            解析后的数据列表，如果失败返回None
        """
        try:
            # 清理数据，移除可能的前缀
            cleaned_data = js_data.strip()
            if ':' in cleaned_data and cleaned_data.index(':') < 50:
                cleaned_data = cleaned_data[cleaned_data.index('['):]
            
            # 尝试直接解析JSON
            try:
                parsed_data = json.loads(cleaned_data)
                if isinstance(parsed_data, list) and len(parsed_data) > 0:
                    self.logger.info(f"直接JSON解析成功，获得 {len(parsed_data)} 条记录")
                    return parsed_data
            except json.JSONDecodeError:
                pass
            
            # JavaScript对象转JSON的转换规则
            conversions = [
                # 为未加引号的键名添加引号
                (r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'"\1":'),
                # 为未加引号的字符串值添加引号（排除数字、布尔值、null）
                (r':\s*([a-zA-Z_$][a-zA-Z0-9_$:/\.\-]*?)\s*([,}])', r': "\1"\2'),
                # 处理特殊字符（如$符号）
                (r'([a-zA-Z0-9_])\$([a-zA-Z0-9_])', r'\1_DOLLAR_\2'),
                # 处理单引号
                (r"'", r'"'),
            ]
            
            converted_data = cleaned_data
            for pattern, replacement in conversions:
                converted_data = re.sub(pattern, replacement, converted_data)
            
            # 再次尝试解析
            try:
                parsed_data = json.loads(converted_data)
                if isinstance(parsed_data, list) and len(parsed_data) > 0:
                    self.logger.info(f"转换后JSON解析成功，获得 {len(parsed_data)} 条记录")
                    return parsed_data
            except json.JSONDecodeError as e:
                self.logger.warning(f"转换后仍无法解析JSON: {e}")
            
            # 手动解析JavaScript对象格式
            return self._manual_parse_js_object(cleaned_data)
            
        except Exception as e:
            self.logger.error(f"解析JavaScript对象异常: {e}")
            return None
    
    def _manual_parse_js_object(self, js_data: str) -> Optional[List[Dict[str, Any]]]:
        """
        手动解析JavaScript对象格式的数据
        
        Args:
            js_data: JavaScript对象字符串
            
        Returns:
            解析后的数据列表
        """
        try:
            # 查找所有对象
            object_pattern = r'\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
            objects = re.findall(object_pattern, js_data)
            
            parsed_objects = []
            for obj_content in objects:
                obj_dict = {}
                
                # 解析键值对
                kv_pattern = r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*([^,}]+)'
                matches = re.findall(kv_pattern, obj_content)
                
                for key, value in matches:
                    # 清理值
                    value = value.strip().strip('"\'')
                    obj_dict[key] = value
                
                # 只保留包含必要字段的对象
                if 'team_name' in obj_dict or 'team_id' in obj_dict:
                    parsed_objects.append(obj_dict)
            
            if parsed_objects:
                self.logger.info(f"手动解析成功，获得 {len(parsed_objects)} 条记录")
                return parsed_objects
            else:
                self.logger.warning("手动解析未找到有效对象")
                return None
                
        except Exception as e:
            self.logger.error(f"手动解析异常: {e}")
            return None
    
    def extract_team_info(self, teams_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从解析的数据中提取球队信息
        
        Args:
            teams_data: 解析后的球队数据列表
            
        Returns:
            提取的球队信息列表
        """
        extracted_teams = []
        
        for team_data in teams_data:
            try:
                # 提取必需的字段
                team_info = {
                    'team_name': team_data.get('team_name', ''),
                    'team_id': team_data.get('team_id', ''),
                    'team_logo': team_data.get('team_logo', ''),
                    'scheme': team_data.get('scheme', ''),
                    'league': self.league_name,
                    'extracted_at': datetime.now().isoformat()
                }
                
                # 验证必需字段
                if all([team_info['team_name'], team_info['team_id']]):
                    extracted_teams.append(team_info)
                    self.logger.debug(f"提取球队: {team_info['team_name']} (ID: {team_info['team_id']})")
                else:
                    self.logger.warning(f"球队数据不完整，跳过: {team_data}")
                    
            except Exception as e:
                self.logger.error(f"提取球队信息异常: {e}")
                continue
        
        self.logger.info(f"成功提取 {len(extracted_teams)} 支球队信息")
        return extracted_teams
    
    def save_teams_to_database(self, teams_info: List[Dict[str, Any]]) -> int:
        """
        将球队信息保存到数据库
        
        Args:
            teams_info: 球队信息列表
            
        Returns:
            成功保存的数量
        """
        try:
            # 连接数据库
            if not self.db_manager.connect():
                self.logger.error("数据库连接失败")
                return 0
            
            # 批量插入
            success_count = self.db_manager.insert_teams_batch(teams_info)
            
            self.logger.info(f"数据库保存完成，成功: {success_count}/{len(teams_info)}")
            return success_count
            
        except Exception as e:
            self.logger.error(f"保存到数据库异常: {e}")
            return 0
        finally:
            self.db_manager.close()
    
    def crawl_league(self, url: str) -> Tuple[bool, int]:
        """
        爬取指定联赛的数据
        
        Args:
            url: 联赛数据页面URL
            
        Returns:
            Tuple[bool, int]: (是否成功, 保存的球队数量)
        """
        try:
            self.logger.info(f"开始爬取联赛: {self.league_name}")
            self.logger.info(f"目标URL: {url}")
            
            # 1. 提取原始数据
            raw_data = self.extract_standing_data(url)
            if not raw_data:
                self.logger.error("未能提取到原始数据")
                return False, 0
            
            # 2. 解析数据
            parsed_data = self.parse_javascript_object(raw_data)
            if not parsed_data:
                self.logger.error("未能解析数据")
                return False, 0
            
            # 3. 提取球队信息
            teams_info = self.extract_team_info(parsed_data)
            if not teams_info:
                self.logger.error("未能提取到球队信息")
                return False, 0
            
            # 4. 保存到数据库
            saved_count = self.save_teams_to_database(teams_info)
            
            if saved_count > 0:
                self.logger.info(f"✅ 联赛 {self.league_name} 爬取成功，保存 {saved_count} 支球队")
                return True, saved_count
            else:
                self.logger.error(f"❌ 联赛 {self.league_name} 数据保存失败")
                return False, 0
                
        except Exception as e:
            self.logger.error(f"爬取联赛异常: {e}")
            return False, 0


def crawl_premier_league() -> Tuple[bool, int]:
    """
    爬取英超联赛数据
    
    Returns:
        Tuple[bool, int]: (是否成功, 保存的球队数量)
    """
    spider = UniversalLeagueSpider("英超")
    return spider.crawl_league("https://www.dongqiudi.com/data/1")


def crawl_csl() -> Tuple[bool, int]:
    """
    爬取中超联赛数据
    
    Returns:
        Tuple[bool, int]: (是否成功, 保存的球队数量)
    """
    spider = UniversalLeagueSpider("中超")
    return spider.crawl_league("https://www.dongqiudi.com/data/231")


def crawl_custom_league(league_name: str, url: str) -> Tuple[bool, int]:
    """
    爬取自定义联赛数据
    
    Args:
        league_name: 联赛名称
        url: 联赛数据页面URL
        
    Returns:
        Tuple[bool, int]: (是否成功, 保存的球队数量)
    """
    spider = UniversalLeagueSpider(league_name)
    return spider.crawl_league(url)


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 示例：爬取英超数据
    print("🚀 开始爬取英超数据...")
    success, count = crawl_premier_league()
    
    if success:
        print(f"✅ 英超数据爬取成功，保存了 {count} 支球队")
    else:
        print("❌ 英超数据爬取失败")