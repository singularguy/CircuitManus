# IDT_AGENT_NATIVE/circuitmanus/utils/logging_config.py
import os
import sys
import logging
from datetime import datetime
from typing import Optional # 导入 Optional
import traceback

LOG_DIR = "WebUIAgentLogs"  # 默认日志目录，可以被覆盖
console_handler: Optional[logging.StreamHandler] = None # 类型提示
file_handler: Optional[logging.FileHandler] = None    # 类型提示

def setup_logging(
    console_log_level: int = logging.INFO, 
    file_log_level: int = logging.DEBUG, 
    log_dir_override: Optional[str] = None,
    # verbose_mode is effectively replaced by direct console_log_level setting
    # but we keep it for now if Agent's self.verbose_mode directly maps to DEBUG for console
    # For a cleaner approach, Agent should pass the resolved console_log_level directly.
    # Let's assume Agent will pass the desired console_log_level.
    # If verbose_mode is still used by Agent to mean "console=DEBUG", Agent __init__ should resolve it.
) -> logging.Logger:
    """
    Configures the root logger and a specific logger for the application.
    Now accepts explicit console and file log levels, and a log directory override.

    Args:
        console_log_level (int): The logging level for the console.
        file_log_level (int): The logging level for the file.
        log_dir_override (Optional[str]): If provided, overrides the default LOG_DIR.

    Returns:
        logging.Logger: The configured logger instance for the 'circuitmanus' application.
    """
    global console_handler, file_handler, LOG_DIR # 声明我们要修改全局变量

    # 如果提供了 log_dir_override，则使用它
    if log_dir_override:
        current_log_dir = log_dir_override
    else:
        current_log_dir = LOG_DIR # 使用模块级默认值

    try:
        if not os.path.exists(current_log_dir):
            os.makedirs(current_log_dir)
    except OSError as e:
        sys.stderr.write(f"严重错误: 无法创建日志目录 '{current_log_dir}'. 错误信息: {e}\n")
        sys.stderr.write("文件日志功能可能不可用。程序将仅使用控制台日志继续运行。\n")

    current_time_for_log = datetime.now()
    log_file_name = os.path.join(
        current_log_dir, # 使用 current_log_dir
        f"agent_log_v1_1_3_async_call_fix_{current_time_for_log.strftime('%Y%m%d_%H%M%S')}_{current_time_for_log.microsecond // 1000:03d}_P{os.getpid()}.log"
    )

    log_format = '%(asctime)s - %(name)s - %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger() # 获取根 logger
    
    # --- 控制台日志处理器 ---
    # 清理可能存在的旧的同名控制台处理器
    if console_handler and console_handler in root_logger.handlers:
        root_logger.removeHandler(console_handler)
        console_handler.close() # 关闭旧的处理器
        console_handler = None
    
    # 创建新的控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(console_log_level) # 直接使用传入的级别
    root_logger.addHandler(console_handler)

    # --- 文件日志处理器 ---
    # 清理可能存在的旧的文件处理器
    if file_handler and file_handler in root_logger.handlers:
        root_logger.removeHandler(file_handler)
        file_handler.close()
        file_handler = None
        
    try:
        file_handler = logging.FileHandler(log_file_name, mode='a', encoding='utf-8')
        file_handler.setLevel(file_log_level) # 直接使用传入的级别
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # 如果文件日志配置失败，通过控制台日志报告错误
        # 创建一个临时logger或直接使用print，因为标准logger可能还未完全配置好
        sys.stderr.write(f"严重错误(setup_logging): 配置日志文件到 '{log_file_name}' 失败。错误信息: {e}\nTraceback: {traceback.format_exc()}\n")
        sys.stderr.write("Agent 将仅使用控制台日志继续运行。\n")
        file_handler = None # 确保 file_handler 为 None

    # 设置根日志级别为所有处理器中最低的级别，以确保消息能被考虑
    # (DEBUG is 10, INFO is 20, etc.)
    effective_root_level = min(console_log_level, file_log_level)
    # 如果 file_handler 失败了，则根级别只考虑 console
    if file_handler is None:
        effective_root_level = console_log_level
        
    root_logger.setLevel(effective_root_level)

    # 获取一个特定的 logger 实例供应用主模块使用
    app_logger = logging.getLogger("circuitmanus") 
    
    # 抑制第三方库的冗余日志 (保持不变)
    logging.getLogger("zhipuai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)

    # 最终确认日志配置状态
    if file_handler:
        app_logger.info(f"文件日志配置成功。级别: {logging.getLevelName(file_handler.level)}, 文件: {os.path.abspath(log_file_name)}")
    else:
        app_logger.warning("文件日志未配置成功。")
    app_logger.info(f"控制台日志配置成功。级别: {logging.getLevelName(console_handler.level)}")
    app_logger.info(f"Root logger 级别设置为: {logging.getLevelName(root_logger.level)}")
    
    return app_logger