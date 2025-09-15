#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
懂球帝球队信息爬虫模块
基于Nuxt.js架构的现代前端应用数据爬取
专门用于爬取各大联赛球队相关数据
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from urllib.parse import quote

class TeamSpider:
    """
    懂球帝球队数据爬虫
    基于Nuxt.js架构的现代前端应用数据提取器
    """
    
    def __init__(self):
        """
        初始化爬虫
        """
        self.session = requests.Session()
        self.base_url = 'https://www.dongqiudi.com'
        self.api_base_url = 'https://sport-data.dongqiudi.com'
        
        # 联赛信息映射
        self.league_mapping = {
            1: {'name': '英超', 'season_id': 21740, 'url_path': '/data/1'},
            2: {'name': '西甲', 'season_id': 21741, 'url_path': '/data/2'},
            3: {'name': '意甲', 'season_id': 21742, 'url_path': '/data/3'},
            4: {'name': '德甲', 'season_id': 21743, 'url_path': '/data/4'},
            5: {'name': '法甲', 'season_id': 21744, 'url_path': '/data/5'}
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.dongqiudi.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin'
        }
        self.session.headers.update(self.headers)
        self.logger = logging.getLogger(__name__)
        
    def get_all_leagues_teams(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取所有联赛的球队信息
        
        Returns:
            包含所有联赛球队信息的字典
        """
        all_teams = {}
        
        for league_id, league_info in self.league_mapping.items():
            self.logger.info(f"正在获取{league_info['name']}球队信息...")
            teams = self.get_league_teams(league_id)
            if teams:
                all_teams[league_info['name']] = teams
                self.logger.info(f"✅ 成功获取{league_info['name']} {len(teams)}支球队")
            else:
                self.logger.warning(f"❌ 未能获取{league_info['name']}球队信息")
                all_teams[league_info['name']] = []
            
            # 添加延迟避免请求过于频繁
            time.sleep(1)
            
        return all_teams
    
    def get_league_teams(self, league_id: int) -> List[Dict[str, Any]]:
        """
        获取指定联赛的球队信息
        
        Args:
            league_id: 联赛ID (1=英超, 2=西甲, 3=意甲, 4=德甲, 5=法甲)
            
        Returns:
            球队信息列表
        """
        if league_id not in self.league_mapping:
            self.logger.error(f"未知的联赛ID: {league_id}")
            return []
            
        league_info = self.league_mapping[league_id]
        
        # 方法1: 尝试从API获取积分榜数据
        teams = self._get_teams_from_api(league_id)
        if teams:
            return teams
            
        # 方法2: 尝试从页面提取Nuxt.js数据
        teams = self._get_teams_from_page(league_id)
        if teams:
            return teams
            
        self.logger.warning(f"所有方法都未能获取到{league_info['name']}的球队信息")
        return []
        
    def get_league_data(self, league_id: int = 1) -> Optional[Dict[str, Any]]:
        """
        获取联赛数据（保持向后兼容）
        
        Args:
            league_id: 联赛ID (1=英超, 2=西甲, 3=意甲, 4=德甲, 5=法甲)
            
        Returns:
            联赛数据字典或None
        """
        teams = self.get_league_teams(league_id)
        if teams:
            league_info = self.league_mapping.get(league_id, {})
            return {
                'type': 'league_teams',
                'source': 'api_or_page',
                'league_name': league_info.get('name', f'联赛{league_id}'),
                'teams': teams,
                'total_teams': len(teams),
                'league_id': league_id,
                'crawl_time': datetime.now().isoformat()
            }
        return None
    
    def _get_teams_from_api(self, league_id: int) -> List[Dict[str, Any]]:
        """
        从API获取球队数据
        
        Args:
            league_id: 联赛ID
            
        Returns:
            格式化后的球队信息列表
        """
        league_info = self.league_mapping[league_id]
        season_id = league_info['season_id']
        league_name = league_info['name']
        
        # 构建API URL
        api_url = f"{self.api_base_url}/soccer/biz/data/standing?season_id={season_id}&app=dqd&version=0&platform=web&language=zh-cn&app_type="
        
        try:
            self.logger.info(f"正在调用API获取{league_name}数据...")
            response = self.session.get(api_url, timeout=10)
            
            if response and response.status_code == 200:
                try:
                    api_data = response.json()
                    raw_teams = self._process_api_teams_data(api_data, league_name)
                    if raw_teams:
                        return self.format_team_data(raw_teams, league_name)
                except json.JSONDecodeError as e:
                    self.logger.error(f"API响应JSON解析失败: {e}")
            else:
                self.logger.error(f"API请求失败，状态码: {response.status_code if response else 'None'}")
                
        except Exception as e:
            self.logger.error(f"调用API获取{league_name}数据时发生异常: {e}")
            
        return []
    
    def _get_teams_from_page(self, league_id: int) -> List[Dict[str, Any]]:
        """
        从页面提取Nuxt.js数据获取球队信息
        
        Args:
            league_id: 联赛ID
            
        Returns:
            格式化后的球队信息列表
        """
        league_info = self.league_mapping[league_id]
        league_name = league_info['name']
        url = f"{self.base_url}{league_info['url_path']}"
        
        try:
            self.logger.info(f"正在访问{league_name}页面: {url}")
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                raw_teams = self._extract_nuxt_teams_data(response.text, league_name)
                if raw_teams:
                    return self.format_team_data(raw_teams, league_name)
                else:
                    self.logger.warning(f"未能从{league_name}页面提取球队数据")
            else:
                self.logger.error(f"{league_name}页面访问失败，状态码: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"获取{league_name}页面数据时发生异常: {e}")
            
        return []
    
    def _process_api_teams_data(self, api_data: Dict[str, Any], league_name: str) -> List[Dict[str, Any]]:
        """
        处理API返回的球队数据
        
        Args:
            api_data: API返回的原始数据
            league_name: 联赛名称
            
        Returns:
            球队信息列表
        """
        teams = []
        
        try:
            # 检查是否是标准的{code, message, data}格式
            if api_data.get('code') == 0 and api_data.get('data'):
                data = api_data['data']
            else:
                data = api_data
            
            # 从积分榜数据中提取球队信息
            if 'standings' in data:
                standings_data = data['standings']
                
                for standing in standings_data:
                    if 'team' in standing:
                        team = standing['team']
                        team_info = {
                            'team_id': team.get('id'),
                            'team_name': team.get('name'),
                            'team_name_en': team.get('name_en', team.get('name')),
                            'team_logo': team.get('logo'),
                            'rank': standing.get('rank'),
                            'points': standing.get('points'),
                            'matches': standing.get('matches'),
                            'wins': standing.get('wins'),
                            'draws': standing.get('draws'),
                            'losses': standing.get('losses')
                        }
                        teams.append(team_info)
            
            self.logger.info(f"从API成功提取{league_name} {len(teams)}支球队数据")
                
        except Exception as e:
            self.logger.error(f"处理{league_name}API数据时发生异常: {e}")
            
        return teams
    
    def _extract_nuxt_teams_data(self, html_content: str, league_name: str) -> List[Dict[str, Any]]:
        """
        从Nuxt.js页面提取球队数据
        
        Args:
            html_content: 页面HTML内容
            league_name: 联赛名称
            
        Returns:
            球队信息列表
        """
        teams = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 尝试从script标签中提取JSON数据
            scripts = soup.find_all('script')
            
            for script in scripts:
                if not script.string:
                    continue
                    
                # 查找Nuxt.js数据模式
                patterns = [
                    r'window\.__NUXT__\s*=\s*(.+);',
                    r'window\.__INITIAL_STATE__\s*=\s*(.+);',
                    r'"standings"\s*:\s*(\[.+?\])',
                    r'"teams"\s*:\s*(\[.+?\])',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        try:
                            json_str = match.group(1)
                            if json_str.endswith(';'):
                                json_str = json_str[:-1]
                            
                            if json_str.startswith('(function'):
                                continue
                                
                            data = json.loads(json_str)
                            teams = self._extract_teams_from_nuxt_data(data)
                            if teams:
                                self.logger.info(f"从{league_name}页面成功提取 {len(teams)} 支球队数据")
                                return teams
                                
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            self.logger.error(f"从{league_name}页面提取数据时发生异常: {e}")
            
        return teams
    
    def _extract_teams_from_nuxt_data(self, data: Any) -> List[Dict[str, Any]]:
        """
        从Nuxt.js数据中递归提取球队信息
        
        Args:
            data: Nuxt.js数据
            
        Returns:
            球队信息列表
        """
        teams = []
        
        def search_teams(obj):
            if isinstance(obj, dict):
                # 检查是否是积分榜数据
                if 'standings' in obj and isinstance(obj['standings'], list):
                    for standing in obj['standings']:
                        if isinstance(standing, dict) and 'team' in standing:
                            team = standing['team']
                            team_info = {
                                'team_id': team.get('id'),
                                'team_name': team.get('name'),
                                'team_name_en': team.get('name_en', team.get('name')),
                                'team_logo': team.get('logo'),
                                'rank': standing.get('rank'),
                                'points': standing.get('points'),
                                'matches': standing.get('matches'),
                                'wins': standing.get('wins'),
                                'draws': standing.get('draws'),
                                'losses': standing.get('losses')
                            }
                            teams.append(team_info)
                
                # 检查是否直接是球队列表
                elif 'teams' in obj and isinstance(obj['teams'], list):
                    for team in obj['teams']:
                        if isinstance(team, dict) and 'name' in team:
                            team_info = {
                                'team_id': team.get('id'),
                                'team_name': team.get('name'),
                                'team_name_en': team.get('name_en', team.get('name')),
                                'team_logo': team.get('logo'),
                                'rank': 0,
                                'points': 0,
                                'matches': 0,
                                'wins': 0,
                                'draws': 0,
                                'losses': 0
                            }
                            teams.append(team_info)
                
                # 递归搜索其他字段
                for value in obj.values():
                    search_teams(value)
                    
            elif isinstance(obj, list):
                for item in obj:
                    search_teams(item)
        
        search_teams(data)
        return teams
    
    def format_team_data(self, teams: List[Dict[str, Any]], league_name: str) -> List[Dict[str, Any]]:
        """
        格式化球队数据为标准格式
        
        Args:
            teams: 原始球队数据列表
            league_name: 联赛名称
            
        Returns:
            格式化后的球队数据列表
        """
        formatted_teams = []
        
        for team in teams:
            if not team.get('team_id') or not team.get('team_name'):
                continue
                
            team_id = str(team['team_id'])
            team_name = team['team_name']
            team_logo = team.get('team_logo', '')
            
            # 生成scheme字段
            scheme = f"dongqiudi://v1/data/team/{team_id}"
            
            formatted_team = {
                'team_name': team_name,
                'team_id': team_id,
                'team_logo': team_logo,
                'scheme': scheme,
                'league': league_name,
                'team_name_en': team.get('team_name_en', team_name),
                'rank': team.get('rank', 0),
                'points': team.get('points', 0),
                'matches': team.get('matches', 0),
                'wins': team.get('wins', 0),
                'draws': team.get('draws', 0),
                'losses': team.get('losses', 0)
            }
            
            formatted_teams.append(formatted_team)
            
        return formatted_teams
     
    def _extract_data_from_page(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        从页面HTML中提取数据（保持向后兼容）
        
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
        teams = self.get_league_teams(league_id=1)
        return teams if teams else []
    
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
    
    def _get_league_data_from_api(self, league_id: int) -> Optional[Dict[str, Any]]:
        """
        直接从API获取联赛数据
        
        Args:
            league_id: 联赛ID
            
        Returns:
            API数据或None
        """
        # 联赛ID到season_id的映射
        season_mapping = {
            1: 21740,  # 英超
            2: 21741,  # 西甲
            3: 21742,  # 意甲
            4: 21743,  # 德甲
            5: 21744   # 法甲
        }
        
        season_id = season_mapping.get(league_id)
        if not season_id:
            self.logger.error(f"未知的联赛ID: {league_id}")
            return None
            
        # 构建API URL
        api_url = f"https://sport-data.dongqiudi.com/soccer/biz/data/standing?season_id={season_id}&app=dqd&version=0&platform=web&language=zh-cn&app_type="
        
        try:
            self.logger.info(f"正在调用API获取联赛 {league_id} 数据...")
            response = self.session.get(api_url, timeout=10)
            
            if response and response.status_code == 200:
                try:
                    api_data = response.json()
                    
                    # 检查是否是标准的{code, message, data}格式
                    if api_data.get('code') == 0 and api_data.get('data'):
                        return self._process_api_data(api_data['data'])
                    # 检查是否直接包含standings数据
                    elif 'standings' in api_data:
                        return self._process_api_data(api_data)
                    else:
                        self.logger.warning(f"API返回未知格式")
                except json.JSONDecodeError as e:
                    self.logger.error(f"API响应JSON解析失败: {e}")
                    self.logger.error(f"响应内容: {response.text[:500]}")
            else:
                self.logger.error(f"API请求失败，状态码: {response.status_code if response else 'None'}")
                
        except Exception as e:
            self.logger.error(f"调用API获取联赛 {league_id} 数据时发生异常: {e}")
            
        return None
    
    def _process_api_data(self, api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理API返回的数据
        
        Args:
            api_data: API返回的原始数据
            
        Returns:
            处理后的数据字典
        """
        try:
            teams = []
            
            # 从积分榜数据中提取球队信息
            if 'standings' in api_data:
                standings_data = api_data['standings']
                
                for standing in standings_data:
                    if 'team' in standing:
                        team = standing['team']
                        team_info = {
                            'team_id': team.get('id'),
                            'team_name': team.get('name'),
                            'team_name_en': team.get('name_en', team.get('name')),
                            'team_logo': team.get('logo'),
                            'rank': standing.get('rank'),
                            'points': standing.get('points'),
                            'matches': standing.get('matches'),
                            'wins': standing.get('wins'),
                            'draws': standing.get('draws'),
                            'losses': standing.get('losses')
                        }
                        teams.append(team_info)
            
            # 处理新的数据格式：template + content结构
            elif 'template' in api_data and 'content' in api_data:
                content = api_data['content']
                
                # 检查content中是否有rounds字段（比赛数据）
                if 'rounds' in content:
                    # 从比赛数据中提取球队信息
                    teams_set = set()
                    
                    for round_data in content['rounds']:
                        if 'content' in round_data and 'data' in round_data['content']:
                            for match in round_data['content']['data']:
                                # 提取主队信息
                                if 'team_A_id' in match and 'team_A_name' in match:
                                    team_id = str(match['team_A_id'])
                                    if team_id not in teams_set:
                                        teams_set.add(team_id)
                                        team_info = {
                                            'team_id': team_id,
                                            'team_name': match['team_A_name'],
                                            'team_name_en': match.get('team_A_short_name', match['team_A_name']),
                                            'team_logo': match.get('team_A_logo', ''),
                                            'rank': 0,
                                            'points': 0,
                                            'matches': 0,
                                            'wins': 0,
                                            'draws': 0,
                                            'losses': 0
                                        }
                                        teams.append(team_info)
                                
                                # 提取客队信息
                                if 'team_B_id' in match and 'team_B_name' in match:
                                    team_id = str(match['team_B_id'])
                                    if team_id not in teams_set:
                                        teams_set.add(team_id)
                                        team_info = {
                                            'team_id': team_id,
                                            'team_name': match['team_B_name'],
                                            'team_name_en': match.get('team_B_short_name', match['team_B_name']),
                                            'team_logo': match.get('team_B_logo', ''),
                                            'rank': 0,
                                            'points': 0,
                                            'matches': 0,
                                            'wins': 0,
                                            'draws': 0,
                                            'losses': 0
                                        }
                                        teams.append(team_info)
                    
                    if teams:
                        return {
                            'type': 'api_matches',
                            'source': 'api',
                            'teams': teams,
                            'total_teams': len(teams),
                            'league_id': api_data.get('season_id'),
                            'crawl_time': datetime.now().isoformat()
                        }
            
            if teams:
                return {
                    'type': 'api_standings',
                    'source': 'api',
                    'teams': teams,
                    'total_teams': len(teams),
                    'league_id': api_data.get('season_id'),
                    'crawl_time': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"处理API数据时发生异常: {e}")
            
        return None

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