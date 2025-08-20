#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量爬取球队详情脚本
从数据库获取所有球队，逐一爬取base_info信息并更新到数据库
"""

import logging
import time
from typing import Dict, Any, Optional
import sys
import os

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from team_database import TeamDatabaseManager
from team_detail_spider import TeamDetailSpider

class BatchTeamDetailCrawler:
    """
    批量球队详情爬虫
    """
    
    def __init__(self):
        """
        初始化批量爬虫
        """
        self.db_manager = TeamDatabaseManager()
        self.spider = TeamDetailSpider()
        self.logger = logging.getLogger(__name__)
        
        # 爬取统计
        self.total_teams = 0
        self.success_count = 0
        self.failed_count = 0
        self.updated_count = 0
        
    def run(self, delay_seconds: float = 2.0, max_teams: Optional[int] = None):
        """
        运行批量爬取任务
        
        Args:
            delay_seconds: 每次请求之间的延迟时间（秒）
            max_teams: 最大爬取球队数量，None表示爬取所有
        """
        try:
            # 连接数据库
            if not self.db_manager.connect():
                self.logger.error("数据库连接失败，退出程序")
                return
            
            # 获取所有球队
            teams = self.db_manager.find_all_teams()
            if not teams:
                self.logger.warning("数据库中没有找到球队数据")
                return
            
            self.total_teams = len(teams)
            if max_teams:
                teams = teams[:max_teams]
                self.logger.info(f"限制爬取数量为 {max_teams} 支球队")
            
            self.logger.info(f"开始批量爬取 {len(teams)} 支球队的详情信息")
            
            # 逐一爬取球队详情
            for i, team in enumerate(teams, 1):
                team_id = team.get('team_id')
                team_name = team.get('team_name', '未知球队')
                
                self.logger.info(f"[{i}/{len(teams)}] 正在爬取球队: {team_name} (ID: {team_id})")
                
                try:
                    # 构建球队详情页面URL
                    team_url = f"https://www.dongqiudi.com/team/{team_id}.html"
                    
                    # 爬取球队详情
                    team_detail = self.spider.get_team_detail(team_url)
                    
                    if team_detail and 'team_detail' in team_detail:
                        parsed_detail = team_detail['team_detail']
                        
                        if 'base_info' in parsed_detail:
                            base_info = parsed_detail['base_info']
                            
                            # 更新数据库
                            if self.db_manager.update_team_base_info(team_id, base_info):
                                self.success_count += 1
                                self.updated_count += 1
                                self.logger.info(f"✅ 成功更新球队 {team_name} 的详情信息")
                            else:
                                self.failed_count += 1
                                self.logger.warning(f"❌ 更新球队 {team_name} 的详情信息失败")
                        else:
                            self.failed_count += 1
                            self.logger.warning(f"❌ 球队 {team_name} 未找到base_info数据")
                    else:
                        self.failed_count += 1
                        self.logger.warning(f"❌ 球队 {team_name} 爬取失败")
                        
                except Exception as e:
                    self.failed_count += 1
                    self.logger.error(f"❌ 爬取球队 {team_name} 时发生异常: {e}")
                
                # 打印进度
                if i % 10 == 0 or i == len(teams):
                    self._print_progress(i, len(teams))
                
                # 延迟以避免过于频繁的请求
                if i < len(teams):  # 最后一个不需要延迟
                    time.sleep(delay_seconds)
            
            # 打印最终统计
            self._print_final_stats()
            
        except Exception as e:
            self.logger.error(f"批量爬取过程中发生异常: {e}")
        finally:
            # 关闭数据库连接
            self.db_manager.close()
    
    def _print_progress(self, current: int, total: int):
        """
        打印进度信息
        """
        progress = (current / total) * 100
        print(f"\n=== 进度报告 ===")
        print(f"进度: {current}/{total} ({progress:.1f}%)")
        print(f"成功: {self.success_count}")
        print(f"失败: {self.failed_count}")
        print(f"更新: {self.updated_count}")
        print("================\n")
    
    def _print_final_stats(self):
        """
        打印最终统计信息
        """
        print("\n" + "="*50)
        print("批量爬取完成！")
        print("="*50)
        print(f"总球队数: {self.total_teams}")
        print(f"成功爬取: {self.success_count}")
        print(f"爬取失败: {self.failed_count}")
        print(f"数据库更新: {self.updated_count}")
        print(f"成功率: {(self.success_count / max(self.total_teams, 1)) * 100:.1f}%")
        print("="*50)

def main():
    """
    主函数
    """
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('batch_crawl.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    print("开始批量爬取球队详情信息...")
    print("注意：此过程可能需要较长时间，请耐心等待")
    
    # 创建批量爬虫实例
    crawler = BatchTeamDetailCrawler()
    
    # 运行批量爬取（可以设置最大爬取数量进行测试）
    # crawler.run(delay_seconds=2.0, max_teams=5)  # 测试模式：只爬取5支球队
    crawler.run(delay_seconds=2.0)  # 正式模式：爬取所有球队

if __name__ == '__main__':
    main()