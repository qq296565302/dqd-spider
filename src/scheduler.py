# -*- coding: utf-8 -*-
"""
定时任务调度器模块
"""

import logging
import signal
import sys
from datetime import datetime
from typing import Dict, Any, Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from pytz import timezone

from config.config import SCHEDULER_CONFIG
from src.spider import spider


class SpiderScheduler:
    """
    爬虫定时任务调度器
    """
    
    def __init__(self, background: bool = False):
        """
        初始化调度器
        
        Args:
            background: 是否使用后台调度器
        """
        self.logger = logging.getLogger(__name__)
        self.background = background
        
        # 配置调度器
        jobstores = {
            'default': MemoryJobStore()
        }
        
        executors = {
            'default': ThreadPoolExecutor(max_workers=SCHEDULER_CONFIG['max_workers'])
        }
        
        job_defaults = {
            'coalesce': True,  # 合并多个相同的任务
            'max_instances': 1,  # 同一时间只允许一个实例运行
            'misfire_grace_time': 300  # 任务错过执行时间的宽限期（秒）
        }
        
        # 创建调度器
        if background:
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=timezone(SCHEDULER_CONFIG['timezone'])
            )
        else:
            self.scheduler = BlockingScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=timezone(SCHEDULER_CONFIG['timezone'])
            )
        
        # 添加事件监听器
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        # 注册信号处理器
        self._register_signal_handlers()
    
    def _job_listener(self, event):
        """
        任务执行事件监听器
        
        Args:
            event: 任务事件
        """
        if event.exception:
            self.logger.error(f"任务执行失败: {event.job_id}, 异常: {event.exception}")
        else:
            self.logger.info(f"任务执行成功: {event.job_id}, 返回值: {event.retval}")
    
    def _register_signal_handlers(self):
        """
        注册信号处理器
        """
        def signal_handler(signum, frame):
            self.logger.info(f"接收到信号 {signum}，正在关闭调度器...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _spider_job(self, max_pages: int = 5) -> Dict[str, Any]:
        """
        爬虫任务函数
        
        Args:
            max_pages: 最大爬取页数
            
        Returns:
            Dict: 任务执行结果
        """
        try:
            self.logger.info("开始执行定时爬虫任务")
            result = spider.run(max_pages)
            self.logger.info(f"定时爬虫任务完成: {result}")
            return result
        except Exception as e:
            self.logger.error(f"定时爬虫任务异常: {e}")
            raise
    
    def add_interval_job(self, 
                        job_func: Callable = None,
                        minutes: int = None,
                        hours: int = None,
                        days: int = None,
                        job_id: str = None,
                        **kwargs) -> str:
        """
        添加间隔执行的任务
        
        Args:
            job_func: 任务函数
            minutes: 间隔分钟数
            hours: 间隔小时数
            days: 间隔天数
            job_id: 任务ID
            **kwargs: 其他参数
            
        Returns:
            str: 任务ID
        """
        if job_func is None:
            job_func = self._spider_job
        
        if job_id is None:
            job_id = f"interval_job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 使用配置中的默认间隔
        if not any([minutes, hours, days]):
            minutes = SCHEDULER_CONFIG['interval_minutes']
        
        trigger = IntervalTrigger(
            minutes=minutes,
            hours=hours,
            days=days,
            timezone=timezone(SCHEDULER_CONFIG['timezone'])
        )
        
        self.scheduler.add_job(
            func=job_func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs
        )
        
        self.logger.info(f"添加间隔任务: {job_id}, 间隔: {minutes}分钟 {hours}小时 {days}天")
        return job_id
    
    def add_cron_job(self,
                    job_func: Callable = None,
                    cron_expression: str = None,
                    hour: int = None,
                    minute: int = None,
                    second: int = None,
                    day_of_week: str = None,
                    job_id: str = None,
                    **kwargs) -> str:
        """
        添加定时执行的任务（cron格式）
        
        Args:
            job_func: 任务函数
            cron_expression: cron表达式
            hour: 小时
            minute: 分钟
            second: 秒
            day_of_week: 星期几
            job_id: 任务ID
            **kwargs: 其他参数
            
        Returns:
            str: 任务ID
        """
        if job_func is None:
            job_func = self._spider_job
        
        if job_id is None:
            job_id = f"cron_job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if cron_expression:
            # 解析cron表达式
            cron_parts = cron_expression.split()
            if len(cron_parts) >= 5:
                trigger = CronTrigger(
                    minute=cron_parts[0],
                    hour=cron_parts[1],
                    day=cron_parts[2],
                    month=cron_parts[3],
                    day_of_week=cron_parts[4],
                    timezone=timezone(SCHEDULER_CONFIG['timezone'])
                )
        else:
            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                second=second,
                day_of_week=day_of_week,
                timezone=timezone(SCHEDULER_CONFIG['timezone'])
            )
        
        self.scheduler.add_job(
            func=job_func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs
        )
        
        self.logger.info(f"添加定时任务: {job_id}, 触发器: {trigger}")
        return job_id
    
    def add_default_spider_job(self) -> str:
        """
        添加默认的爬虫任务
        
        Returns:
            str: 任务ID
        """
        job_id = "default_spider_job"
        
        # 每30分钟执行一次爬虫任务
        return self.add_interval_job(
            job_func=self._spider_job,
            minutes=SCHEDULER_CONFIG['interval_minutes'],
            job_id=job_id,
            max_pages=3  # 默认爬取3页
        )
    
    def remove_job(self, job_id: str) -> bool:
        """
        移除任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            bool: 是否成功移除
        """
        try:
            self.scheduler.remove_job(job_id)
            self.logger.info(f"成功移除任务: {job_id}")
            return True
        except Exception as e:
            self.logger.error(f"移除任务失败: {job_id}, 错误: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """
        暂停任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            bool: 是否成功暂停
        """
        try:
            self.scheduler.pause_job(job_id)
            self.logger.info(f"成功暂停任务: {job_id}")
            return True
        except Exception as e:
            self.logger.error(f"暂停任务失败: {job_id}, 错误: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """
        恢复任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            bool: 是否成功恢复
        """
        try:
            self.scheduler.resume_job(job_id)
            self.logger.info(f"成功恢复任务: {job_id}")
            return True
        except Exception as e:
            self.logger.error(f"恢复任务失败: {job_id}, 错误: {e}")
            return False
    
    def get_jobs(self) -> list:
        """
        获取所有任务
        
        Returns:
            list: 任务列表
        """
        return self.scheduler.get_jobs()
    
    def get_job_info(self, job_id: str) -> Dict[str, Any]:
        """
        获取任务信息
        
        Args:
            job_id: 任务ID
            
        Returns:
            Dict: 任务信息
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return {
                    'id': job.id,
                    'name': job.name,
                    'func': str(job.func),
                    'trigger': str(job.trigger),
                    'next_run_time': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else None,
                    'pending': job.pending
                }
        except Exception as e:
            self.logger.error(f"获取任务信息失败: {job_id}, 错误: {e}")
        
        return {}
    
    def start(self):
        """
        启动调度器
        """
        try:
            self.logger.info("启动任务调度器")
            
            # 添加默认爬虫任务
            self.add_default_spider_job()
            
            # 启动调度器
            self.scheduler.start()
            
        except Exception as e:
            self.logger.error(f"启动调度器失败: {e}")
            raise
    
    def stop(self, wait: bool = True):
        """
        停止调度器
        
        Args:
            wait: 是否等待正在执行的任务完成
        """
        try:
            self.logger.info("停止任务调度器")
            self.scheduler.shutdown(wait=wait)
        except Exception as e:
            self.logger.error(f"停止调度器失败: {e}")
    
    def run_once(self, max_pages: int = 5) -> Dict[str, Any]:
        """
        立即执行一次爬虫任务
        
        Args:
            max_pages: 最大爬取页数
            
        Returns:
            Dict: 执行结果
        """
        self.logger.info("立即执行爬虫任务")
        return self._spider_job(max_pages)
    
    def print_jobs(self):
        """
        打印所有任务信息
        """
        jobs = self.get_jobs()
        if not jobs:
            print("没有任务")
            return
        
        print("\n当前任务列表:")
        print("-" * 80)
        print(f"{'任务ID':<20} {'下次执行时间':<20} {'触发器':<30} {'状态':<10}")
        print("-" * 80)
        
        for job in jobs:
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else '未知'
            status = '暂停' if job.pending else '运行中'
            print(f"{job.id:<20} {next_run:<20} {str(job.trigger):<30} {status:<10}")
        
        print("-" * 80)


# 创建调度器实例
scheduler = SpiderScheduler()
background_scheduler = SpiderScheduler(background=True)