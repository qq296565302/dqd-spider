#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
懂球帝球队详情爬虫模块
专门用于爬取球队详情页面的teamDetail数据
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os
from typing import Dict, Optional, Any
from datetime import datetime
import logging

class TeamDetailSpider:
    """
    懂球帝球队详情数据爬虫
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
        
    def get_team_detail(self, team_url: str) -> Optional[Dict[str, Any]]:
        """
        获取球队详情数据
        
        Args:
            team_url: 球队详情页面URL
            
        Returns:
            球队详情数据字典或None
        """
        try:
            self.logger.info(f"正在获取球队详情: {team_url}")
            
            response = self.session.get(team_url, timeout=10)
            
            if response.status_code == 200:
                # 从页面中提取teamDetail数据
                team_detail = self._extract_team_detail_from_page(response.text)
                if team_detail:
                    result = {
                        'team_detail': team_detail,
                        'source_url': team_url,
                        'crawl_time': datetime.now().isoformat(),
                        'method': 'requests'
                    }
                    return result
                else:
                    self.logger.warning(f"未能从页面提取teamDetail数据: {team_url}")
            else:
                self.logger.error(f"请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"获取球队详情异常: {e}")
            
        return None
    

    
    def _extract_team_detail_from_page(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        从页面HTML中提取teamDetail数据
        专门从window.__NUXT__函数中提取teamDetail字段
        
        Args:
            html_content: 页面HTML内容
            
        Returns:
            提取的teamDetail数据字典或None
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 从script标签中提取teamDetail数据
            team_detail = self._extract_team_detail_from_nuxt(soup)
            if team_detail:
                return team_detail
            
            self.logger.warning("未能从页面提取teamDetail数据")
            return None
                
        except Exception as e:
            self.logger.error(f"数据提取异常: {e}")
            
        return None
    
    def _extract_team_detail_from_nuxt(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        从script标签中的window.__NUXT__函数中提取teamDetail数据
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            提取的teamDetail数据或None
        """
        scripts = soup.find_all('script')
        self.logger.info(f"找到 {len(scripts)} 个script标签")
        
        for i, script in enumerate(scripts):
            if not script.string:
                continue
                
            # 查找 window.__NUXT__ = (function...) 格式
            nuxt_function_pattern = r'window\.__NUXT__\s*=\s*(\(function[^;]+)'
            nuxt_match = re.search(nuxt_function_pattern, script.string, re.DOTALL)
            if nuxt_match:
                self.logger.info(f"在第 {i+1} 个script标签中找到 window.__NUXT__ 函数")
                function_content = nuxt_match.group(1)
                self.logger.info(f"函数内容长度: {len(function_content)} 字符")
                
                # 从函数中提取teamDetail数据
                team_detail = self._extract_team_detail_from_function(function_content)
                if team_detail:
                    self.logger.info("成功从 window.__NUXT__ 函数中提取teamDetail数据")
                    return team_detail
                else:
                    self.logger.warning("未能从 window.__NUXT__ 函数中提取teamDetail数据")
                        
        self.logger.warning("未能从任何script标签中找到window.__NUXT__函数")
        return None
    
    def _extract_team_detail_from_function(self, function_str: str) -> Optional[Dict[str, Any]]:
        """
        从函数调用字符串中提取teamDetail数据
        专门查找 return 语句中的 teamDetail 字段
        
        Args:
            function_str: 函数调用字符串
            
        Returns:
            提取的teamDetail数据或None
        """
        try:
            self.logger.info(f"开始解析长度为 {len(function_str)} 字符的混淆函数")
            
            # 专门查找teamDetail字段的正则表达式模式
            team_detail_patterns = [
                # 模式1: return语句中的teamDetail字段
                r'return\s*\{[^{}]*teamDetail\s*:\s*(\{.*?)(?:,\s*error\s*:|,\s*state\s*:|,\s*serverRendered\s*:|\}\s*$)',
                # 模式2: 直接的teamDetail对象
                r'teamDetail\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
                # 模式3: 更宽泛的teamDetail匹配
                r'"teamDetail"\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
                # 模式4: 查找任何包含teamDetail的内容
                r'(teamDetail)',
                # 模式5: 简单的teamDetail字段匹配
                r'teamDetail\s*:\s*(\{)',
                # 模式6: 在return语句中的teamDetail
                r'return\s*\{[^{}]*teamDetail\s*:\s*(\{)',
                # 模式7: 带引号的teamDetail匹配
                r'["\']teamDetail["\']\s*:\s*(\{)'
            ]
            
            # 先保存函数内容到文件以便调试
            with open('function_content_debug.txt', 'w', encoding='utf-8') as f:
                f.write(function_str)
            self.logger.info(f"函数内容已保存到 function_content_debug.txt 用于调试")
            
            # 查找teamDetail的位置并提取完整对象
            if 'teamDetail' in function_str:
                self.logger.info("在函数中找到teamDetail关键字")
                
                # 查找teamDetail:{ 的位置
                team_detail_start = function_str.find('teamDetail:{')
                if team_detail_start != -1:
                    self.logger.info(f"找到teamDetail对象开始位置: {team_detail_start}")
                    
                    # 从teamDetail:{开始提取完整的对象
                    brace_start = function_str.find('{', team_detail_start)
                    if brace_start != -1:
                        # 提取平衡的大括号内容
                        team_detail_content = self._extract_balanced_braces_simple(function_str, brace_start)
                        if team_detail_content:
                            self.logger.info(f"提取到teamDetail对象，长度: {len(team_detail_content)} 字符")
                            
                            # 保存原始teamDetail内容到文件
                            with open('teamdetail_extracted.txt', 'w', encoding='utf-8') as f:
                                f.write(team_detail_content)
                            self.logger.info("teamDetail原始内容已保存到 teamdetail_extracted.txt")
                            
                            # 尝试解析为字典（这里需要处理JavaScript变量）
                            parsed_data = self._parse_team_detail_object(team_detail_content)
                            if parsed_data:
                                self.logger.info(f"成功解析teamDetail数据: {list(parsed_data.keys())[:10]}")
                                return parsed_data
                            else:
                                # 即使解析失败，也返回原始内容
                                self.logger.info("返回原始teamDetail内容")
                                return {'raw_team_detail': team_detail_content}
            else:
                self.logger.warning("在函数中未找到teamDetail关键字")
            
            # 查找teamDetail字段
            for i, pattern in enumerate(team_detail_patterns):
                matches = re.findall(pattern, function_str, re.DOTALL)
                self.logger.info(f"teamDetail模式 {i+1} 找到 {len(matches)} 个匹配")
                
                if matches and i == 3:  # 模式4是简单的teamDetail搜索
                    self.logger.info(f"找到teamDetail关键字 {len(matches)} 次")
                    continue
                
                for match in matches:
                    self.logger.info(f"找到teamDetail数据，长度: {len(match)} 字符")
                    
                    # 使用平衡括号匹配来获取完整的teamDetail对象
                    team_detail_content = self._extract_balanced_braces(match)
                    if team_detail_content:
                        # 尝试将JavaScript对象转换为Python字典
                        team_detail_dict = self._parse_js_object_to_dict(team_detail_content)
                        if team_detail_dict:
                            self.logger.info(f"成功解析teamDetail数据，包含字段: {list(team_detail_dict.keys())[:10]}")
                            return team_detail_dict
                        else:
                            # 如果解析失败，保存原始内容到文件
                            with open('teamdetail_raw.txt', 'w', encoding='utf-8') as f:
                                f.write(team_detail_content)
                            self.logger.info(f"teamDetail原始内容已保存到 teamdetail_raw.txt")
        
        except Exception as e:
            self.logger.error(f"解析函数时发生错误: {e}")
        
        self.logger.warning("未能从函数中提取到有效的teamDetail数据")
        return None

    def _extract_balanced_braces(self, text: str) -> Optional[str]:
        """
        提取平衡的大括号内容
        """
        try:
            # 如果text本身就是以{开头的，直接处理
            if text.startswith('{'):
                return self._extract_balanced_braces_simple(text, 0)
            
            # 否则查找第一个{的位置
            start_pos = text.find('{')
            if start_pos != -1:
                return self._extract_balanced_braces_simple(text, start_pos)
            
            return None
        except Exception as e:
            self.logger.warning(f"提取平衡大括号内容时出错: {e}")
            return None
    
    def _extract_balanced_braces_simple(self, text: str, start_pos: int) -> Optional[str]:
        """
        从指定位置开始提取平衡的大括号内容
        """
        try:
            if start_pos >= len(text) or text[start_pos] != '{':
                return None
            
            brace_count = 0
            pos = start_pos
            
            while pos < len(text):
                if text[pos] == '{':
                    brace_count += 1
                elif text[pos] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return text[start_pos:pos + 1]
                pos += 1
            
            return None
        except Exception as e:
            self.logger.warning(f"提取平衡大括号内容时出错: {e}")
            return None
    
    def _parse_team_detail_object(self, team_detail_str: str) -> Optional[Dict[str, Any]]:
        """
        解析teamDetail对象字符串，专门提取base_info信息
        """
        try:
            # 尝试使用转换工具解析JavaScript对象
            parsed_data = self._convert_js_to_json(team_detail_str)
            if parsed_data and isinstance(parsed_data, dict):
                # 提取base_info字段
                base_info = parsed_data.get('base_info', {})
                if base_info:
                    self.logger.info("成功提取base_info数据")
                    print("\n=== 球队基础信息 ===")
                    for key, value in base_info.items():
                        print(f"{key}: {value}")
                    print("===================\n")
                    
                    return {'base_info': base_info}
                else:
                    self.logger.warning("未找到base_info字段")
            
            return None
        except Exception as e:
            self.logger.warning(f"解析teamDetail对象时出错: {e}")
            return None
    


    def save_team_detail_to_json(self, team_detail, team_id, filename=None):
        """
        将teamDetail数据保存到JSON文件
        """
        if filename is None:
            filename = f"team_detail_{team_id}.json"
        
        try:
            # 创建保存数据的结构
            save_data = {
                "team_id": team_id,
                "crawl_time": datetime.now().isoformat(),
                "team_detail": team_detail
            }
            
            # 保存到JSON文件
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"teamDetail数据已保存到 {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"保存JSON文件失败: {e}")
            return None
    

    
    def _convert_js_to_json(self, js_content: str) -> Optional[Dict[str, Any]]:
        """
        将JavaScript对象转换为JSON格式
        使用类似convert_raw_content.py的逻辑
        """
        import re
        import json
        
        try:
            # 处理Unicode转义字符
            js_content = self._convert_unicode_escapes(js_content)
            
            # 尝试直接解析为JSON
            try:
                return json.loads(js_content)
            except json.JSONDecodeError:
                pass
            
            # 处理JavaScript对象格式
            # 1. 添加引号到属性名
            js_content = re.sub(r'([{,\[]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'\1"\2":', js_content)
            
            # 2. 处理未引用的字符串值
            def replace_value(m):
                value = m.group(1)
                if value not in ['true', 'false', 'null'] and not value.isdigit():
                    return f': "{value}"'
                return m.group(0)
            
            js_content = re.sub(r':\s*([a-zA-Z_$][a-zA-Z0-9_$]*)(?=\s*[,}\]])', replace_value, js_content)
            
            # 3. 处理数组中的未引用变量
            def replace_array_value(m):
                prefix = m.group(1)
                value = m.group(2)
                if value not in ['true', 'false', 'null'] and not value.isdigit():
                    return f'{prefix}"{value}"'
                return m.group(0)
            
            js_content = re.sub(r'(\[\s*|,\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)(?=\s*[,\]])', replace_array_value, js_content)
            
            # 处理单引号字符串
            js_content = re.sub(r"'([^']*)'(?=\s*[,}\]])", r'"\1"', js_content)
            
            # 处理undefined值
            js_content = re.sub(r'\bundefined\b', 'null', js_content)
            
            # 再次尝试解析
            return json.loads(js_content)
            
        except Exception as e:
            self.logger.warning(f"JavaScript到JSON转换失败: {e}")
            return None
    
    def _convert_unicode_escapes(self, text: str) -> str:
        """
        转换Unicode转义字符
        """
        import re
        
        def replace_unicode(match):
            try:
                unicode_str = match.group(1)
                return chr(int(unicode_str, 16))
            except ValueError:
                return match.group(0)
        
        # 处理\u0000格式的Unicode转义
        text = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, text)
        
        # 处理\x00格式的转义
        def replace_hex(match):
            try:
                hex_str = match.group(1)
                return chr(int(hex_str, 16))
            except ValueError:
                return match.group(0)
        
        text = re.sub(r'\\x([0-9a-fA-F]{2})', replace_hex, text)
        
        return text

# 创建全局实例
team_detail_spider = TeamDetailSpider()

if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 测试URL
    test_url = "https://www.dongqiudi.com/team/50000534.html"
    
    print(f"正在测试球队详情爬虫...")
    print(f"测试URL: {test_url}")
    
    # 获取球队详情
    team_detail = team_detail_spider.get_team_detail(test_url)
    
    if team_detail:
        print("\n✅ 成功获取球队详情数据")
        
        # 保存数据到JSON文件
        team_id = "50000534"
        filename = team_detail_spider.save_team_detail_to_json(team_detail.get('team_detail'), team_id)
        if filename:
            print(f"数据已保存到文件: {filename}")
    else:
        print("❌ 未能获取球队详情数据")