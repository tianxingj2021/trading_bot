import os
from loguru import logger

# 确保logs文件夹存在
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# 配置日志输出
logger.add(
    os.path.join(logs_dir, "more_{time}.log"),  # 日志文件路径
    rotation="1 day",        # 每天轮换一次
    retention="7 days",      # 保留7天的日志
    level="INFO",           # 日志级别
    encoding="utf-8",       # 编码
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"  # 日志格式
)
