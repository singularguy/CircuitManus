# server.py
import os
import uuid
import asyncio
import logging
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict
import time

# 导入您的 Agent 核心代码文件中的 Agent 类
# 请确保文件名 'CircuitManusCore' 是正确的
try:
    from CircuitManusCore import CircuitDesignAgentV7, console_handler
    AGENT_AVAILABLE = True
except ImportError as e:
    print(f"错误: 无法导入 Agent 类，请确保 'CircuitManusCore.py' 文件存在且无误。错误信息: {e}")
    AGENT_AVAILABLE = False
    # 定义一个假的 Agent 类，以便服务器能启动，但功能受限
    class CircuitDesignAgentV7:
        def __init__(self, *args, **kwargs): pass
        async def process_user_request(self, msg): return "<think>Agent核心代码未加载</think>\n\n错误：无法处理请求。"

# --- 日志配置 (简化版，FastAPI/Uvicorn 会有自己的日志) ---
# 可以调整这里的级别来控制 FastAPI 部分的日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 如果 Agent 代码中的 console_handler 可用，可以设置其级别
if AGENT_AVAILABLE and 'console_handler' in globals():
    console_handler.setLevel(logging.INFO) # 服务器后台日志通常不需要 DEBUG 级别

# --- FastAPI 应用实例 ---
app = FastAPI(title="CircuitManus Agent API", version="1.0.0")

# --- 挂载静态文件目录 ---
# 确保 'static' 目录在 server.py 的同级目录下
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("静态文件目录 '/static' 挂载成功。")
except RuntimeError as e:
    logger.error(f"挂载静态文件目录 '/static' 失败: {e}. 请确保 'static' 目录存在于正确的位置。", exc_info=True)
    # 即使静态文件挂载失败，API 可能仍能工作，但无法提供 Web 界面

# --- Agent 实例和会话管理 ---
agent_sessions: Dict[str, CircuitDesignAgentV7] = {}
agent_locks: Dict[str, asyncio.Lock] = {}

# --- 获取 API Key ---
API_KEY = os.environ.get("ZHIPUAI_API_KEY")
if not API_KEY:
    logger.critical("错误: 环境变量 ZHIPUAI_API_KEY 未设置！后端服务无法启动。")
    # 在实际部署中可能需要更优雅的处理方式，这里直接退出以便于发现问题
    exit(1)
else:
    logger.info("成功获取 ZHIPUAI_API_KEY 环境变量。")

async def get_agent_instance(session_id: str) -> CircuitDesignAgentV7:
    """根据会话 ID 获取或创建 Agent 实例。"""
    if session_id not in agent_sessions:
        logger.info(f"为 Session {session_id} 创建新的 Agent 实例...")
        if AGENT_AVAILABLE:
            try:
                # 注意：这里的 verbose=True 指的是 Agent 内部日志的详细程度
                # Web UI 的简洁/详细可以通过前端控制是否显示 <think> 块
                new_agent = CircuitDesignAgentV7(api_key=API_KEY, verbose=True)
                agent_sessions[session_id] = new_agent
                agent_locks[session_id] = asyncio.Lock()
                logger.info(f"Agent 实例为 Session {session_id} 创建成功。")
            except Exception as e:
                logger.error(f"创建 Agent 实例失败 (Session {session_id}): {e}", exc_info=True)
                # 返回一个临时的、功能受限的实例或抛出错误
                # 为简单起见，我们让它在 API 端点中处理错误
                raise RuntimeError(f"无法为会话 {session_id} 创建 Agent 实例: {e}") from e
        else:
            # 如果 Agent 类导入失败，返回假的实例
            agent_sessions[session_id] = CircuitDesignAgentV7() # 假的实例
            agent_locks[session_id] = asyncio.Lock()
            logger.warning(f"Agent 核心代码不可用，为 Session {session_id} 创建了一个假的 Agent 实例。")

    return agent_sessions[session_id]

async def get_session_lock(session_id: str) -> asyncio.Lock:
    """获取会话对应的锁。"""
    if session_id not in agent_locks:
        # 如果锁不存在（可能 agent 实例也还不存在），先创建锁
        agent_locks[session_id] = asyncio.Lock()
    return agent_locks[session_id]

# --- API 请求模型 ---
class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None # 让前端可以传递会话 ID

# --- API 端点 ---
@app.post("/api/chat")
async def process_chat_message(payload: ChatMessage):
    """处理来自前端的聊天消息请求。"""
    session_id = payload.session_id
    user_message = payload.message
    request_id = str(uuid.uuid4())[:8] # 用于日志追踪

    logger.info(f"[Request:{request_id}] 收到消息。Session: {session_id or '新会话'}, Message: '{user_message[:50]}...'")

    if not AGENT_AVAILABLE:
        logger.error(f"[Request:{request_id}] Agent 核心代码未加载，无法处理请求。")
        return {"response": "<think>系统错误</think>\n\n错误：Agent核心代码未能加载，无法处理您的请求。", "session_id": session_id, "error": True}

    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"[Request:{request_id}] 未提供 session_id，生成新的: {session_id}")

    try:
        agent = await get_agent_instance(session_id)
        lock = await get_session_lock(session_id)
    except Exception as e_get_agent:
         logger.error(f"[Request:{request_id}] 获取或创建 Agent 实例失败 (Session: {session_id}): {e_get_agent}", exc_info=True)
         return {"response": f"<think>系统错误</think>\n\n错误：无法初始化处理会话 {session_id}。", "session_id": session_id, "error": True}


    async with lock: # 确保对同一个 session 的请求是串行的
        logger.info(f"[Request:{request_id}] 开始处理 Session {session_id} 的消息...")
        try:
            start_time = time.monotonic()
            agent_response = await agent.process_user_request(user_message)
            duration = time.monotonic() - start_time
            logger.info(f"[Request:{request_id}] Session {session_id} 消息处理完成，耗时: {duration:.3f} 秒。")
            return {"response": agent_response, "session_id": session_id, "error": False}
        except Exception as e:
            logger.error(f"[Request:{request_id}] 处理 Session {session_id} 消息时发生内部错误: {e}", exc_info=True)
            return {"response": f"<think>处理时发生内部错误: {e}</think>\n\n抱歉，处理您的消息时服务器内部发生了错误。", "session_id": session_id, "error": True}

# --- 根路径，提供 HTML 界面 ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """提供 Web UI 的入口 HTML 文件。"""
    logger.info("请求根路径 '/'，尝试提供 index.html。")
    # 确保 static/index.html 存在
    html_file_path = os.path.join("static", "index.html")
    if not os.path.exists(html_file_path):
        logger.error("错误: 未在 'static' 目录下找到 'index.html' 文件！")
        return HTMLResponse(content="<h1>错误: 无法加载界面文件 (index.html not found)</h1>", status_code=500)
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"读取 index.html 文件时出错: {e}", exc_info=True)
        return HTMLResponse(content="<h1>错误: 加载界面时出错</h1>", status_code=500)

# --- (可选) WebSocket 端点 (如果需要实时功能) ---
# 省略 WebSocket 实现，保持方案简洁

# --- 用于直接运行服务器进行测试 ---
if __name__ == "__main__":
    import uvicorn
    logger.info("直接运行 server.py，启动 Uvicorn 开发服务器...")
    # 运行在 0.0.0.0 上允许局域网访问，端口可自定义
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)