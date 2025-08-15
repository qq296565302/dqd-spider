# -*- coding: utf-8 -*-
"""
懂球帝网站爬虫核心模块
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from retrying import retry
from fake_useragent import UserAgent

from config.config import DONGQIUDI_CONFIG
from src.database import db_manager


class DongQiuDiSpider:
    """
    懂球帝网站爬虫类
    """
    
    def __init__(self):
        """
        初始化爬虫
        """
        self.session = requests.Session()
        self.base_url = DONGQIUDI_CONFIG['base_url']
        self.headers = DONGQIUDI_CONFIG['headers'].copy()
        self.timeout = DONGQIUDI_CONFIG['timeout']
        self.retry_times = DONGQIUDI_CONFIG['retry_times']
        self.retry_delay = DONGQIUDI_CONFIG['retry_delay']
        self.logger = logging.getLogger(__name__)
        
        # 初始化User-Agent生成器
        self.ua = UserAgent()
        
        # 设置session headers
        self.session.headers.update(self.headers)
        
    def _get_random_user_agent(self) -> str:
        """
        获取随机User-Agent
        
        Returns:
            str: 随机User-Agent字符串
        """
        try:
            return self.ua.random
        except Exception:
            return self.headers['User-Agent']
    
    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def _make_request(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        发送HTTP请求
        
        Args:
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            Optional[requests.Response]: 响应对象
        """
        try:
            # 更新User-Agent
            headers = kwargs.get('headers', {})
            headers['User-Agent'] = self._get_random_user_agent()
            kwargs['headers'] = headers
            
            # 设置超时
            kwargs.setdefault('timeout', self.timeout)
            
            response = self.session.get(url, **kwargs)
            response.raise_for_status()
            
            # 添加延迟，避免请求过于频繁
            time.sleep(1)
            
            return response
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求失败: {url}, 错误: {e}")
            raise
        except Exception as e:
            self.logger.error(f"请求异常: {url}, 错误: {e}")
            raise
    
    def _parse_news_list(self, html: str) -> List[Dict[str, Any]]:
        """
        解析新闻列表页面
        
        Args:
            html: 页面HTML内容
            
        Returns:
            List[Dict]: 新闻列表
        """
        news_list = []
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 查找新闻条目
            news_items = soup.find_all(['div', 'article'], class_=re.compile(r'news|article|item'))
            
            for item in news_items:
                news_data = self._extract_news_item(item)
                if news_data:
                    news_list.append(news_data)
            
            self.logger.info(f"解析到 {len(news_list)} 条新闻")
            
        except Exception as e:
            self.logger.error(f"解析新闻列表失败: {e}")
        
        return news_list
    
    def _extract_news_item(self, item) -> Optional[Dict[str, Any]]:
        """
        提取单个新闻条目信息
        
        Args:
            item: BeautifulSoup元素
            
        Returns:
            Optional[Dict]: 新闻数据
        """
        try:
            news_data = {}
            
            # 提取标题和链接
            title_elem = item.find(['a', 'h1', 'h2', 'h3', 'h4'], href=True) or item.find(['h1', 'h2', 'h3', 'h4'])
            if title_elem:
                news_data['title'] = title_elem.get_text(strip=True)
                
                # 提取链接
                if title_elem.get('href'):
                    news_data['url'] = urljoin(self.base_url, title_elem['href'])
                else:
                    # 如果标题元素没有链接，查找父级或兄弟元素中的链接
                    link_elem = item.find('a', href=True)
                    if link_elem:
                        news_data['url'] = urljoin(self.base_url, link_elem['href'])
            
            # 提取摘要
            summary_elem = item.find(['p', 'div'], class_=re.compile(r'summary|desc|content'))
            if summary_elem:
                news_data['summary'] = summary_elem.get_text(strip=True)
            
            # 提取时间
            time_elem = item.find(['time', 'span'], class_=re.compile(r'time|date'))
            if time_elem:
                time_text = time_elem.get_text(strip=True)
                news_data['publish_time'] = self._parse_time(time_text)
            
            # 提取图片
            img_elem = item.find('img')
            if img_elem and img_elem.get('src'):
                news_data['image_url'] = urljoin(self.base_url, img_elem['src'])
            
            # 提取作者
            author_elem = item.find(['span', 'div'], class_=re.compile(r'author|writer'))
            if author_elem:
                news_data['author'] = author_elem.get_text(strip=True)
            
            # 提取分类
            category_elem = item.find(['span', 'div'], class_=re.compile(r'category|tag'))
            if category_elem:
                news_data['category'] = category_elem.get_text(strip=True)
            
            # 验证必要字段
            if news_data.get('title') and news_data.get('url'):
                return news_data
            
        except Exception as e:
            self.logger.warning(f"提取新闻条目失败: {e}")
        
        return None
    
    def _parse_time(self, time_text: str) -> Optional[str]:
        """
        解析时间字符串
        
        Args:
            time_text: 时间文本
            
        Returns:
            Optional[str]: 格式化的时间字符串
        """
        try:
            # 处理相对时间
            if '分钟前' in time_text:
                minutes = re.search(r'(\d+)分钟前', time_text)
                if minutes:
                    return (datetime.now() - timedelta(minutes=int(minutes.group(1)))).strftime('%Y-%m-%d %H:%M:%S')
            
            elif '小时前' in time_text:
                hours = re.search(r'(\d+)小时前', time_text)
                if hours:
                    return (datetime.now() - timedelta(hours=int(hours.group(1)))).strftime('%Y-%m-%d %H:%M:%S')
            
            elif '天前' in time_text:
                days = re.search(r'(\d+)天前', time_text)
                if days:
                    return (datetime.now() - timedelta(days=int(days.group(1)))).strftime('%Y-%m-%d %H:%M:%S')
            
            # 处理绝对时间格式
            time_patterns = [
                r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})',
                r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})',
                r'(\d{4})-(\d{2})-(\d{2})',
                r'(\d{2})-(\d{2})\s+(\d{2}):(\d{2})',
                r'(\d{2}):(\d{2})'
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, time_text)
                if match:
                    return time_text
            
        except Exception as e:
            self.logger.warning(f"解析时间失败: {time_text}, 错误: {e}")
        
        return None
    
    def _get_news_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """
        获取新闻详情
        
        Args:
            url: 新闻详情页URL
            
        Returns:
            Optional[Dict]: 新闻详情数据
        """
        try:
            response = self._make_request(url)
            if not response:
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            detail_data = {}
            
            # 提取正文内容
            content_selectors = [
                '.article-content',
                '.news-content',
                '.content',
                'article',
                '.detail-content'
            ]
            
            content = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(strip=True)
                    break
            
            if content:
                detail_data['content'] = content
            
            # 提取标签
            tags = []
            tag_elems = soup.find_all(['span', 'a'], class_=re.compile(r'tag|label'))
            for tag_elem in tag_elems:
                tag_text = tag_elem.get_text(strip=True)
                if tag_text and len(tag_text) < 20:
                    tags.append(tag_text)
            
            if tags:
                detail_data['tags'] = tags
            
            return detail_data
            
        except Exception as e:
            self.logger.error(f"获取新闻详情失败: {url}, 错误: {e}")
            return None
    
    def crawl_news(self, max_pages: int = 5) -> List[Dict[str, Any]]:
        """
        爬取新闻数据
        
        Args:
            max_pages: 最大爬取页数
            
        Returns:
            List[Dict]: 爬取的新闻列表
        """
        all_news = []
        
        try:
            self.logger.info(f"开始爬取懂球帝新闻，最大页数: {max_pages}")
            
            for page in range(1, max_pages + 1):
                self.logger.info(f"正在爬取第 {page} 页")
                
                # 构建页面URL
                if page == 1:
                    page_url = self.base_url
                else:
                    page_url = f"{self.base_url}?page={page}"
                
                # 获取页面内容
                response = self._make_request(page_url)
                if not response:
                    self.logger.warning(f"第 {page} 页请求失败，跳过")
                    continue
                
                # 解析新闻列表
                news_list = self._parse_news_list(response.text)
                
                if not news_list:
                    self.logger.warning(f"第 {page} 页没有找到新闻，停止爬取")
                    break
                
                # 获取新闻详情（可选）
                for news in news_list:
                    if news.get('url'):
                        detail = self._get_news_detail(news['url'])
                        if detail:
                            news.update(detail)
                
                all_news.extend(news_list)
                
                self.logger.info(f"第 {page} 页爬取完成，获得 {len(news_list)} 条新闻")
                
                # 添加页面间延迟
                time.sleep(2)
            
            self.logger.info(f"爬取完成，总共获得 {len(all_news)} 条新闻")
            
        except Exception as e:
            self.logger.error(f"爬取新闻异常: {e}")
        
        return all_news
    
    def save_to_database(self, news_list: List[Dict[str, Any]]) -> int:
        """
        保存新闻数据到数据库
        
        Args:
            news_list: 新闻数据列表
            
        Returns:
            int: 成功保存的数据条数
        """
        if not news_list:
            return 0
        
        try:
            # 连接数据库
            if not db_manager.connect():
                self.logger.error("数据库连接失败")
                return 0
            
            # 批量插入数据
            success_count = db_manager.insert_many_news(news_list)
            
            self.logger.info(f"成功保存 {success_count}/{len(news_list)} 条新闻到数据库")
            
            return success_count
            
        except Exception as e:
            self.logger.error(f"保存数据到数据库异常: {e}")
            return 0
    
    def run(self, max_pages: int = 5) -> Dict[str, Any]:
        """
        运行爬虫
        
        Args:
            max_pages: 最大爬取页数
            
        Returns:
            Dict: 运行结果统计
        """
        start_time = datetime.now()
        
        try:
            self.logger.info("懂球帝爬虫开始运行")
            
            # 爬取新闻
            news_list = self.crawl_news(max_pages)
            
            # 保存到数据库
            saved_count = self.save_to_database(news_list)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'duration': duration,
                'crawled_count': len(news_list),
                'saved_count': saved_count,
                'success_rate': saved_count / len(news_list) if news_list else 0
            }
            
            self.logger.info(f"爬虫运行完成: {result}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"爬虫运行异常: {e}")
            return {
                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': str(e)
            }
        finally:
            # 关闭数据库连接
            db_manager.close()


# 创建爬虫实例
spider = DongQiuDiSpider()