import os
import uuid
import asyncio
import logging
import json # 导入json库,用于处理WebSocket消息
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException # 导入WebSocket相关类和HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel # 虽然换了WebSocket,但 BaseModel 可能用于内部结构或文档,保留
from typing import Dict, Callable, Awaitable # 导入类型提示 Callable 和 Awaitable
import time
import traceback # 用于在错误处理中获取详细的 traceback 信息

# 导入您的 Agent 核心代码文件中的 Agent 类
# 请确保文件名 'CircuitManusCore' 和类名 'CircuitAgent' 是正确的
try:
    from CircuitManusCore import CircuitAgent, console_handler # 导入Agent核心类和其内部的 console_handler
    AGENT_AVAILABLE = True # 标记Agent是否成功导入
    logger = logging.getLogger(__name__) # 获取当前模块的logger
    logger.info("CircuitAgent 模块导入成功. ")
except ImportError as e:
    logger = logging.getLogger(__name__) # 确保 logger 已初始化
    logger.critical(f"错误: 无法导入 Agent 类 'CircuitAgent' 从 'CircuitManusCore.py'. 错误信息: {e}", exc_info=True)
    AGENT_AVAILABLE = False
    class CircuitAgent: # pylint: disable=invalid-name
        def __init__(self, *args, **kwargs):
            logger.warning("Agent核心代码不可用,使用假的Agent实例. ")
            self.verbose_mode = kwargs.get('verbose', False)

        async def process_user_request(self, user_request: str, status_callback: Callable[[Dict], Awaitable[None]] = None) -> None:
            # V1.0.0 - Fake agent error message does not need <think> tags.
            error_msg_content = "错误: 后端Agent核心模块未能加载,无法处理您的请求. 请联系管理员检查服务器日志 (V1.0.0-Reasoning Fallback). "
            logger.error("假的Agent: 收到请求,返回错误信息. ")
            if status_callback:
                 # This thinking detail is for the process log, not part of the user-facing message.
                 await status_callback({"type": "status", "stage": "error", "status": "completed", "message": "Agent核心模块未加载. ", "details": {"thinking": "Agent核心代码未加载 (V1.0.0 Fallback)"}})
                 await status_callback({"type": "final_response", "content": error_msg_content})


# --- FastAPI 应用实例 ---
app = FastAPI(title="CircuitManus Agent API - V1.0.0 Reasoning", version="1.3.0") # V1.0.0 Version Update

# --- 挂载静态文件目录 ---
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("静态文件目录 '/static' 挂载成功. ")
except RuntimeError as e:
    logger.error(f"挂载静态文件目录 '/static' 失败: {e}. 请确保 'static' 目录存在于正确的位置. ", exc_info=True)


# --- Agent 实例和会话管理 ---
agent_sessions: Dict[str, CircuitAgent] = {}
agent_locks: Dict[str, asyncio.Lock] = {}
active_websockets: Dict[str, WebSocket] = {}

# --- 获取 API Key ---
API_KEY = os.environ.get("ZHIPUAI_API_KEY")
if not API_KEY:
    logger.critical("错误: 环境变量 ZHIPUAI_API_KEY 未设置！后端服务可能无法正常使用大语言模型功能. ")
else:
    logger.info("成功获取 ZHIPUAI_API_KEY 环境变量. ")


# 函数: 根据会话 ID 获取或创建 Agent 实例
async def get_agent_instance(session_id: str) -> CircuitAgent:
    """根据会话 ID 获取或创建 Agent 实例. """
    if session_id not in agent_sessions:
        logger.info(f"为 Session {session_id} 创建新的 Agent 实例 (V1.0.0 Reasoning Model)...")
        if AGENT_AVAILABLE:
            try:
                # Pass verbose=True for detailed logging from Agent to console/file
                # Agent __init__ now defaults to glm-z1-flash
                new_agent = CircuitAgent(api_key=API_KEY, verbose=True)
                agent_sessions[session_id] = new_agent
                agent_locks[session_id] = asyncio.Lock()
                logger.info(f"Agent 实例为 Session {session_id} 创建成功. ")
            except Exception as e:
                logger.error(f"创建 Agent 实例失败 (Session {session_id}): {e}", exc_info=True)
                raise RuntimeError(f"无法为会话 {session_id} 创建 Agent 实例: {e}") from e
        else:
             logger.warning(f"Agent 核心代码不可用,为 Session {session_id} 创建了一个假的 Agent 实例. ")
             agent_sessions[session_id] = CircuitAgent(api_key=API_KEY, verbose=True) # Fake agent
             agent_locks[session_id] = asyncio.Lock()
    return agent_sessions[session_id]

