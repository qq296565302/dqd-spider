# 懂球帝爬虫项目

一个用于爬取懂球帝网站新闻数据的Python项目，支持定时任务和MongoDB数据存储。

## 项目特性

- 🕷️ **智能爬虫**: 自动爬取懂球帝网站的最新足球新闻
- ⏰ **定时任务**: 支持灵活的定时调度，可配置间隔时间或cron表达式
- 🗄️ **数据存储**: 将爬取的数据保存到MongoDB数据库
- 📝 **日志记录**: 完整的日志系统，支持文件轮转和分级记录
- 🔧 **配置管理**: 灵活的配置系统，支持环境变量
- 🛡️ **错误处理**: 完善的异常处理和重试机制
- 📊 **数据去重**: 自动检测和过滤重复数据

## 项目结构

```
DongQiuDi_Spider/
├── src/                    # 源代码目录
│   ├── __init__.py
│   ├── spider.py          # 爬虫核心模块
│   ├── database.py        # 数据库连接模块
│   ├── scheduler.py       # 定时任务调度器
│   └── logger.py          # 日志配置模块
├── config/                 # 配置文件目录
│   ├── __init__.py
│   └── config.py          # 项目配置
├── logs/                   # 日志文件目录
├── data/                   # 数据文件目录
├── main.py                 # 主程序入口
├── requirements.txt        # 项目依赖
├── .env                    # 环境配置文件
├── LICENSE                 # 许可证
└── README.md              # 项目说明
```

## 安装和配置

### 1. 环境要求

- Python 3.7+
- MongoDB 4.0+

### 2. 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd DongQiuDi_Spider

# 安装Python依赖
pip install -r requirements.txt
```

### 3. 配置MongoDB

确保MongoDB服务正在运行，默认配置为：
- 主机: localhost
- 端口: 27017
- 数据库: thunderstorm-news
- 集合: dongqiudi_news

### 4. 环境配置

复制并编辑环境配置文件：

```bash
cp .env.example .env
```

根据需要修改 `.env` 文件中的配置项。

## 使用方法

### 命令行接口

项目提供了完整的命令行接口：

```bash
# 查看帮助
python main.py --help

# 运行一次爬虫（爬取3页）
python main.py run

# 运行一次爬虫（爬取5页）
python main.py run --pages 5

# 启动定时调度器（每30分钟执行一次）
python main.py schedule --interval 30

# 启动定时调度器（使用cron表达式，每2小时执行一次）
python main.py schedule --cron "0 */2 * * *"

# 启动后台调度器
python main.py background

# 测试数据库连接
python main.py test

# 显示系统状态
python main.py status
```

### 编程接口

也可以在代码中直接使用：

```python
from src.spider import spider
from src.database import db_manager
from src.scheduler import scheduler

# 运行一次爬虫
result = spider.run(max_pages=5)
print(f"爬取了 {result['crawled_count']} 条新闻")

# 查询数据库
with db_manager:
    news_list = db_manager.find_news(limit=10)
    print(f"数据库中有 {len(news_list)} 条新闻")

# 添加定时任务
job_id = scheduler.add_interval_job(minutes=30)
scheduler.start()
```

## 配置说明

### 主要配置项

在 `config/config.py` 中可以修改以下配置：

- **MongoDB配置**: 数据库连接信息
- **爬虫配置**: 请求超时、重试次数、User-Agent等
- **调度器配置**: 执行间隔、最大工作线程数、时区
- **日志配置**: 日志级别、文件路径、轮转设置

### 环境变量

支持通过 `.env` 文件或系统环境变量进行配置：

```bash
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DATABASE=thunderstorm-news
SCHEDULER_INTERVAL_MINUTES=30
LOG_LEVEL=INFO
```

## 数据结构

爬取的新闻数据包含以下字段：

```json
{
  "title": "新闻标题",
  "url": "新闻链接",
  "summary": "新闻摘要",
  "content": "新闻正文",
  "author": "作者",
  "category": "分类",
  "tags": ["标签1", "标签2"],
  "image_url": "图片链接",
  "publish_time": "发布时间",
  "created_at": "创建时间",
  "updated_at": "更新时间"
}
```

## 日志系统

项目使用分层日志系统：

- `logs/spider.log`: 主日志文件
- `logs/error.log`: 错误日志文件
- `logs/spider.log`: 爬虫模块日志
- `logs/database.log`: 数据库模块日志
- `logs/scheduler.log`: 调度器模块日志

日志文件支持自动轮转，默认单文件最大10MB，保留5个备份文件。

## 监控和维护

### 查看运行状态

```bash
# 查看系统状态
python main.py status

# 查看日志
tail -f logs/spider.log

# 查看错误日志
tail -f logs/error.log
```

### 数据库操作

```python
from src.database import db_manager

# 连接数据库
with db_manager:
    # 查询新闻总数
    total = db_manager.count_news()
    
    # 查询最近的新闻
    recent_news = db_manager.find_news(limit=10)
    
    # 按条件查询
    news = db_manager.find_news({"category": "足球"}, limit=5)
    
    # 删除旧数据
    from datetime import datetime, timedelta
    old_date = datetime.now() - timedelta(days=30)
    db_manager.delete_news({"created_at": {"$lt": old_date}})
```

## 性能优化

- **请求频率控制**: 内置请求间隔，避免对目标网站造成压力
- **数据去重**: 使用URL作为唯一索引，自动过滤重复数据
- **批量插入**: 支持批量数据库操作，提高写入效率
- **连接池**: 使用连接池管理数据库连接
- **异常重试**: 自动重试失败的请求

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查MongoDB服务是否启动
   - 验证连接配置是否正确
   - 检查网络连接

2. **爬虫无法获取数据**
   - 检查目标网站是否可访问
   - 验证User-Agent和请求头设置
   - 查看是否被反爬虫机制阻止

3. **定时任务不执行**
   - 检查调度器是否正常启动
   - 验证时区设置
   - 查看任务配置是否正确

### 调试模式

```bash
# 设置调试级别日志
export LOG_LEVEL=DEBUG
python main.py run

# 或在代码中设置
from src.logger import logger_manager
logger_manager.set_level('DEBUG')
```

## 开发指南

### 添加新的爬虫功能

1. 在 `src/spider.py` 中添加新的解析方法
2. 更新数据库模型（如需要）
3. 添加相应的测试
4. 更新配置文件

### 扩展调度器

```python
from src.scheduler import scheduler

# 添加自定义任务
def custom_task():
    print("执行自定义任务")

scheduler.add_interval_job(
    job_func=custom_task,
    minutes=10,
    job_id="custom_task"
)
```

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 GitHub Issue
- 发送邮件至项目维护者

---

**注意**: 请遵守目标网站的robots.txt文件和使用条款，合理使用爬虫功能。
