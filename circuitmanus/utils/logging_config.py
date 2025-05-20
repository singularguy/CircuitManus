# IDT_AGENT_Pro/circuitmanus/utils/logging_config.py
import os
import sys
import logging
from datetime import datetime

LOG_DIR = "WebUIAgentLogs"  # 日志文件存放的目录名
console_handler = None      # 全局控制台处理器引用，方便后续可能在其他地方调整级别
file_handler = None         # 全局文件处理器引用

def setup_logging(log_level: int = logging.DEBUG, verbose_mode: bool = True) -> logging.Logger:
    """
    Configures the root logger and a specific logger for the application.

    Args:
        log_level (int): The base logging level for file and console (if not overridden by verbose_mode).
        verbose_mode (bool): If True, console log level is set to DEBUG, otherwise to INFO.

    Returns:
        logging.Logger: The configured logger instance for the main application.
    """
    global console_handler, file_handler # 声明我们要修改全局变量

    try:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
    except OSError as e:
        # 即使创建目录失败，也应该尝试继续使用控制台日志
        sys.stderr.write(f"严重错误: 无法创建日志目录 '{LOG_DIR}'. 错误信息: {e}\n")
        sys.stderr.write("文件日志功能可能不可用。程序将仅使用控制台日志继续运行。\n")

    current_time_for_log = datetime.now()
    # 更新日志文件名以反映版本和更精确的时间，保持与原代码一致
    log_file_name = os.path.join(
        LOG_DIR,
        f"agent_log_v1_1_3_async_call_fix_{current_time_for_log.strftime('%Y%m%d_%H%M%S')}_{current_time_for_log.microsecond // 1000:03d}_P{os.getpid()}.log"
    )

    log_format = '%(asctime)s - %(name)s - %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
    formatter = logging.Formatter(log_format)

    # --- 控制台日志处理器 ---
    # 移除可能已存在的旧处理器，以避免重复添加
    root_logger = logging.getLogger()
    
    # 清理root logger中所有现有的StreamHandlers，以防重复配置
    # 特别是在被多次调用setup_logging的场景 (例如 server reload)
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr: # 特指我们之前加的
            root_logger.removeHandler(handler)
            if console_handler is handler: # 如果全局变量引用的是它
                console_handler = None
        # 也可以考虑移除已有的FileHandler，如果担心文件名冲突或重复日志
        # 但这里我们根据文件名是动态的，每次都是新的file_handler，所以主要关注StreamHandler

    if console_handler is None: # 确保只创建一个新的 console_handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    console_log_level_actual = logging.DEBUG if verbose_mode else logging.INFO
    console_handler.setLevel(console_log_level_actual)


    # --- 文件日志处理器 ---
    # 同样，如果file_handler已存在且指向同一个文件，理论上不应重复添加
    # 但由于log_file_name是动态的，每次调用setup_logging都会是一个新的文件处理器实例
    # 如果希望单个进程生命周期内只配置一次文件日志，可以添加类似 console_handler 的检查
    try:
        if file_handler: # 如果之前已经配置过一个file_handler
            root_logger.removeHandler(file_handler) # 先移除旧的
            file_handler.close()
            
        file_handler = logging.FileHandler(log_file_name, mode='a', encoding='utf-8')
        file_handler.setLevel(log_level) # 文件日志级别通常更详细
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # 如果文件日志配置失败，通过控制台日志（如果可用）报告错误
        # 使用 root_logger.name 来避免循环依赖于 __name__ 的 logger
        temp_logger_for_error = logging.getLogger(f"{root_logger.name}.logging_setup_error")
        if console_handler: # 确保控制台已经设置
            temp_logger_for_error.addHandler(console_handler)
            temp_logger_for_error.propagate = False # 不要让这个错误信息再次通过root logger传播
        
        temp_logger_for_error.error(f"严重错误: 配置日志文件到 '{log_file_name}' 失败。错误信息: {e}", exc_info=True)
        temp_logger_for_error.error("Agent 将仅使用控制台日志继续运行。")
        if file_handler: # 如果创建了但添加失败，尝试关闭
            file_handler = None


    # 设置根日志级别，确保所有处理器的消息都能被考虑
    # 通常设置为所有处理器中最低的级别
    root_logger.setLevel(min(console_log_level_actual, log_level))

    # 获取一个特定的 logger 实例供应用主模块使用
    # 这里的 __name__ 会是 "circuitmanus.utils.logging_config"
    # 通常我们希望返回一个通用的应用 logger
    app_logger = logging.getLogger("circuitmanus") # 或者用一个更通用的名字，如 "app"
    
    # 抑制第三方库的冗余日志
    logging.getLogger("zhipuai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)

    if file_handler:
        app_logger.info(f"文件日志配置成功。日志消息也将保存至: {os.path.abspath(log_file_name)}")
    app_logger.info(f"控制台日志级别设置为: {logging.getLevelName(console_handler.level)}")
    
    return app_logger

# 在模块加载时，可以进行一次默认的日志设置，
# 或者让调用者显式调用 setup_logging。
# 为了灵活性，让调用者显式调用更好。
# logger = setup_logging() # 如果想在导入时就配置，可以取消这行注释