#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AC米兰球队人员数据爬虫
爬取AC米兰球队页面中的所有人员信息（球员、教练、工作人员等）
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

class ACMilanTeamScraper:
    """AC米兰球队人员数据爬虫类"""
    
    def __init__(self):
        """初始化爬虫"""
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
                logging.FileHandler('ac_milan_team_scraper.log', encoding='utf-8')
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
                    members_data.append(member_data)
            
            result = {
                'url': url,
                'scrape_time': datetime.now().isoformat(),
                'total_members': len(members_data),
                'members': members_data
            }
            
            self.logger.info(f"成功解析 {len(members_data)} 名人员的数据")
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"网络请求失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"爬取过程中发生异常: {e}")
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
                    elif i == 3:  # 姓名
                        member_data['name'] = item_span.get_text(strip=True)
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
    """主函数"""
    url = "https://www.dongqiudi.com/team/50001038.html"
    
    scraper = ACMilanTeamScraper()
    
    # 爬取数据
    print("正在爬取AC米兰球队数据...")
    result = scraper.scrape_team_members(url)
    
    if result:
        # 尝试与解压缩数据合并
        print("\n正在合并解压缩数据...")
        enhanced_result = scraper.merge_with_decompressed_data(result)
        
        # 打印摘要
        scraper.print_summary(enhanced_result)
        
        # 保存合并后的数据
        if enhanced_result.get('has_enhanced_data'):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ac_milan_enhanced_data_{timestamp}.json"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ac_milan_team_members_{timestamp}.json"
        
        saved_file = scraper.save_to_json(enhanced_result, filename)
        print(f"\nData saved to: {saved_file}")
        
        # 显示增强数据统计
        if enhanced_result.get('has_enhanced_data'):
            members = enhanced_result.get('members', [])
            enhanced_count = sum(1 for m in members if m.get('person_id'))
            print(f"\n=== Enhanced Data Statistics ===")
            print(f"Total members: {len(members)}")
            print(f"Enhanced with person_id: {enhanced_count}")
            print(f"Enhancement rate: {enhanced_count/len(members)*100:.1f}%" if members else "0%")
        
    else:
        print("Failed to scrape data. Please check network connection and URL.")

if __name__ == '__main__':
    main()