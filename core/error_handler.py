"""
统一错误处理模块
提供友好的错误提示和异常处理装饰器
"""
import traceback
import logging
from functools import wraps
from typing import Callable, Any, Optional
from enum import Enum

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    DATA_LOAD_ERROR = "数据加载错误"
    DATA_QUALITY_ERROR = "数据质量错误"
    CALCULATION_ERROR = "计算错误"
    NETWORK_ERROR = "网络错误"
    CONFIG_ERROR = "配置错误"
    USER_ERROR = "用户输入错误"
    SYSTEM_ERROR = "系统错误"


class DashboardError(Exception):
    """Dashboard自定义异常基类"""
    def __init__(self, message: str, error_type: ErrorType = ErrorType.SYSTEM_ERROR, 
                 user_message: Optional[str] = None, details: Optional[str] = None):
        self.message = message
        self.error_type = error_type
        self.user_message = user_message or message
        self.details = details
        super().__init__(self.message)


def handle_error(func: Callable) -> Callable:
    """错误处理装饰器，自动捕获异常并记录日志"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DashboardError as e:
            logger.error(f"{e.error_type.value}: {e.message}", exc_info=True)
            if e.details:
                logger.debug(f"详细信息: {e.details}")
            return None
        except Exception as e:
            error_msg = f"发生未预期的错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None
    return wrapper


def safe_execute(func: Callable, default_return: Any = None, 
                 error_message: Optional[str] = None) -> Any:
    """安全执行函数，出错时返回默认值"""
    try:
        return func()
    except Exception as e:
        if error_message:
            logger.warning(f"{error_message}: {str(e)}")
        else:
            logger.warning(f"安全执行失败: {str(e)}", exc_info=True)
        return default_return


def create_data_error(ticker: str, reason: str) -> DashboardError:
    """创建数据加载错误"""
    return DashboardError(
        message=f"无法加载 {ticker} 的数据: {reason}",
        error_type=ErrorType.DATA_LOAD_ERROR,
        user_message=f"资产 {ticker} 的数据加载失败，请检查资产代码是否正确或数据源是否可用。",
        details=reason
    )


def create_quality_error(ticker: str, issue: str) -> DashboardError:
    """创建数据质量错误"""
    return DashboardError(
        message=f"{ticker} 数据质量问题: {issue}",
        error_type=ErrorType.DATA_QUALITY_ERROR,
        user_message=f"资产 {ticker} 的数据存在质量问题: {issue}",
        details=issue
    )


def create_network_error(data_source: str, reason: str) -> DashboardError:
    """创建网络错误"""
    return DashboardError(
        message=f"数据源 {data_source} 网络错误: {reason}",
        error_type=ErrorType.NETWORK_ERROR,
        user_message=f"无法连接到数据源 {data_source}，请检查网络连接或稍后重试。",
        details=reason
    )
