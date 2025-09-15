#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
球队数据爬取测试脚本
测试各大联赛球队信息的爬取功能
"""

import sys
import os
import json
import logging
from datetime import datetime

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from team_spider import TeamSpider

def setup_logging():
    """
    设置日志配置
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('teams_crawler.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def save_teams_data(teams_data, filename='teams_data.json'):
    """
    保存球队数据到JSON文件
    
    Args:
        teams_data: 球队数据字典
        filename: 保存的文件名
    """
    try:
        # 确保data目录存在
        data_dir = 'data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        filepath = os.path.join(data_dir, filename)
        
        # 添加元数据
        output_data = {
            'crawl_time': datetime.now().isoformat(),
            'total_leagues': len(teams_data),
            'total_teams': sum(len(teams) for teams in teams_data.values()),
            'leagues': teams_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ 球队数据已保存到: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ 保存数据失败: {e}")
        return None

def test_single_league(spider, league_id):
    """
    测试单个联赛的数据爬取
    
    Args:
        spider: TeamSpider实例
        league_id: 联赛ID
    """
    league_info = spider.league_mapping.get(league_id)
    if not league_info:
        print(f"❌ 未知的联赛ID: {league_id}")
        return []
        
    print(f"\n🔍 正在测试{league_info['name']}数据爬取...")
    teams = spider.get_league_teams(league_id)
    
    if teams:
        print(f"✅ 成功获取{league_info['name']} {len(teams)}支球队:")
        for i, team in enumerate(teams[:5], 1):  # 显示前5支球队
            print(f"  {i}. {team['team_name']} (ID: {team['team_id']})")
        if len(teams) > 5:
            print(f"  ... 还有{len(teams) - 5}支球队")
    else:
        print(f"❌ 未能获取{league_info['name']}球队信息")
        
    return teams

def test_all_leagues(spider):
    """
    测试所有联赛的数据爬取
    
    Args:
        spider: TeamSpider实例
        
    Returns:
        所有联赛的球队数据
    """
    print("🚀 开始爬取所有联赛球队数据...")
    all_teams = spider.get_all_leagues_teams()
    
    print("\n📊 爬取结果汇总:")
    total_teams = 0
    for league_name, teams in all_teams.items():
        team_count = len(teams)
        total_teams += team_count
        status = "✅" if team_count > 0 else "❌"
        print(f"  {status} {league_name}: {team_count}支球队")
        
    print(f"\n🎯 总计: {total_teams}支球队来自{len(all_teams)}个联赛")
    return all_teams

def show_sample_data(teams_data):
    """
    显示示例数据格式
    
    Args:
        teams_data: 球队数据字典
    """
    print("\n📋 数据格式示例:")
    
    for league_name, teams in teams_data.items():
        if teams:  # 如果有球队数据
            sample_team = teams[0]
            print(f"\n{league_name}示例数据:")
            print(json.dumps(sample_team, ensure_ascii=False, indent=2))
            break

def main():
    """
    主函数
    """
    setup_logging()
    
    print("🏈 懂球帝球队数据爬取测试")
    print("=" * 50)
    
    # 创建爬虫实例
    spider = TeamSpider()
    
    # 选择测试模式
    print("\n请选择测试模式:")
    print("1. 测试单个联赛")
    print("2. 测试所有联赛")
    print("3. 快速测试英超")
    
    try:
        choice = input("\n请输入选择 (1-3): ").strip()
        
        if choice == '1':
            print("\n联赛列表:")
            for league_id, info in spider.league_mapping.items():
                print(f"{league_id}. {info['name']}")
            
            league_id = int(input("\n请输入联赛ID: "))
            teams = test_single_league(spider, league_id)
            
            if teams:
                league_name = spider.league_mapping[league_id]['name']
                filename = f"{league_name}_teams.json"
                save_teams_data({league_name: teams}, filename)
                
        elif choice == '2':
            all_teams = test_all_leagues(spider)
            save_teams_data(all_teams)
            show_sample_data(all_teams)
            
        elif choice == '3':
            teams = test_single_league(spider, 1)  # 英超
            if teams:
                save_teams_data({'英超': teams}, '英超_teams.json')
                show_sample_data({'英超': teams})
        else:
            print("❌ 无效选择")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        logging.exception("测试异常")
    
    print("\n🏁 测试完成")

if __name__ == '__main__':
    main()