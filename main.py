#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
懂球帝爬虫项目主程序入口
"""

import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.logger import get_logger, setup_spider_logging
from src.spider import spider
from src.scheduler import scheduler, background_scheduler
from src.database import db_manager
from config.config import SCHEDULER_CONFIG


def setup_environment():
    """
    设置环境
    """
    # 加载环境变量
    try:
        from dotenv import load_dotenv
        env_path = project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass
    
    # 设置日志
    setup_spider_logging()


def run_spider_once(args):
    """
    运行一次爬虫
    
    Args:
        args: 命令行参数
    """
    logger = get_logger(__name__)
    
    try:
        logger.info("开始执行单次爬虫任务")
        
        # 测试数据库连接
        if not db_manager.connect():
            logger.error("数据库连接失败，程序退出")
            return False
        
        # 运行爬虫
        result = spider.run(max_pages=args.pages)
        
        # 打印结果
        print("\n=== 爬虫执行结果 ===")
        print(f"开始时间: {result.get('start_time', 'Unknown')}")
        print(f"结束时间: {result.get('end_time', 'Unknown')}")
        print(f"执行时长: {result.get('duration', 0):.2f} 秒")
        print(f"爬取数量: {result.get('crawled_count', 0)} 条")
        print(f"保存数量: {result.get('saved_count', 0)} 条")
        print(f"成功率: {result.get('success_rate', 0):.2%}")
        
        if 'error' in result:
            print(f"错误信息: {result['error']}")
            return False
        
        logger.info("单次爬虫任务执行完成")
        return True
        
    except Exception as e:
        logger.error(f"执行单次爬虫任务异常: {e}")
        return False
    finally:
        db_manager.close()


def run_scheduler(args):
    """
    运行定时调度器
    
    Args:
        args: 命令行参数
    """
    logger = get_logger(__name__)
    
    try:
        logger.info("启动定时调度器")
        
        # 测试数据库连接
        if not db_manager.connect():
            logger.error("数据库连接失败，程序退出")
            return False
        
        db_manager.close()  # 关闭测试连接
        
        # 如果指定了自定义间隔，添加自定义任务
        if args.interval:
            job_id = scheduler.add_interval_job(
                minutes=args.interval,
                max_pages=args.pages
            )
            logger.info(f"添加自定义间隔任务: {job_id}, 间隔: {args.interval} 分钟")
        
        # 如果指定了cron表达式，添加cron任务
        if args.cron:
            job_id = scheduler.add_cron_job(
                cron_expression=args.cron,
                max_pages=args.pages
            )
            logger.info(f"添加cron任务: {job_id}, 表达式: {args.cron}")
        
        # 打印任务信息
        scheduler.print_jobs()
        
        # 启动调度器（阻塞模式）
        print("\n调度器已启动，按 Ctrl+C 停止...")
        scheduler.start()
        
    except KeyboardInterrupt:
        logger.info("接收到停止信号，正在关闭调度器...")
        scheduler.stop()
        print("调度器已停止")
        return True
    except Exception as e:
        logger.error(f"运行调度器异常: {e}")
        return False


def run_background_scheduler(args):
    """
    运行后台调度器
    
    Args:
        args: 命令行参数
    """
    logger = get_logger(__name__)
    
    try:
        logger.info("启动后台调度器")
        
        # 测试数据库连接
        if not db_manager.connect():
            logger.error("数据库连接失败，程序退出")
            return False
        
        db_manager.close()  # 关闭测试连接
        
        # 启动后台调度器
        background_scheduler.start()
        
        print("后台调度器已启动")
        print("程序将在后台运行，按 Ctrl+C 停止...")
        
        # 保持程序运行
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("接收到停止信号，正在关闭后台调度器...")
            background_scheduler.stop()
            print("后台调度器已停止")
        
        return True
        
    except Exception as e:
        logger.error(f"运行后台调度器异常: {e}")
        return False


def test_database(args):
    """
    测试数据库连接
    
    Args:
        args: 命令行参数
    """
    logger = get_logger(__name__)
    
    try:
        print("正在测试数据库连接...")
        
        # 连接数据库
        if db_manager.connect():
            print("✓ 数据库连接成功")
            
            # 获取数据库统计信息
            total_count = db_manager.count_news()
            print(f"✓ 数据库中共有 {total_count} 条新闻记录")
            
            # 获取最近的几条记录
            recent_news = db_manager.find_news(limit=5)
            if recent_news:
                print("\n最近的5条新闻:")
                for i, news in enumerate(recent_news, 1):
                    print(f"{i}. {news.get('title', 'Unknown')} - {news.get('created_at', 'Unknown')}")
            
            db_manager.close()
            return True
        else:
            print("✗ 数据库连接失败")
            return False
            
    except Exception as e:
        logger.error(f"测试数据库连接异常: {e}")
        print(f"✗ 数据库连接异常: {e}")
        return False


def show_status(args):
    """
    显示系统状态
    
    Args:
        args: 命令行参数
    """
    print("=== 懂球帝爬虫系统状态 ===")
    
    # 显示配置信息
    print(f"\n配置信息:")
    print(f"  数据库: mongodb://localhost:27017/thunderstorm-news")
    print(f"  调度间隔: {SCHEDULER_CONFIG['interval_minutes']} 分钟")
    print(f"  最大工作线程: {SCHEDULER_CONFIG['max_workers']}")
    print(f"  时区: {SCHEDULER_CONFIG['timezone']}")
    
    # 测试数据库连接
    print(f"\n数据库状态:")
    if db_manager.connect():
        total_count = db_manager.count_news()
        print(f"  ✓ 连接正常")
        print(f"  ✓ 新闻记录数: {total_count}")
        db_manager.close()
    else:
        print(f"  ✗ 连接失败")
    
    # 显示日志文件信息
    print(f"\n日志文件:")
    log_dir = project_root / 'logs'
    if log_dir.exists():
        for log_file in log_dir.glob('*.log'):
            size = log_file.stat().st_size
            print(f"  {log_file.name}: {size / 1024:.1f} KB")
    else:
        print(f"  日志目录不存在")


def main():
    """
    主函数
    """
    # 设置环境
    setup_environment()
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description='懂球帝爬虫项目',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py run --pages 5                    # 运行一次爬虫，爬取5页
  python main.py schedule --interval 30           # 启动定时调度器，每30分钟执行一次
  python main.py schedule --cron "0 */2 * * *"     # 启动定时调度器，每2小时执行一次
  python main.py background                       # 启动后台调度器
  python main.py test                             # 测试数据库连接
  python main.py status                           # 显示系统状态
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 运行一次爬虫
    run_parser = subparsers.add_parser('run', help='运行一次爬虫')
    run_parser.add_argument('--pages', type=int, default=3, help='爬取页数 (默认: 3)')
    
    # 启动调度器
    schedule_parser = subparsers.add_parser('schedule', help='启动定时调度器')
    schedule_parser.add_argument('--interval', type=int, help='执行间隔（分钟）')
    schedule_parser.add_argument('--cron', type=str, help='cron表达式')
    schedule_parser.add_argument('--pages', type=int, default=3, help='爬取页数 (默认: 3)')
    
    # 启动后台调度器
    background_parser = subparsers.add_parser('background', help='启动后台调度器')
    background_parser.add_argument('--pages', type=int, default=3, help='爬取页数 (默认: 3)')
    
    # 测试数据库
    test_parser = subparsers.add_parser('test', help='测试数据库连接')
    
    # 显示状态
    status_parser = subparsers.add_parser('status', help='显示系统状态')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 执行对应的命令
    success = False
    
    if args.command == 'run':
        success = run_spider_once(args)
    elif args.command == 'schedule':
        success = run_scheduler(args)
    elif args.command == 'background':
        success = run_background_scheduler(args)
    elif args.command == 'test':
        success = test_database(args)
    elif args.command == 'status':
        show_status(args)
        success = True
    
    # 退出程序
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()