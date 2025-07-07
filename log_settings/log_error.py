import os
from log_settings.log import logger
import logging

# 确保logs文件夹存在
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# 设置 logging 配置
logging.basicConfig(
    filename=os.path.join(logs_dir, 'error_log.txt'),  # 错误日志文件路径
    level=logging.ERROR,  # 设置日志级别
    format='%(asctime)s - %(levelname)s - %(message)s',  # 日志格式
    encoding='utf-8'  # 强制使用 UTF-8 编码
)

logger = logging.getLogger()

class GasFeeError(Exception):
    """表示燃料费用不足的错误类型"""
    pass

def log_error(profile, error_message):
    """储存错误信息到日志文件中"""
    logger.error(f"处理用户 {profile['name']} 时发生下列错误: {error_message}")

