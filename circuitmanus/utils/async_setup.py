# IDT_AGENT_Pro/circuitmanus/utils/async_setup.py
import asyncio
import logging

logger = logging.getLogger(__name__) # 使用当前模块的 logger

_initialized_loop = None # 模块级变量，存储我们设置的循环

def get_event_loop() -> asyncio.AbstractEventLoop:
    """
    Ensures an asyncio event loop is available and set for the current context.
    If a loop is already running, it returns that loop.
    Otherwise, it creates a new loop, sets it as the current loop for the main thread,
    and returns it.
    
    This function aims to provide a consistent way to get a loop,
    especially when the script might be run in different environments
    (e.g., as a standalone script vs. part of a larger asyncio application).
    """
    global _initialized_loop
    try:
        # 尝试获取当前正在运行的事件循环
        loop = asyncio.get_running_loop()
        logger.debug("get_event_loop: Found an already running event loop.")
        if _initialized_loop is None: # 如果是第一次在这个模块发现运行中的循环
            _initialized_loop = loop # 记录它
    except RuntimeError:  # 'RuntimeError: There is no current event loop...'
        logger.debug("get_event_loop: No running event loop found, creating a new one.")
        # 如果之前通过此函数创建并设置过循环，则尝试复用
        if _initialized_loop and not _initialized_loop.is_closed():
            loop = _initialized_loop
            logger.debug("get_event_loop: Reusing previously initialized loop.")
        else:
            loop = asyncio.new_event_loop()
            logger.debug("get_event_loop: New event loop created.")
            _initialized_loop = loop
        
        try:
            asyncio.set_event_loop(loop)
            logger.debug("get_event_loop: New event loop set as the current event loop for this thread.")
        except RuntimeError as e:
            # 这通常发生在非主线程尝试设置事件循环，而策略不允许时
            # 或者一个循环已经在其他地方被设置了
            logger.warning(f"get_event_loop: Could not set the event loop: {e}. This might be an issue if running in a non-main thread without a loop already set.")
            # 在这种情况下，我们仍然返回我们创建/获取的loop，调用者需要意识到它可能不是“当前”的
    
    return loop

# 在模块加载时，可以调用一次以确保主线程的事件循环被初始化
# loop = get_event_loop() # 同样，根据需要决定是否在导入时执行