# 函数: 获取会话对应的锁
async def get_session_lock(session_id: str) -> asyncio.Lock:
    """获取会话对应的锁. 如果锁不存在则创建. """
    if session_id not in agent_locks:
        agent_locks[session_id] = asyncio.Lock()
        logger.debug(f"为 Session {session_id} 创建了新的锁. ")
    return agent_locks[session_id]

# --- 根路径,提供 HTML 界面 ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """提供 Web UI 的入口 HTML 文件. """
    logger.info("请求根路径 '/',尝试提供 static/index.html. ")
    html_file_path = os.path.join("static", "index.html")
    if not os.path.exists(html_file_path):
        logger.error("错误: 未在 'static' 目录下找到 'index.html' 文件！")
        return HTMLResponse(content="<h1>Internal Server Error: UI file not found.</h1>", status_code=500)
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"读取 index.html 文件时出错: {e}", exc_info=True)
        return HTMLResponse(content="<h1>Internal Server Error: Error loading UI.</h1>", status_code=500)


# --- WebSocket 端点 ---
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端点,处理前端与 Agent 的实时交互. 
    """
    await websocket.accept()
    logger.info(f"WebSocket 连接已接受 (来自: {websocket.client.host}:{websocket.client.port}).")
    session_id = None 
    agent_instance = None

    try:
        async def send_status_update_to_client(status_data: Dict):
            """将Agent的状态信息通过WebSocket发送给当前连接的前端. """
            nonlocal session_id
            try:
                logger.debug(f"SERVER SENDING TO CLIENT (Session {session_id if session_id else 'N/A'}): {json.dumps(status_data)}")
                await websocket.send_json(status_data)
            except WebSocketDisconnect:
                logger.warning(f"尝试发送状态更新到 Session {session_id} 时WebSocket已断开. ")
                raise asyncio.CancelledError("WebSocket connection lost during status update.")
            except Exception as e_send_status:
                logger.error(f"通过WebSocket发送状态更新失败 (Session {session_id}): {e_send_status}", exc_info=True)
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "init":
                    temp_session_id = message.get("session_id")
                    if not temp_session_id:
                        session_id = str(uuid.uuid4())
                        logger.info(f"收到WebSocket初始化消息,未提供session_id,生成新的: {session_id}")
                    else:
                        session_id = temp_session_id
                        logger.info(f"收到WebSocket初始化消息,使用提供的session_id: {session_id}")
                    
                    active_websockets[session_id] = websocket
                    
                    try:
                        agent_instance = await get_agent_instance(session_id)
                        await websocket.send_json({
                            "type": "init_success",
                            "session_id": session_id,
                            "message": "WebSocket连接建立成功,Agent (V1.0.0 Reasoning Model)已准备就绪. ", # V1.0.0 Version Update
                            "agent_available": AGENT_AVAILABLE
                        })
                        logger.info(f"Session {session_id} WebSocket初始化成功并发送确认. ")
                    except Exception as e_init_agent:
                         logger.error(f"Session {session_id} Agent初始化失败: {e_init_agent}", exc_info=True)
                         await websocket.send_json({
                             "type": "init_error",
                             "session_id": session_id,
                             "message": f"Agent初始化失败: {str(e_init_agent)}",
                             "agent_available": AGENT_AVAILABLE
                         })
                         await websocket.close(code=1011)
                         break

                elif msg_type == "message" and session_id and agent_instance:
                    user_message_content = message.get("content")
                    if not user_message_content:
                         logger.warning(f"Session {session_id} 收到空消息内容. ")
                         await send_status_update_to_client({"type": "status", "stage": "user_input", "status": "ignored", "message": "收到空消息,已忽略. "})
                         continue

                    logger.info(f"Session {session_id} 收到用户消息: '{user_message_content[:50]}...'")
                    
                    lock = await get_session_lock(session_id)
                    async with lock:
                        logger.info(f"Session {session_id} 获取到锁,开始处理消息...")
                        start_time = time.monotonic()
                        try:
                            await agent_instance.process_user_request(user_message_content, status_callback=send_status_update_to_client)
                            duration = time.monotonic() - start_time
                            logger.info(f"Session {session_id} 消息处理流程调用完成,耗时: {duration:.3f} 秒. ")
                        except asyncio.CancelledError:
                             logger.warning(f"Session {session_id} Agent消息处理任务被取消. ")
                        except Exception as e_process:
                            logger.error(f"Session {session_id} 消息处理时发生内部顶层错误: {e_process}", exc_info=True)
                            error_details_str = str(e_process)
                            await send_status_update_to_client({"type": "status", "stage": "processing", "status": "error", "message": "处理过程中发生未预期错误. ", "details": {"error_type": type(e_process).__name__, "error_message": error_details_str, "thinking": f"处理消息时发生错误: {error_details_str}"}})
                            final_err_content_process = f"抱歉,处理您的消息时服务器内部发生了错误. "
                            await send_status_update_to_client({"type": "final_response", "content": final_err_content_process})
                        finally:
                             logger.info(f"Session {session_id} 释放锁. ")
                elif not session_id or not agent_instance:
                    logger.warning(f"收到消息 (type: {msg_type}) 但 session_id 或 agent_instance 未初始化. 忽略. ")
                    await websocket.send_json({"type": "error", "message": "会话未初始化,请先发送 'init' 消息. "})

                elif msg_type:
                    logger.warning(f"Session {session_id} 收到未知消息类型: {msg_type}")
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_json({"type": "error", "message": f"服务器收到未知消息类型: {msg_type}"})

            except json.JSONDecodeError:
                logger.warning(f"Session {session_id or '未知'} 收到非JSON格式或无效JSON消息: {data[:100]}...")
                if session_id and websocket.client_state.name == "CONNECTED":
                    try: await websocket.send_json({"type": "error", "message": "服务器收到无效消息格式,请发送JSON. ", "details": data[:100]})
                    except WebSocketDisconnect: pass
            except WebSocketDisconnect:
                 logger.info(f"Session {session_id or '未知'} WebSocket连接已断开 (在接收消息时). ")
                 break
            except Exception as e_loop:
                logger.error(f"Session {session_id or '未知'} 在消息接收循环中发生未预期错误: {e_loop}", exc_info=True)
                if websocket.client_state.name == "CONNECTED":
                    try:
                        await websocket.send_json({"type": "error", "message": f"服务器内部错误: {str(e_loop)}", "details": traceback.format_exc()})
                        await websocket.close(code=1011)
                    except Exception: pass
                break
    except WebSocketDisconnect as e_ws_disconnect:
        logger.info(f"Session {session_id or '未知'} WebSocket连接已断开 (在外部捕获): code={e_ws_disconnect.code}, reason='{e_ws_disconnect.reason}'")
    except Exception as e_websocket_main:
        logger.critical(f"Session {session_id or '未知'} WebSocket连接处理发生顶层未预期异常: {e_websocket_main}", exc_info=True)
        if websocket.client_state.name == "CONNECTED":
            try: await websocket.close(code=1011)
            except Exception: pass
    finally:
        if session_id and session_id in active_websockets:
            del active_websockets[session_id]
            logger.info(f"Session {session_id} 的WebSocket连接已从活动列表中移除. ")
        logger.info(f"Session {session_id or '未知'} WebSocket连接处理结束 (客户端: {websocket.client.host}:{websocket.client.port}).")


# --- 用于直接运行服务器进行测试 ---
if __name__ == "__main__":
    import uvicorn
    logger.info("直接运行 server.py,启动 Uvicorn 开发服务器 (V1.0.0 Reasoning)...") # V1.0.0 Version Update

    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="debug"
    )
