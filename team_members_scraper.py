#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
球队人员数据爬虫
爬取球队页面中的所有人员信息（球员、教练、工作人员等）
支持批量爬取多个球队的人员数据并保存到数据库
"""

import requests
from bs4 import BeautifulSoup
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import os
import sys

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from team_database import TeamDatabaseManager

class TeamMemberScraper:
    """球队人员数据爬虫类"""
    
    def __init__(self):
        """初始化爬虫"""
        # 初始化数据库管理器
        self.db_manager = TeamDatabaseManager()
        if not self.db_manager.connect():
            raise Exception("数据库连接失败")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
        # 设置连接池和重试
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('team_members_scraper.log', encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def scrape_team_members(self, url: str) -> Optional[Dict[str, Any]]:
        """爬取球队人员数据
        
        Args:
            url: 球队页面URL
            
        Returns:
            包含所有人员数据的字典，如果失败返回None
        """
        try:
            self.logger.info(f"开始爬取球队人员数据: {url}")
            
            # 发送请求，增加重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.logger.info(f"尝试第 {attempt + 1} 次请求...")
                    response = self.session.get(url, timeout=60, verify=False)
                    response.raise_for_status()
                    response.encoding = 'utf-8'
                    break
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if attempt == max_retries - 1:
                        raise e
                    self.logger.warning(f"第 {attempt + 1} 次请求失败，等待重试: {e}")
                    time.sleep(2 ** attempt)  # 指数退避
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取schema数据（包含person_id和detailed_type）
            schema_data = self._extract_schema_data(soup)
            # 保存schema数据用于调试
            self._last_schema_data = schema_data
            
            # 查找team-player-data元素
            team_player_element = soup.find(class_='team-player-data')
            
            if not team_player_element:
                self.logger.error("未找到class为team-player-data的元素")
                return None
            
            # 查找所有analysis-list-item子元素
            member_items = team_player_element.find_all(class_='analysis-list-item')
            
            self.logger.info(f"找到 {len(member_items)} 个人员项目")
            
            if len(member_items) == 0:
                self.logger.warning("未找到任何人员项目")
                return None
            
            # 解析人员数据
            members_data = []
            for i, item in enumerate(member_items):
                member_data = self._extract_member_data(item, i + 1)
                if member_data:
                    # 如果有schema数据，尝试通过姓名匹配合并person_id和detailed_type
                    if schema_data:
                        matched_schema = self._match_member_with_schema(member_data, schema_data)
                        if matched_schema:
                            member_data['person_id'] = matched_schema.get('person_id', '')
                            member_data['detailed_type'] = matched_schema.get('detailed_type', '')
                            self.logger.debug(f"为 {member_data.get('name', 'Unknown')} 匹配到schema数据")
                        else:
                            # 如果无法匹配，使用索引匹配（作为备选方案）
                            if i < len(schema_data):
                                schema_member = schema_data[i]
                                member_data['person_id'] = schema_member.get('person_id', '')
                                member_data['detailed_type'] = schema_member.get('detailed_type', '')
                                self.logger.debug(f"为 {member_data.get('name', 'Unknown')} 使用索引匹配schema数据")
                            else:
                                member_data['person_id'] = ''
                                member_data['detailed_type'] = ''
                    else:
                        member_data['person_id'] = ''
                        member_data['detailed_type'] = ''
                    
                    members_data.append(member_data)
            
            result = {
                'url': url,
                'scrape_time': datetime.now().isoformat(),
                'total_members': len(members_data),
                'members': members_data,
                'has_schema_data': bool(schema_data)
            }
            
            self.logger.info(f"成功解析 {len(members_data)} 名人员的数据")
            if schema_data:
                self.logger.info(f"成功提取schema数据，包含 {len(schema_data)} 个人员的详细信息")
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"网络请求失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"爬取过程中发生异常: {e}")
            return None
    
    def _extract_schema_data(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """从网页中提取schema数据（包含person_id和detailed_type）
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            包含人员schema数据的列表
        """
        try:
            # 方法1: 查找JSON-LD结构化数据
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            if json_ld_scripts:
                self.logger.info(f"找到 {len(json_ld_scripts)} 个JSON-LD script标签")
                for script in json_ld_scripts:
                    try:
                        json_data = json.loads(script.get_text())
                        # 查找人员相关数据
                        members_data = self._extract_members_from_json_ld(json_data)
                        if members_data:
                            return members_data
                    except json.JSONDecodeError:
                        continue
            
            # 方法2: 查找data-*属性中的人员ID
            members_with_ids = []
            member_elements = soup.find_all(class_='analysis-list-item')
            self.logger.info(f"找到 {len(member_elements)} 个analysis-list-item元素")
            
            for i, element in enumerate(member_elements):
                member_info = {'index': i}
                
                # 查找所有属性
                all_attrs = element.attrs
                if all_attrs:
                    self.logger.debug(f"人员 {i+1} 的属性: {all_attrs}")
                    for attr_name, attr_value in all_attrs.items():
                        if 'id' in attr_name.lower() or 'person' in attr_name.lower() or 'data' in attr_name.lower():
                            member_info[attr_name.replace('-', '_')] = attr_value
                
                # 查找所有子元素的属性
                all_children = element.find_all(True)
                for child in all_children:
                    child_attrs = child.attrs
                    if child_attrs:
                        for attr_name, attr_value in child_attrs.items():
                            if 'id' in attr_name.lower() or 'person' in attr_name.lower() or 'data' in attr_name.lower():
                                member_info[f"child_{attr_name.replace('-', '_')}"] = attr_value
                
                # 查找链接中的ID
                links = element.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    self.logger.debug(f"人员 {i+1} 的链接: {href}")
                    
                    # 提取URL中的ID
                    id_match = re.search(r'/person/(\d+)', href)
                    if id_match:
                        member_info['person_id'] = id_match.group(1)
                        self.logger.debug(f"从URL提取到person_id: {id_match.group(1)}")
                    
                    # 提取其他可能的ID模式
                    id_match2 = re.search(r'[?&]id=(\d+)', href)
                    if id_match2:
                        member_info['url_id'] = id_match2.group(1)
                        self.logger.debug(f"从URL提取到url_id: {id_match2.group(1)}")
                    
                    # 提取球员页面ID
                    player_match = re.search(r'/player/(\d+)', href)
                    if player_match:
                        member_info['player_id'] = player_match.group(1)
                        self.logger.debug(f"从URL提取到player_id: {player_match.group(1)}")
                
                # 查找姓名
                name_element = element.find('span', class_='item3')
                if name_element:
                    member_info['name'] = name_element.get_text(strip=True)
                
                # 保存原始HTML用于调试（只保存前200字符）
                member_info['debug_html'] = str(element)[:200] + "..."
                
                members_with_ids.append(member_info)
            
            if members_with_ids:
                self.logger.info(f"从HTML属性中提取到 {len(members_with_ids)} 个人员的信息")
                # 统计有ID的人员数量
                with_person_id = sum(1 for m in members_with_ids if m.get('person_id'))
                with_player_id = sum(1 for m in members_with_ids if m.get('player_id'))
                self.logger.info(f"其中有person_id的: {with_person_id}, 有player_id的: {with_player_id}")
                
                # 如果已经有足够的ID信息，直接返回
                if with_person_id > 0 or with_player_id > 0:
                    return members_with_ids
                
                # 否则继续查找script标签中的数据来补充ID信息
                self.logger.info("继续查找script标签中的数据来补充ID信息")
            
            # 方法3: 查找所有script标签中的数据
            scripts = soup.find_all('script')
            self.logger.info(f"找到 {len(scripts)} 个script标签")
            
            # 保存所有script内容用于调试
            debug_scripts_file = 'debug_all_scripts.txt'
            with open(debug_scripts_file, 'w', encoding='utf-8') as f:
                f.write(f"=== 找到 {len(scripts)} 个Script标签 ===\n")
                for i, script in enumerate(scripts):
                    if script.string:
                        script_content = script.string.strip()
                        f.write(f"\n=== Script {i+1} (长度: {len(script_content)}) ===\n")
                        if len(script_content) > 0:
                            f.write(script_content[:2000] + "\n")
                            # 检查关键字
                            keywords_found = []
                            for keyword in ['nuxt', 'teammemberdata', 'person_id', 'detailed_type', '__NUXT__']:
                                if keyword.lower() in script_content.lower():
                                    keywords_found.append(keyword)
                            if keywords_found:
                                f.write(f"*** 包含关键字: {', '.join(keywords_found)} ***\n")
                        else:
                            f.write("(空内容)\n")
                    else:
                        f.write(f"\n=== Script {i+1} ===\n")
                        f.write("(无string属性)\n")
            
            for i, script in enumerate(scripts):
                if not script.string:
                    continue
                
                # 扩大搜索范围，查找多种可能的模式
                patterns = [
                    r'window\.__NUXT__\s*=\s*\(function[^;]+',  # 原始模式
                    r'window\.__NUXT__\s*=\s*[^;]+',  # 更宽泛的模式
                    r'__NUXT__\s*=\s*[^;]+',  # 简化模式
                ]
                
                for pattern_name, pattern in zip(['完整函数', '宽泛模式', '简化模式'], patterns):
                    nuxt_match = re.search(pattern, script.string, re.DOTALL)
                    if nuxt_match:
                        self.logger.info(f"在第 {i+1} 个script标签中使用{pattern_name}找到 window.__NUXT__")
                        function_content = nuxt_match.group(0)
                        
                        # 调试：确保function_content不为空
                        if function_content:
                            self.logger.info(f"提取到的函数内容长度: {len(function_content)}")
                            
                            # 从函数中提取teamDetail数据
                            team_detail = self._extract_team_detail_from_function(function_content)
                            if team_detail:
                                # 从teamDetail中提取人员数据
                                members_data = self._parse_members_from_team_detail(team_detail)
                                if members_data:
                                    self.logger.info(f"成功从schema数据中提取 {len(members_data)} 个人员信息")
                                    return members_data
                            
                            # 如果teamDetail解析失败，尝试直接解析teamMemberData
                            members_data = self._extract_team_detail_from_function(function_content)
                            if members_data:
                                self.logger.info(f"成功从混淆JavaScript中提取 {len(members_data)} 个人员信息")
                                return members_data
                        else:
                            self.logger.warning(f"使用{pattern_name}提取到的函数内容为空")
                        break  # 找到一个匹配就跳出内层循环
            
            self.logger.warning("未能从任何方法中找到有效的schema数据")
            return None
            
        except Exception as e:
            self.logger.error(f"提取schema数据时发生异常: {e}")
            return None
    
    def _extract_team_detail_from_function(self, function_str: str) -> Optional[Dict[str, Any]]:
        """从JavaScript函数中提取teamDetail数据
        
        Args:
            function_str: JavaScript函数字符串
            
        Returns:
            teamDetail数据字典
        """
        try:
            # 保存调试信息
            debug_file = 'debug_team_detail.txt'
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write("=== 完整的JavaScript函数内容 ===\n")
                f.write(f"函数长度: {len(function_str)}\n")
                if function_str:
                    f.write(f"函数前100字符: {function_str[:100]}\n")
                    f.write(f"函数后100字符: {function_str[-100:]}\n\n")
                    f.write(function_str + "\n\n")
                else:
                    f.write("函数内容为空！\n\n")
                
                # 搜索所有可能的字段名
                f.write("=== 搜索关键字段 ===\n")
                keywords = ['teamMemberData', 'memberData', 'players', 'staff', 'person_id', 'detailed_type', 'personId', 'detailedType']
                for keyword in keywords:
                    if keyword.lower() in function_str.lower():
                        f.write(f"找到关键字: {keyword}\n")
                        # 找到关键字周围的内容
                        start_pos = function_str.lower().find(keyword.lower())
                        if start_pos != -1:
                            context_start = max(0, start_pos - 200)
                            context_end = min(len(function_str), start_pos + 500)
                            context = function_str[context_start:context_end]
                            f.write(f"上下文: {context}\n\n")
                f.write("\n")
            
            # 尝试执行JavaScript函数来获取实际数据
            # 首先尝试找到函数的返回值部分
            if 'return' in function_str:
                # 查找return语句
                return_match = re.search(r'return\s+([^;]+)', function_str, re.DOTALL)
                if return_match:
                    return_content = return_match.group(1)
                    
                    with open(debug_file, 'a', encoding='utf-8') as f:
                        f.write("=== 找到return语句 ===\n")
                        f.write(return_content[:1000] + "\n\n")
            
            # 直接在完整的JavaScript代码中搜索teamDetail和相关数据
            with open(debug_file, 'a', encoding='utf-8') as f:
                f.write(f"=== JavaScript函数长度: {len(function_str)} ===\n")
                
                # 查找teamDetail的位置
                team_detail_pos = function_str.find('teamDetail')
                if team_detail_pos != -1:
                    f.write(f"找到teamDetail位置: {team_detail_pos}\n")
                    # 提取teamDetail周围的内容
                    start_pos = max(0, team_detail_pos - 100)
                    end_pos = min(len(function_str), team_detail_pos + 2000)
                    context = function_str[start_pos:end_pos]
                    f.write(f"teamDetail上下文:\n{context}\n\n")
                    
                    # 尝试找到teamDetail对象的完整结构
                    # 从teamDetail开始，找到对应的大括号
                    brace_start = function_str.find('{', team_detail_pos)
                    if brace_start != -1:
                        brace_count = 1
                        pos = brace_start + 1
                        while pos < len(function_str) and brace_count > 0:
                            if function_str[pos] == '{':
                                brace_count += 1
                            elif function_str[pos] == '}':
                                brace_count -= 1
                            pos += 1
                        
                        if brace_count == 0:
                            team_detail_content = function_str[brace_start:pos]
                            f.write(f"完整teamDetail对象 (长度{len(team_detail_content)}):\n{team_detail_content[:1500]}\n\n")
                            
                            # 在teamDetail中查找teamMemberData
                            if 'teamMemberData' in team_detail_content:
                                member_data_pos = team_detail_content.find('teamMemberData')
                                f.write(f"在teamDetail中找到teamMemberData位置: {member_data_pos}\n")
                                
                                # 提取teamMemberData周围的内容
                                start = max(0, member_data_pos - 50)
                                end = min(len(team_detail_content), member_data_pos + 200)
                                member_context = team_detail_content[start:end]
                                f.write(f"teamMemberData上下文: {member_context}\n\n")
                else:
                    f.write("未找到teamDetail\n")
                
                # 直接搜索teamMemberData
                member_data_pos = function_str.find('teamMemberData')
                if member_data_pos != -1:
                    f.write(f"直接找到teamMemberData位置: {member_data_pos}\n")
                    start = max(0, member_data_pos - 100)
                    end = min(len(function_str), member_data_pos + 500)
                    context = function_str[start:end]
                    f.write(f"teamMemberData直接上下文:\n{context}\n\n")
            
            # 备用方案：直接搜索包含人员数据的数组模式
            team_member_data_patterns = [
                r'teamMemberData["\s]*:[\s]*\[([^\]]+)\]',  # teamMemberData: [...]
                r'"teamMemberData"[\s]*:[\s]*\[([^\]]+)\]',  # "teamMemberData": [...]
                r'teamMemberData[\s]*=[\s]*\[([^\]]+)\]',  # teamMemberData = [...]
                r'\[([^\]]*\{[^\}]*person_id[^\}]*\}[^\]]*)\]',  # 包含person_id的对象数组
                r'\[([^\]]*\{[^\}]*detailed_type[^\}]*\}[^\]]*)\]',  # 包含detailed_type的对象数组
            ]
            
            # 查找 teamMemberData 数组
            team_member_data = None
            for i, pattern in enumerate(team_member_data_patterns):
                matches = re.finditer(pattern, function_str, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    candidate_data = '[' + match.group(1) + ']'
                    # 检查是否包含关键字段
                    if any(keyword in candidate_data.lower() for keyword in ['person_id', 'detailed_type', 'avatar', 'jersey', 'position']):
                        team_member_data = candidate_data
                        self.logger.info(f"使用模式 {i+1} 找到包含关键字段的数组，长度约: {len(match.group(1))} 字符")
                        break
                if team_member_data:
                    break
            
            # 如果找到了 teamMemberData，保存并尝试解析
            if team_member_data:
                with open(debug_file, 'a', encoding='utf-8') as f:
                    f.write("=== 找到teamMemberData ===\n")
                    f.write(team_member_data[:3000] + "\n\n")  # 保存前3000字符
                
                try:
                    parsed_data = self._parse_js_object(team_member_data)
                    if parsed_data and isinstance(parsed_data, list):
                        self.logger.info(f"成功解析teamMemberData，包含 {len(parsed_data)} 个成员")
                        return parsed_data
                except Exception as e:
                    self.logger.error(f"解析teamMemberData失败: {e}")
                    # 如果解析失败，尝试简单的字符串替换来修复常见问题
                    try:
                        # 尝试修复一些常见的JavaScript到JSON的转换问题
                        fixed_data = team_member_data.replace("'", '"').replace('undefined', 'null').replace('true', 'true').replace('false', 'false')
                        parsed_data = json.loads(fixed_data)
                        if parsed_data and isinstance(parsed_data, list):
                            self.logger.info(f"修复后成功解析teamMemberData，包含 {len(parsed_data)} 个成员")
                            return parsed_data
                    except Exception as e2:
                        self.logger.error(f"修复后仍然解析失败: {e2}")
            
            # 额外尝试：直接搜索包含大量对象的数组
            large_array_pattern = r'\[([^\]]*\{[^\}]*\}[^\]]*\{[^\}]*\}[^\]]*\{[^\}]*\}[^\]]*)\]'  # 至少包含3个对象的数组
            large_arrays = re.finditer(large_array_pattern, function_str, re.DOTALL)
            for match in large_arrays:
                array_content = '[' + match.group(1) + ']'
                if len(array_content) > 1000:  # 只考虑较大的数组
                    with open(debug_file, 'a', encoding='utf-8') as f:
                        f.write(f"=== 找到大型数组 (长度: {len(array_content)}) ===\n")
                        f.write(array_content[:2000] + "\n\n")
                    
                    try:
                        parsed_data = self._parse_js_object(array_content)
                        if parsed_data and isinstance(parsed_data, list) and len(parsed_data) > 10:  # 至少10个元素
                            self.logger.info(f"找到可能的人员数据数组，包含 {len(parsed_data)} 个元素")
                            return parsed_data
                    except Exception as e:
                        continue
            
            # 备用方案：查找其他可能包含人员数据的模式
            patterns = [
                  r'"person_id"\s*:\s*"?([^,"\}]+)"?',
                  r'"detailed_type"\s*:\s*"?([^,"\}]+)"?',
                 r'person_id["\s]*:[\s]*"?([^,"\}]+)"?',
                 r'detailed_type["\s]*:[\s]*"?([^,"\}]+)"?',
                 r'\[\s*{[^\]]+person_id[^\]]+}\s*\]',  # 查找包含person_id的数组
                 r'{[^}]*person_id[^}]*}',  # 查找包含person_id的对象
             ]
            
            found_data = []
            for i, pattern in enumerate(patterns):
                matches = re.findall(pattern, function_str, re.DOTALL | re.IGNORECASE)
                if matches:
                    found_data.append(f"模式{i+1}: {matches[:5]}")  # 只保存前5个匹配
            
            # 保存提取结果
            with open(debug_file, 'a', encoding='utf-8') as f:
                f.write("=== 查找到的数据模式 ===\n")
                if found_data:
                    for data in found_data:
                        f.write(data + "\n")
                else:
                    f.write("未找到person_id或detailed_type相关数据\n")
            
            # 尝试查找完整的数据结构
            # 查找可能的JSON数组或对象
            json_patterns = [
                r'\[\s*{[^\]]{100,}\]',  # 查找较大的JSON数组
                r'{[^}]{200,}}',  # 查找较大的JSON对象
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, function_str, re.DOTALL)
                for match in matches:
                    if 'person_id' in match or 'detailed_type' in match:
                        try:
                            # 尝试解析为JSON
                            parsed = self._parse_js_object(match)
                            if parsed:
                                return parsed
                        except:
                            continue
            
            # 现在尝试实际解析teamMemberData
            member_data_pos = function_str.find('teamMemberData')
            if member_data_pos != -1:
                # 找到teamMemberData数组的开始位置
                bracket_pos = function_str.find('[', member_data_pos)
                if bracket_pos != -1:
                    # 提取完整的数组
                    bracket_count = 0
                    end_pos = bracket_pos
                    for i, char in enumerate(function_str[bracket_pos:]):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end_pos = bracket_pos + i + 1
                                break
                    
                    if end_pos > bracket_pos:
                        member_data_str = function_str[bracket_pos:end_pos]
                        self.logger.info(f"提取到teamMemberData数组，长度: {len(member_data_str)}")
                        
                        # 解析人员信息
                        return self._parse_member_data_from_obfuscated_js(function_str)
            
            return None
            
        except Exception as e:
            self.logger.error(f"提取teamDetail时出错: {e}")
            return None
    
    def _extract_variable_mapping(self, js_content):
        """
        从混淆的JavaScript代码中提取变量映射
        """
        var_mapping = {}
        try:
            # 查找函数开头的变量定义部分
            # 格式类似: window.__NUXT__=(function(a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z,A,B,C,D,E,F,G,H,I,J,K,
            func_start = js_content.find('window.__NUXT__=(function(')
            if func_start == -1:
                return var_mapping
            
            # 查找参数列表
            params_start = func_start + len('window.__NUXT__=(function(')
            params_end = js_content.find(')', params_start)
            if params_end == -1:
                return var_mapping
            
            params_str = js_content[params_start:params_end]
            param_names = [p.strip() for p in params_str.split(',') if p.strip()]
            
            # 查找函数调用部分，获取实际参数值
            # 可能在文件末尾，格式类似: })("value1","value2",...)
            # 或者在其他位置
            call_patterns = [
                r'\}\)\(([^)]+)\)$',  # 在文件末尾
                r'\}\)\(([^)]+)\)',   # 在任意位置
            ]
            
            call_match = None
            for pattern in call_patterns:
                call_match = re.search(pattern, js_content)
                if call_match:
                    break
            
            if call_match:
                args_str = call_match.group(1)
                # 解析参数值 - 改进的解析逻辑
                args = []
                current_arg = ''
                in_quotes = False
                quote_char = None
                escape_next = False
                paren_count = 0
                
                for char in args_str:
                    if escape_next:
                        current_arg += char
                        escape_next = False
                        continue
                    
                    if char == '\\':
                        current_arg += char
                        escape_next = True
                        continue
                    
                    if not in_quotes:
                        if char in ['"', "'"]:
                            in_quotes = True
                            quote_char = char
                            current_arg += char
                        elif char == '(':
                            paren_count += 1
                            current_arg += char
                        elif char == ')':
                            paren_count -= 1
                            current_arg += char
                        elif char == ',' and paren_count == 0:
                            args.append(current_arg.strip())
                            current_arg = ''
                        else:
                            current_arg += char
                    else:
                        if char == quote_char:
                            in_quotes = False
                        current_arg += char
                
                if current_arg.strip():
                    args.append(current_arg.strip())
                
                # 创建变量映射
                for i, param_name in enumerate(param_names):
                    if i < len(args):
                        arg_value = args[i]
                        # 去除引号
                        if arg_value.startswith('"') and arg_value.endswith('"'):
                            arg_value = arg_value[1:-1]
                        elif arg_value.startswith("'") and arg_value.endswith("'"):
                            arg_value = arg_value[1:-1]
                        
                        # 处理转义字符
                        arg_value = arg_value.replace('\\u002F', '/').replace('\\"', '"').replace("\\\\", "\\")
                        var_mapping[param_name] = arg_value
            
            # 如果还是没有找到变量映射，尝试从JavaScript内容中直接提取一些常见的值
            if not var_mapping:
                # 尝试从内容中找到一些明显的字符串值来建立映射
                common_values = [
                    '主教练', '助理教练', '守门员教练', '体能教练', '战术教练',
                    '西班牙', '阿根廷', '英格兰', '法国', '德国', '意大利', '巴西',
                    '前锋', '中场', '后卫', '守门员'
                ]
                
                # 简单的启发式映射
                for i, param_name in enumerate(param_names[:len(common_values)]):
                    if i < len(common_values):
                        var_mapping[param_name] = common_values[i]
            
        except Exception as e:
            self.logger.error(f"提取变量映射时出错: {e}")
        
        return var_mapping
    
    def _parse_member_data_from_obfuscated_js(self, js_content):
        """
        解析混淆的JavaScript代码中的人员数据
        """
        try:
            self.logger.info("开始解析混淆的JavaScript人员数据")
            
            # 首先提取变量定义映射
            var_mapping = self._extract_variable_mapping(js_content)
            
            # 查找teamMemberData数组 - 使用手动解析来处理嵌套数组
            start_pattern = r'teamMemberData:\s*\['
            start_match = re.search(start_pattern, js_content)
            
            if not start_match:
                self.logger.warning("未找到teamMemberData数组")
                return []
            
            # 从找到的位置开始手动解析数组
            start_pos = start_match.end() - 1  # 包含开始的 '['
            bracket_count = 0
            square_count = 0
            i = start_pos
            
            while i < len(js_content):
                char = js_content[i]
                if char == '[':
                    square_count += 1
                elif char == ']':
                    square_count -= 1
                    if square_count == 0:
                        # 找到匹配的结束括号
                        member_data_str = js_content[start_pos:i+1]
                        break
                elif char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                i += 1
            else:
                self.logger.warning("未找到teamMemberData数组的结束位置")
                return []
            
            # 保存调试信息
            with open('debug_member_parsing.txt', 'w', encoding='utf-8') as f:
                f.write(f"=== 变量映射 (共{len(var_mapping)}个) ===\n")
                for i, (var_name, var_value) in enumerate(list(var_mapping.items())[:20]):  # 只显示前20个
                    f.write(f"{var_name}: {var_value}\n")
                if len(var_mapping) > 20:
                    f.write(f"... 还有 {len(var_mapping) - 20} 个变量\n")
                f.write("\n")
                
                f.write("=== 原始teamMemberData数组 ===\n")
                f.write(f"数组长度: {len(member_data_str)}\n")
                f.write(member_data_str + "\n\n")
                
                # 简单地查找前几个对象
                f.write("=== 前几个对象的结构 ===\n")
                # 使用简单的正则表达式查找对象
                simple_objects = re.findall(r'\{[^{}]*?\}', member_data_str[:3000])
                for i, obj in enumerate(simple_objects[:5]):
                    f.write(f"对象 {i+1}: {obj}\n")
                f.write("\n")
            
            # 由于数据格式是混淆的JavaScript对象，我们需要用不同的方法解析
            # 使用更复杂的方法来解析嵌套的对象和数组
            
            # 手动解析对象
            objects = []
            i = 0
            while i < len(member_data_str):
                if member_data_str[i] == '{':
                    # 找到对象的开始
                    obj_start = i
                    brace_count = 0
                    bracket_count = 0
                    in_string = False
                    escape_next = False
                    
                    j = i
                    while j < len(member_data_str):
                        char = member_data_str[j]
                        
                        if escape_next:
                            escape_next = False
                            j += 1
                            continue
                        
                        if char == '\\' and in_string:
                            escape_next = True
                            j += 1
                            continue
                        
                        if char in ['"', "'"] and not escape_next:
                            in_string = not in_string
                        elif not in_string:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    # 找到对象的结束
                                    obj_text = member_data_str[obj_start:j+1]
                                    objects.append(obj_text)
                                    i = j + 1
                                    break
                            elif char == '[':
                                bracket_count += 1
                            elif char == ']':
                                bracket_count -= 1
                        
                        j += 1
                    else:
                        # 如果没有找到匹配的结束括号，跳出
                        break
                else:
                    i += 1
            
            self.logger.info(f"找到 {len(objects)} 个对象")
            
            # 更新调试信息
            with open('debug_member_parsing.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n=== 解析到的对象样本 ===\n")
                for i, obj in enumerate(objects[:3]):
                    f.write(f"对象 {i+1}: {obj}\n")
                f.write("\n")
            
            object_matches = objects
            
            parsed_members = []
            
            for i, obj_match in enumerate(object_matches):
                try:
                    # 提取关键信息
                    member_info = {
                        'person_id': '',
                        'person_name': '',
                        'detailed_type': '',
                        'person_logo': '',
                        'age': '',
                        'nationality_name': '',
                        'type': ''
                    }
                    
                    # 检查是否包含person_id字段
                    if 'person_id:' not in obj_match:
                        continue
                    
                    # 提取person_id - 可能是字符串或变量
                    person_id_patterns = [
                        r'person_id:"([^"]+)"',  # 字符串格式
                        r'person_id:([a-zA-Z_][a-zA-Z0-9_]*)',  # 变量格式
                        r'person_id:([^,}]+)'  # 通用格式
                    ]
                    
                    for pattern in person_id_patterns:
                        person_id_match = re.search(pattern, obj_match)
                        if person_id_match:
                            value = person_id_match.group(1).strip()
                            # 如果是变量，尝试从映射中获取值
                            if value in var_mapping:
                                member_info['person_id'] = var_mapping[value]
                            else:
                                member_info['person_id'] = value
                            break
                    
                    # 定义一个通用的字段提取函数
                    def extract_field(field_name, obj_text):
                        # 首先尝试字符串格式
                        string_match = re.search(rf'{field_name}:"([^"]+)"', obj_text)
                        if string_match:
                            return string_match.group(1)
                        
                        # 然后尝试变量格式
                        var_match = re.search(rf'{field_name}:([^,}}]+)', obj_text)
                        if var_match:
                            var_name = var_match.group(1).strip()
                            return var_mapping.get(var_name, var_name)
                        
                        return ''
                    
                    # 提取各个字段
                    member_info['person_name'] = extract_field('person_name', obj_match)
                    member_info['detailed_type'] = extract_field('type', obj_match)  # 使用type字段
                    member_info['person_logo'] = extract_field('person_logo', obj_match)
                    member_info['age'] = extract_field('age', obj_match)
                    member_info['nationality_name'] = extract_field('nationality_name', obj_match)
                    
                    # 添加type字段（与detailed_type相同）
                    member_info['type'] = member_info.get('detailed_type', '')
                    
                    # 只有当person_id存在时才添加
                    if member_info['person_id']:
                        parsed_members.append(member_info)
                        self.logger.debug(f"解析成员 {i+1}: {member_info['person_name']} (ID: {member_info['person_id']})")
                    
                except Exception as e:
                    self.logger.warning(f"解析第 {i+1} 个成员时出错: {e}")
                    continue
            
            # 保存解析结果用于调试
            with open('debug_member_parsing.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n=== 解析结果 ===\n")
                f.write(f"成功解析 {len(parsed_members)} 个成员\n\n")
                for member in parsed_members[:10]:  # 只显示前10个
                    f.write(f"成员: {member}\n")
            
            self.logger.info(f"成功解析 {len(parsed_members)} 个成员信息")
            return parsed_members
            
        except Exception as e:
            self.logger.error(f"解析混淆JavaScript人员数据时出错: {e}")
            return []
    
    def _extract_balanced_braces(self, text: str, start_pos: int) -> Optional[str]:
        """提取平衡的大括号内容
        
        Args:
            text: 源文本
            start_pos: 开始位置
            
        Returns:
            平衡的大括号内容
        """
        try:
            brace_count = 0
            i = start_pos
            
            while i < len(text):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return text[start_pos:i+1]
                i += 1
            
            return None
            
        except Exception as e:
            self.logger.error(f"提取平衡大括号时发生异常: {e}")
            return None
    
    def _parse_js_object(self, js_content: str) -> Optional[Dict[str, Any]]:
        """解析JavaScript对象为Python字典
        
        Args:
            js_content: JavaScript对象字符串
            
        Returns:
            解析后的字典
        """
        try:
            # 保存原始内容用于调试
            original_content = js_content[:200] + "..." if len(js_content) > 200 else js_content
            self.logger.debug(f"原始JavaScript内容: {original_content}")
            
            # 简单的JavaScript到JSON转换
            json_content = js_content
            
            # 替换undefined为null
            json_content = re.sub(r'\bundefined\b', 'null', json_content)
            
            # 替换true/false为小写
            json_content = re.sub(r'\btrue\b', 'true', json_content)
            json_content = re.sub(r'\bfalse\b', 'false', json_content)
            
            # 处理属性名的引号问题
            # 匹配没有引号的属性名
            json_content = re.sub(r'([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'\1"\2":', json_content)
            
            # 替换单引号为双引号（处理字符串值）
            json_content = re.sub(r"'([^']*)'(?=\s*[,}])", r'"\1"', json_content)
            
            # 移除JavaScript注释
            json_content = re.sub(r'//.*?$', '', json_content, flags=re.MULTILINE)
            json_content = re.sub(r'/\*.*?\*/', '', json_content, flags=re.DOTALL)
            
            # 移除函数调用和复杂表达式
            json_content = re.sub(r'function\s*\([^)]*\)\s*\{[^}]*\}', 'null', json_content)
            
            # 尝试解析JSON
            parsed_data = json.loads(json_content)
            self.logger.debug(f"成功解析JavaScript对象，包含 {len(parsed_data)} 个字段")
            return parsed_data
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON解析失败: {e}")
            # 尝试使用ast.literal_eval作为备选方案
            try:
                import ast
                # 将JavaScript对象转换为Python字典格式
                python_content = js_content
                python_content = re.sub(r'\bundefined\b', 'None', python_content)
                python_content = re.sub(r'\btrue\b', 'True', python_content)
                python_content = re.sub(r'\bfalse\b', 'False', python_content)
                python_content = re.sub(r'\bnull\b', 'None', python_content)
                
                # 简单的属性名处理
                python_content = re.sub(r'([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'\1"\2":', python_content)
                
                parsed_data = ast.literal_eval(python_content)
                self.logger.debug(f"使用ast.literal_eval成功解析，包含 {len(parsed_data)} 个字段")
                return parsed_data
            except Exception as ast_e:
                self.logger.warning(f"ast.literal_eval也失败: {ast_e}")
                return None
        except Exception as e:
            self.logger.warning(f"解析JavaScript对象失败: {e}")
            return None
    
    def _parse_members_from_team_detail(self, team_detail: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """从teamDetail数据中解析人员信息
        
        Args:
            team_detail: teamDetail数据字典
            
        Returns:
            人员数据列表
        """
        try:
            members_data = []
            
            # 查找人员数据的可能字段
            possible_fields = ['members', 'players', 'staff', 'squad', 'roster']
            
            for field in possible_fields:
                if field in team_detail:
                    members_list = team_detail[field]
                    if isinstance(members_list, list):
                        for member in members_list:
                            if isinstance(member, dict):
                                member_info = {
                                    'person_id': str(member.get('id', member.get('person_id', ''))),
                                    'detailed_type': member.get('type', member.get('position', member.get('role', ''))),
                                    'name': member.get('name', member.get('fullName', member.get('displayName', '')))
                                }
                                members_data.append(member_info)
                        
                        if members_data:
                            self.logger.info(f"从字段 '{field}' 中找到 {len(members_data)} 个人员")
                            return members_data
            
            # 如果没有找到标准字段，尝试递归搜索
            members_data = self._recursive_search_members(team_detail)
            if members_data:
                return members_data
            
            self.logger.warning("未能从teamDetail中找到人员数据")
            return None
            
        except Exception as e:
            self.logger.error(f"解析人员数据时发生异常: {e}")
            return None
    
    def _extract_members_from_json_ld(self, json_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """从JSON-LD数据中提取人员信息
        
        Args:
            json_data: JSON-LD数据
            
        Returns:
            人员数据列表
        """
        try:
            members_data = []
            
            # 查找可能包含人员信息的字段
            if isinstance(json_data, dict):
                for key, value in json_data.items():
                    if key.lower() in ['member', 'members', 'athlete', 'athletes', 'person', 'persons']:
                        if isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    member_info = {
                                        'person_id': str(item.get('@id', item.get('id', ''))),
                                        'name': item.get('name', ''),
                                        'detailed_type': item.get('@type', item.get('type', ''))
                                    }
                                    members_data.append(member_info)
            
            return members_data if members_data else None
            
        except Exception as e:
            self.logger.error(f"从JSON-LD提取人员数据时发生异常: {e}")
            return None
    
    def _recursive_search_members(self, data: Any, depth: int = 0) -> List[Dict[str, Any]]:
        """递归搜索人员数据
        
        Args:
            data: 要搜索的数据
            depth: 递归深度
            
        Returns:
            找到的人员数据列表
        """
        if depth > 5:  # 限制递归深度
            return []
        
        members_data = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    # 检查是否是人员数据列表
                    if self._is_members_list(value):
                        for item in value:
                             if isinstance(item, dict):
                                 member_info = {
                                     'person_id': str(item.get('id', item.get('person_id', ''))),
                                     'detailed_type': item.get('type', item.get('position', item.get('role', ''))),
                                     'name': item.get('name', item.get('fullName', item.get('displayName', '')))
                                 }
                                 members_data.append(member_info)
                        return members_data
                else:
                    # 递归搜索
                    result = self._recursive_search_members(value, depth + 1)
                    if result:
                        members_data.extend(result)
        elif isinstance(data, list):
            for item in data:
                result = self._recursive_search_members(item, depth + 1)
                if result:
                    members_data.extend(result)
        
        return members_data
    
    def _is_members_list(self, data_list: List[Any]) -> bool:
        """判断是否是人员数据列表
        
        Args:
            data_list: 要检查的列表
            
        Returns:
            是否是人员数据列表
        """
        if not data_list or len(data_list) == 0:
            return False
        
        # 检查前几个元素是否包含人员相关字段
        sample_size = min(3, len(data_list))
        for i in range(sample_size):
            item = data_list[i]
            if isinstance(item, dict):
                # 检查是否包含人员相关字段
                person_fields = ['id', 'person_id', 'name', 'type', 'position', 'role']
                if any(field in item for field in person_fields):
                    return True
        
        return False
    
    def _match_member_with_schema(self, member_data: Dict[str, Any], schema_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """通过姓名匹配人员数据与schema数据
        
        Args:
            member_data: 从HTML提取的人员数据
            schema_data: 从schema提取的人员数据列表
            
        Returns:
            匹配的schema数据
        """
        member_name = member_data.get('name', '').strip()
        if not member_name:
            return None
        
        # 尝试精确匹配
        for schema_member in schema_data:
            schema_name = schema_member.get('name', '').strip()
            if member_name == schema_name:
                return schema_member
        
        # 尝试部分匹配（去除空格和特殊字符）
        normalized_member_name = re.sub(r'[\s\-\.]', '', member_name.lower())
        for schema_member in schema_data:
            schema_name = schema_member.get('name', '').strip()
            normalized_schema_name = re.sub(r'[\s\-\.]', '', schema_name.lower())
            if normalized_member_name == normalized_schema_name:
                return schema_member
        
        return None
    
    def _extract_member_data(self, item, index: int) -> Optional[Dict[str, Any]]:
        """从单个analysis-list-item元素中提取人员数据
        
        Args:
            item: BeautifulSoup元素对象
            index: 元素索引
            
        Returns:
            人员数据字典（英文字段名）
        """
        try:
            member_data = {
                'index': index
            }
            
            # 查找item1-item6的span标签
            for i in range(1, 7):
                item_span = item.find('span', class_=f'item{i}')
                if item_span:
                    if i == 1:  # 位置
                        member_data['position'] = item_span.get_text(strip=True)
                    elif i == 2:  # 号码
                        member_data['jersey_number'] = item_span.get_text(strip=True)
                    elif i == 3:  # 姓名和头像
                        member_data['name'] = item_span.get_text(strip=True)
                        # 提取头像图片地址
                        avatar_img = item_span.find('img')
                        if avatar_img:
                            member_data['avatar_url'] = avatar_img.get('src', '')
                        else:
                            member_data['avatar_url'] = ''
                    elif i == 4:  # 出场
                        member_data['appearances'] = item_span.get_text(strip=True)
                    elif i == 5:  # 进球
                        member_data['goals'] = item_span.get_text(strip=True)
                    elif i == 6:  # 国籍（图片）
                        # 查找图片元素
                        img_elem = item_span.find('img')
                        if img_elem:
                            img_src = img_elem.get('src', '')
                            img_alt = img_elem.get('alt', '')
                            member_data['nationality_flag'] = img_src
                            member_data['nationality'] = img_alt
                        else:
                            # 如果没有图片，尝试获取文本
                            nationality_text = item_span.get_text(strip=True)
                            if nationality_text:
                                member_data['nationality'] = nationality_text
            
            # 如果没有找到item1-item6的span标签，尝试其他方法提取
            if not any(key in member_data for key in ['position', 'name']):
                self.logger.debug(f"人员 {index} 未找到item1-item6标签，尝试其他方法")
                fallback_data = self._extract_fallback_data(item)
                if fallback_data:
                    member_data.update(fallback_data)
            
            # 添加原始HTML用于调试
            member_data['raw_html'] = str(item)
            
            # 添加所有文本内容
            member_data['raw_text'] = item.get_text(strip=True)
            
            return member_data
            
        except Exception as e:
            self.logger.error(f"提取人员 {index} 数据时出错: {e}")
            return None
    
    def _extract_fallback_data(self, item) -> Optional[Dict[str, str]]:
        """备用数据提取方法
        
        Args:
            item: BeautifulSoup元素对象
            
        Returns:
            提取的数据字典
        """
        try:
            fallback_data = {}
            
            # 获取所有文本
            all_text = item.get_text(strip=True)
            
            # 尝试识别位置关键词
            position_keywords = ['前锋', '中场', '后卫', '门将', '教练', '工作人员']
            for keyword in position_keywords:
                if keyword in all_text:
                    fallback_data['position'] = keyword
                    break
            
            # 尝试提取数字（可能是号码）
            numbers = re.findall(r'\d+', all_text)
            if numbers:
                # 第一个数字可能是号码
                fallback_data['jersey_number'] = numbers[0]
                # 其他数字可能是统计数据
                if len(numbers) > 1:
                    fallback_data['appearances'] = numbers[1]
                if len(numbers) > 2:
                    fallback_data['goals'] = numbers[2]
            
            # 尝试提取姓名（移除位置和数字后的文本）
            name_text = all_text
            if 'position' in fallback_data:
                name_text = name_text.replace(fallback_data['position'], '')
            for num in numbers:
                name_text = name_text.replace(num, '')
            
            # 清理姓名文本
            name_text = re.sub(r'[~-]+', '', name_text).strip()
            if name_text and len(name_text) > 1:
                fallback_data['name'] = name_text
            
            return fallback_data if fallback_data else None
            
        except Exception as e:
            self.logger.error(f"备用数据提取失败: {e}")
            return None
    
    def load_decompressed_data(self, decompressed_file: str = None) -> Optional[Dict[str, Any]]:
        """加载解压缩的数据文件
        
        Args:
            decompressed_file: 解压缩数据文件路径
            
        Returns:
            解压缩的数据，失败返回None
        """
        if decompressed_file is None:
            # 查找最新的解压缩数据文件
            pattern = "decompressed_team_data_*.json"
            import glob
            files = glob.glob(pattern)
            if files:
                decompressed_file = max(files, key=os.path.getctime)
                self.logger.info(f"自动找到解压缩数据文件: {decompressed_file}")
            else:
                self.logger.warning("未找到解压缩数据文件")
                return None
        
        try:
            with open(decompressed_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.info(f"成功加载解压缩数据: {decompressed_file}")
            return data
        except Exception as e:
            self.logger.error(f"加载解压缩数据失败: {e}")
            return None
    

    
    def merge_with_decompressed_data(self, scraped_data: Dict[str, Any], decompressed_file: str = None) -> Dict[str, Any]:
        """将爬取的数据与解压缩数据合并
        
        Args:
            scraped_data: 爬取的原始数据
            decompressed_file: 解压缩数据文件路径
            
        Returns:
            合并后的数据
        """
        # 加载解压缩数据
        decompressed_data = self.load_decompressed_data(decompressed_file)
        if not decompressed_data:
            self.logger.warning("无法加载解压缩数据，返回原始数据")
            return scraped_data
        
        # 复制原始数据
        merged_data = scraped_data.copy()
        merged_data['merge_time'] = datetime.now().isoformat()
        merged_data['has_enhanced_data'] = True
        
        # 获取解压缩数据的成员列表
        decompressed_members = decompressed_data.get('members', [])
        scraped_members = scraped_data.get('members', [])
        
        # 使用索引匹配合并成员数据
        merged_members = []
        matched_count = 0
        
        for i, member in enumerate(scraped_members):
            # 复制原始成员数据
            merged_member = member.copy()
            
            # 使用索引匹配解压缩数据
            if i < len(decompressed_members):
                decompressed_member = decompressed_members[i]
                merged_member['person_id'] = decompressed_member.get('person_id', '')
                merged_member['detailed_type'] = decompressed_member.get('type', '')
                matched_count += 1
                
                member_name = member.get('name', '')
                person_id = merged_member['person_id']
                detailed_type = merged_member['detailed_type']
                self.logger.debug(f"索引匹配成功: [{i}] {member_name} -> {person_id} ({detailed_type})")
            else:
                merged_member['person_id'] = None
                merged_member['detailed_type'] = None
                self.logger.warning(f"索引超出范围: [{i}] {member.get('name', '')}")
            
            merged_members.append(merged_member)
        
        merged_data['members'] = merged_members
        
        # 记录合并统计
        self.logger.info(f"数据合并完成: 匹配 {matched_count}/{len(scraped_members)} 个成员")
        
        return merged_data
    
    def update_team_members_to_db(self, team_id: str, members_data: List[Dict[str, Any]]) -> bool:
        """将人员信息更新到数据库的person字段中
        
        Args:
            team_id: 球队ID
            members_data: 人员数据列表
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 提取需要保存的字段
            person_data = []
            for member in members_data:
                person_info = {
                    'position': member.get('position', ''),
                    'jersey_number': member.get('jersey_number', ''),
                    'name': member.get('name', ''),
                    'appearances': member.get('appearances', ''),
                    'goals': member.get('goals', ''),
                    'nationality_flag': member.get('nationality_flag', ''),
                    'person_id': member.get('person_id', ''),
                    'detailed_type': member.get('detailed_type', ''),
                    'avatar_url': member.get('avatar_url', '')
                }
                person_data.append(person_info)
            
            # 更新数据库
            update_data = {
                'person': person_data,
                'person_updated_at': datetime.now(),
                'total_members': len(person_data)
            }
            
            success = self.db_manager.update_team(team_id, update_data)
            if success:
                self.logger.info(f"成功更新球队 {team_id} 的人员信息，共 {len(person_data)} 名成员")
            else:
                self.logger.error(f"更新球队 {team_id} 的人员信息失败")
            
            return success
            
        except Exception as e:
            self.logger.error(f"更新球队 {team_id} 人员信息到数据库时出错: {e}")
            return False
    
    def save_to_json(self, data: Dict[str, Any], filename: str = None) -> str:
        """保存数据到JSON文件
        
        Args:
            data: 要保存的数据
            filename: 文件名，如果不提供则自动生成
            
        Returns:
            保存的文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ac_milan_team_members_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"数据已保存到: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"保存文件失败: {e}")
            raise
    
    def print_summary(self, data: Dict[str, Any]):
        """打印数据摘要
        
        Args:
            data: 人员数据
        """
        print("\n=== AC Milan Team Members Data Summary ===")
        print(f"Scrape Time: {data.get('scrape_time', 'N/A')}")
        print(f"Total Members: {data.get('total_members', 0)}")
        print(f"Data Source: {data.get('url', 'N/A')}")
        
        members = data.get('members', [])
        if members:
            print("\nMembers by Position:")
            
            # 按位置分组显示
            positions = {}
            for member in members:
                pos = member.get('position', 'Unknown')
                if pos not in positions:
                    positions[pos] = []
                positions[pos].append(member)
            
            for position, pos_members in positions.items():
                print(f"\n{position} ({len(pos_members)} members):")
                for member in pos_members[:10]:  # 显示前10个
                    jersey = member.get('jersey_number', 'N/A')
                    name = member.get('name', 'N/A')
                    apps = member.get('appearances', 'N/A')
                    goals = member.get('goals', 'N/A')
                    nationality = member.get('nationality', 'N/A')
                    
                    print(f"  #{jersey} {name} - Apps: {apps} - Goals: {goals} - Nationality: {nationality}")
                
                if len(pos_members) > 10:
                    print(f"  ... and {len(pos_members) - 10} more")
        
        print("\n" + "="*60)
        
        # 显示字段说明
        print("\n=== Field Descriptions ===")
        print("- index: Member index number")
        print("- position: Member position/role")
        print("- jersey_number: Jersey number")
        print("- name: Member name")
        print("- appearances: Number of appearances")
        print("- goals: Number of goals scored")
        print("- nationality: Member nationality")
        print("- nationality_flag: URL of nationality flag image")
        print("- raw_text: Original text from webpage")
        print("- raw_html: Original HTML from webpage")

def main():
    """主函数 - 批量爬取所有球队的人员信息"""
    try:
        scraper = TeamMemberScraper()
        
        # 查询所有球队
        print("正在查询数据库中的所有球队...")
        all_teams = scraper.db_manager.find_all_teams()
        
        if not all_teams:
            print("数据库中没有找到任何球队数据")
            return
        
        print(f"找到 {len(all_teams)} 支球队，开始批量爬取人员信息...")
        
        success_count = 0
        failed_teams = []
        
        for i, team in enumerate(all_teams, 1):
            team_id = team.get('team_id')
            team_name = team.get('team_name', '未知球队')
            
            if not team_id:
                print(f"[{i}/{len(all_teams)}] 跳过球队 {team_name}：缺少team_id")
                failed_teams.append((team_name, "缺少team_id"))
                continue
            
            print(f"\n[{i}/{len(all_teams)}] 正在爬取球队: {team_name} (ID: {team_id})")
            
            # 构建球队页面URL
            url = f"https://www.dongqiudi.com/team/{team_id}.html"
            
            try:
                # 爬取球队人员数据
                result = scraper.scrape_team_members(url)
                
                if result and result.get('members'):
                    # 尝试与解压缩数据合并（如果存在）
                    enhanced_result = scraper.merge_with_decompressed_data(result)
                    
                    # 更新到数据库
                    members_data = enhanced_result.get('members', [])
                    if scraper.update_team_members_to_db(team_id, members_data):
                        success_count += 1
                        print(f"✓ 成功更新球队 {team_name}，共 {len(members_data)} 名成员")
                    else:
                        failed_teams.append((team_name, "数据库更新失败"))
                        print(f"✗ 球队 {team_name} 数据库更新失败")
                else:
                    failed_teams.append((team_name, "爬取数据为空"))
                    print(f"✗ 球队 {team_name} 爬取数据为空")
                
                # 添加延迟避免请求过于频繁
                time.sleep(2)
                
            except Exception as e:
                failed_teams.append((team_name, str(e)))
                print(f"✗ 球队 {team_name} 爬取失败: {e}")
                continue
        
        # 输出统计结果
        print(f"\n{'='*60}")
        print(f"批量爬取完成！")
        print(f"总球队数: {len(all_teams)}")
        print(f"成功更新: {success_count}")
        print(f"失败数量: {len(failed_teams)}")
        
        if failed_teams:
            print(f"\n失败的球队:")
            for team_name, reason in failed_teams:
                print(f"  - {team_name}: {reason}")
        
    except Exception as e:
         print(f"批量爬取过程中发生异常: {e}")
         logging.error(f"批量爬取异常: {e}")

if __name__ == '__main__':
    main()