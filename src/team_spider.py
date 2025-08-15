#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
懂球帝球队信息爬虫模块
专门用于爬取球队相关数据
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

class TeamSpider:
    """
    懂球帝球队数据爬虫
    """
    
    def __init__(self):
        """
        初始化爬虫
        """
        self.session = requests.Session()
        self.base_url = 'https://www.dongqiudi.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.dongqiudi.com/'
        }
        self.session.headers.update(self.headers)
        self.logger = logging.getLogger(__name__)
        
    def get_league_data(self, league_id: int = 1) -> Optional[Dict[str, Any]]:
        """
        获取联赛数据
        
        Args:
            league_id: 联赛ID (1=英超, 2=西甲, 3=意甲, 4=德甲, 5=法甲)
            
        Returns:
            联赛数据字典或None
        """
        url = f'{self.base_url}/data/{league_id}'
        
        try:
            self.logger.info(f"正在获取联赛数据: {url}")
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                # 尝试多种方法提取数据
                data = self._extract_data_from_page(response.text)
                if data:
                    data['league_id'] = league_id
                    data['crawl_time'] = datetime.now().isoformat()
                    return data
                else:
                    self.logger.warning(f"未能从页面提取数据: {url}")
            else:
                self.logger.error(f"请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"获取联赛数据异常: {e}")
            
        return None
    
    def _extract_data_from_page(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        从页面HTML中提取数据
        
        Args:
            html_content: 页面HTML内容
            
        Returns:
            提取的数据字典或None
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 方法1: 尝试从script标签中提取JSON数据
            json_data = self._extract_json_from_scripts(soup)
            if json_data:
                return json_data
            
            # 方法2: 从HTML表格中提取积分榜数据
            table_data = self._extract_table_data(soup)
            if table_data:
                return table_data
            
            # 方法3: 从页面文本中提取球队信息
            text_data = self._extract_text_data(html_content)
            if text_data:
                return text_data
                
        except Exception as e:
            self.logger.error(f"数据提取异常: {e}")
            
        return None
    
    def _extract_json_from_scripts(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        从script标签中提取JSON数据
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            提取的JSON数据或None
        """
        scripts = soup.find_all('script')
        
        for script in scripts:
            if not script.string:
                continue
                
            # 查找各种可能的数据模式
            patterns = [
                r'window\.__NUXT__\s*=\s*(.+);',
                r'window\.__INITIAL_STATE__\s*=\s*(.+);',
                r'var\s+initialData\s*=\s*(.+);',
                r'"standings"\s*:\s*(\[.+?\])',
                r'"teams"\s*:\s*(\[.+?\])',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, script.string, re.DOTALL)
                if match:
                    try:
                        # 尝试解析JSON
                        json_str = match.group(1)
                        if json_str.endswith(';'):
                            json_str = json_str[:-1]
                        
                        # 如果是函数调用，跳过
                        if json_str.startswith('(function'):
                            continue
                            
                        data = json.loads(json_str)
                        self.logger.info("成功从script标签提取JSON数据")
                        return self._process_json_data(data)
                        
                    except json.JSONDecodeError:
                        continue
                        
        return None
    
    def _extract_table_data(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        从HTML表格中提取积分榜数据
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            提取的表格数据或None
        """
        # 查找积分榜表格
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > 5:  # 至少有几行数据
                standings = []
                
                for i, row in enumerate(rows[1:]):  # 跳过表头
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 6:  # 至少有基本的积分榜列
                        try:
                            team_data = {
                                'rank': i + 1,
                                'team_name': cells[1].get_text(strip=True) if len(cells) > 1 else '',
                                'matches': int(cells[2].get_text(strip=True)) if len(cells) > 2 and cells[2].get_text(strip=True).isdigit() else 0,
                                'wins': int(cells[3].get_text(strip=True)) if len(cells) > 3 and cells[3].get_text(strip=True).isdigit() else 0,
                                'draws': int(cells[4].get_text(strip=True)) if len(cells) > 4 and cells[4].get_text(strip=True).isdigit() else 0,
                                'losses': int(cells[5].get_text(strip=True)) if len(cells) > 5 and cells[5].get_text(strip=True).isdigit() else 0,
                                'points': int(cells[-1].get_text(strip=True)) if cells[-1].get_text(strip=True).isdigit() else 0
                            }
                            
                            if team_data['team_name']:  # 确保有球队名称
                                standings.append(team_data)
                                
                        except (ValueError, IndexError):
                            continue
                
                if standings:
                    self.logger.info(f"成功从表格提取 {len(standings)} 支球队数据")
                    return {
                        'type': 'standings',
                        'data': standings,
                        'source': 'html_table'
                    }
                    
        return None
    
    def _extract_text_data(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        从页面文本中提取球队信息
        
        Args:
            html_content: HTML内容
            
        Returns:
            提取的文本数据或None
        """
        # 英超球队名称模式
        team_patterns = [
            r'"(Arsenal|Chelsea|Liverpool|Manchester City|Manchester United|Tottenham|Brighton|Newcastle|Aston Villa|West Ham|Crystal Palace|Fulham|Brentford|Wolves|Everton|Burnley|Sheffield United|Luton Town|Bournemouth|Nottingham Forest)"',
            r'"(阿森纳|切尔西|利物浦|曼城|曼联|热刺|布莱顿|纽卡斯尔|阿斯顿维拉|西汉姆|水晶宫|富勒姆|布伦特福德|狼队|埃弗顿|伯恩利|谢菲尔德联|卢顿|伯恩茅斯|诺丁汉森林)"'
        ]
        
        teams = set()
        for pattern in team_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            teams.update(matches)
        
        if teams:
            self.logger.info(f"从文本提取到 {len(teams)} 支球队")
            team_list = [{'name': team, 'name_en': team} for team in sorted(teams)]
            return {
                'type': 'teams',
                'data': team_list,
                'source': 'text_extraction'
            }
            
        return None
    
    def _process_json_data(self, data: Any) -> Dict[str, Any]:
        """
        处理提取的JSON数据
        
        Args:
            data: 原始JSON数据
            
        Returns:
            处理后的数据字典
        """
        result = {
            'type': 'json',
            'source': 'script_tag',
            'data': data
        }
        
        # 尝试从JSON中提取有用信息
        if isinstance(data, dict):
            # 查找可能的球队或积分榜数据
            for key in ['standings', 'teams', 'data', 'state']:
                if key in data:
                    result[f'extracted_{key}'] = data[key]
                    
        return result
    
    def get_premier_league_teams(self) -> List[Dict[str, Any]]:
        """
        获取英超球队信息
        
        Returns:
            球队信息列表
        """
        data = self.get_league_data(league_id=1)
        
        if data and 'data' in data:
            if data['type'] == 'standings':
                return data['data']
            elif data['type'] == 'teams':
                return data['data']
            elif data['type'] == 'json':
                # 从JSON数据中提取球队信息
                return self._extract_teams_from_json(data['data'])
        
        return []
    
    def _extract_teams_from_json(self, json_data: Any) -> List[Dict[str, Any]]:
        """
        从JSON数据中提取球队信息
        
        Args:
            json_data: JSON数据
            
        Returns:
            球队信息列表
        """
        teams = []
        
        def search_teams(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key.lower() in ['teams', 'standings', 'clubs']:
                        if isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict) and 'name' in item:
                                    teams.append(item)
                    else:
                        search_teams(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    search_teams(item, f"{path}[{i}]")
        
        search_teams(json_data)
        return teams

# 创建全局实例
team_spider = TeamSpider()

if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    print("正在测试球队爬虫...")
    teams = team_spider.get_premier_league_teams()
    
    if teams:
        print(f"✅ 成功获取 {len(teams)} 支球队信息:")
        for i, team in enumerate(teams[:10], 1):  # 只显示前10支
            print(f"{i}. {team}")
    else:
        print("❌ 未能获取球队信息")