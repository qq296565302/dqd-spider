#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试球队详情爬虫的各种提取方法
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.team_detail_spider import TeamDetailSpider
import logging

def test_team_detail_extraction():
    """
    测试球队详情提取功能
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    spider = TeamDetailSpider()
    
    # 测试URL
    test_url = "https://www.dongqiudi.com/team/50000534.html"
    
    print("=" * 60)
    print("测试球队详情爬虫")
    print(f"测试URL: {test_url}")
    print("=" * 60)
    
    # 获取球队详情
    team_detail = spider.get_team_detail(test_url)
    
    if team_detail:
        print("\n✅ 成功获取球队详情数据!")
        print(f"数据类型: {team_detail.get('type', 'unknown')}")
        print(f"数据来源: {team_detail.get('source', 'unknown')}")
        print(f"提取方法: {team_detail.get('method', 'unknown')}")
        
        # 解析数据
        parsed_data = spider.parse_team_detail(team_detail)
        
        print("\n📋 解析后的球队信息:")
        print(f"  球队ID: {parsed_data.get('team_id', 'N/A')}")
        print(f"  球队名称: {parsed_data.get('team_name', 'N/A')}")
        print(f"  英文名称: {parsed_data.get('team_name_en', 'N/A')}")
        print(f"  成立年份: {parsed_data.get('founded_year', 'N/A')}")
        print(f"  国家: {parsed_data.get('country', 'N/A')}")
        print(f"  城市: {parsed_data.get('city', 'N/A')}")
        print(f"  主场: {parsed_data.get('stadium', 'N/A')}")
        print(f"  容量: {parsed_data.get('capacity', 'N/A')}")
        print(f"  描述: {parsed_data.get('description', 'N/A')[:100]}...")
        print(f"  数据来源: {parsed_data.get('data_source', 'N/A')}")
        print(f"  数据类型: {parsed_data.get('data_type', 'N/A')}")
        
        # 显示原始数据结构
        if 'raw_data' in parsed_data:
            raw_data = parsed_data['raw_data']
            if isinstance(raw_data, dict):
                print(f"\n🔍 原始数据字段: {list(raw_data.keys())}")
                if 'data' in raw_data and isinstance(raw_data['data'], dict):
                    print(f"   内部数据字段: {list(raw_data['data'].keys())}")
        
        return True
    else:
        print("\n❌ 未能获取球队详情数据")
        return False

def test_multiple_teams():
    """
    测试多个球队
    """
    spider = TeamDetailSpider()
    
    # 测试多个球队ID
    team_ids = ["50000534", "50000535", "50000536"]
    
    print("\n" + "=" * 60)
    print("测试多个球队")
    print("=" * 60)
    
    success_count = 0
    for team_id in team_ids:
        print(f"\n测试球队ID: {team_id}")
        team_detail = spider.get_team_detail_by_id(team_id)
        
        if team_detail:
            parsed_data = spider.parse_team_detail(team_detail)
            team_name = parsed_data.get('team_name', 'Unknown')
            data_source = parsed_data.get('data_source', 'Unknown')
            print(f"  ✅ 成功: {team_name} (来源: {data_source})")
            success_count += 1
        else:
            print(f"  ❌ 失败")
    
    print(f"\n📊 成功率: {success_count}/{len(team_ids)} ({success_count/len(team_ids)*100:.1f}%)")

if __name__ == '__main__':
    # 测试单个球队详情提取
    success = test_team_detail_extraction()
    
    if success:
        # 如果单个测试成功，继续测试多个球队
        test_multiple_teams()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)