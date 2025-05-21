# IDT_AGENT_Pro/server.py
import os
import uuid
import asyncio
import logging
import json # 用于处理WebSocket消息
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
# pydantic BaseModel 暂时没有直接使用，但保留以备将来可能的请求体模型
# from pydantic import BaseModel
from typing import Dict, Callable, Awaitable, Any, Optional, Union
import time
import traceback # 用于在错误处理中获取详细的 traceback 信息
# --- 核心 Agent 导入 ---
# 从重构后的 circuitmanus 包导入核心类和可能的共享资源
try:
    from circuitmanus.agent import CircuitAgent
    # 尝试从 utils.logging_config 导入 console_handler，如果 server 想控制其级别
    # 注意：Agent 初始化时会调用 setup_logging，通常 server.py 不需要再次配置日志，
    # 除非有特殊需求。如果 Agent 的日志配置已足够，这里可以不导入 console_handler。
    # from circuitmanus.utils.logging_config import console_handler as agent_console_handler
    AGENT_AVAILABLE = True # 标记Agent是否成功导入
    # server.py 应该使用自己的 logger，而不是直接修改 Agent 内部的 logger
    # Agent 的 logger 由其内部的 setup_logging 配置
    logger = logging.getLogger("server") # 为 server.py 创建一个独立的 logger
    # 如果希望 server logger 也遵循与 Agent 相同的格式和级别，
    # 可以在 Agent 初始化后，获取其 logger 的配置并应用，或者在顶层统一配置。
    # 为简单起见，这里 server logger 将使用 FastAPI/Uvicorn 默认的日志配置，
    # Agent 的日志会由其自身管理并输出到控制台和文件。
    logger.info("CircuitAgent 模块从 'circuitmanus.agent' 导入成功.")
except ImportError as e:
    logger = logging.getLogger("server_fallback") # 确保 logger 已初始化
    logger.critical(f"严重错误: 无法导入 Agent 类 'CircuitAgent' 从 'circuitmanus.agent'. 错误信息: {e}", exc_info=True)
    AGENT_AVAILABLE = False
    # 定义一个假的 CircuitAgent 类，以便在核心代码不可用时服务器仍能启动并给出错误提示
    class CircuitAgent: # pylint: disable=invalid-name
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            logger.warning("Agent核心代码不可用,使用假的CircuitAgent实例 (server.py fallback).")
            self.verbose_mode = kwargs.get('verbose', False) # 模拟 verbose_mode
            self.current_request_id: str | None = None # 模拟属性

        async def process_user_request(self, user_request: str, status_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
            # V1.0.0 - Fake agent error message, 保持与原版一致
            error_msg_content = "错误: 后端Agent核心模块未能加载,无法处理您的请求. 请联系管理员检查服务器日志 (V1.0.0-Reasoning Fallback). "
            logger.error("假的Agent (server.py fallback): 收到请求,返回错误信息.")
            if status_callback:
                 # 这个 thinking detail 是为了日志，不是给用户的
                 # 为了与真实 Agent 的回调格式保持某种程度的一致性，发送一个类似的状态
                 # 确保发送的字典键与前端期望的一致
                 request_id_fallback = f"fallback_req_{str(uuid.uuid4())[:6]}"
                 llm_interaction_id_fallback = f"fallback_llm_interaction_id_{str(uuid.uuid4())[:6]}"
                 
                 await status_callback({
                     "type": "general_status", # 使用 'general_status' 兼容真实 Agent 回调
                     "request_id": request_id_fallback,
                     "stage": "fatal_error_handler", # 模拟一个错误阶段
                     "status": "error", 
                     "message": "Agent核心模块未加载,无法提供服务.",
                     "details": {"error_type": "AGENT_UNAVAILABLE", "technicalMessage": "Agent core module CircuitManusCore or circuitmanus.agent failed to load."}
                    })
                 await status_callback({
                     "type": "thinking_log", # 模拟一个 thinking_log
                     "request_id": request_id_fallback,
                     "llm_interaction_id": llm_interaction_id_fallback,
                     "stage": "error_synthesis",
                     "content": "Agent核心代码未加载 (V1.0.0 Fallback). 无法处理请求。"
                    })
                 await status_callback({
                     "type": "final_response", 
                     "request_id": request_id_fallback,
                     "llm_interaction_id": llm_interaction_id_fallback,
                     "content": error_msg_content,
                     "final_json_if_success": None # 明确没有成功的JSON
                    })

# --- FastAPI 应用实例 ---
# 更新应用标题和版本以反映重构
app = FastAPI(title="CircuitManus Agent API - V1.0.0 (Refactored)", version="1.3.0_refactored")

# --- 挂载静态文件目录 ---
# 确保 'static' 目录与 server.py 在同一级别或正确配置路径
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.isdir(STATIC_DIR):
    # 如果 server.py 在项目根目录，而 static 在项目根目录的 static/ 下
    # 那么 os.path.dirname(__file__) 就是项目根目录
    # 如果 server.py 在某个子目录，需要调整
    logger.warning(f"默认静态文件目录 '{STATIC_DIR}' 未找到。尝试上一级目录的 'static'...")
    alt_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.isdir(alt_static_dir):
        STATIC_DIR = alt_static_dir
        logger.info(f"使用备用静态文件目录: {STATIC_DIR}")
    else:
        logger.error(f"静态文件目录 'static' 在 {STATIC_DIR} 或 {alt_static_dir} 均未找到。Web UI可能无法加载。")
        # 即使目录不存在，也尝试挂载，FastAPI会在请求时报错
try:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"静态文件目录 '{STATIC_DIR}' 已尝试挂载到 '/static'.")
except RuntimeError as e:
    # 这通常在目录不存在或不是目录时发生
    logger.error(f"挂载静态文件目录 '{STATIC_DIR}' 失败: {e}. 请确保 'static' 目录存在于正确的位置.", exc_info=True)


# --- Agent 实例和会话管理 ---
agent_sessions: Dict[str, CircuitAgent] = {} # 存储每个会话ID对应的Agent实例
agent_locks: Dict[str, asyncio.Lock] = {}   # 存储每个会话ID对应的锁，确保串行处理请求
active_websockets: Dict[str, WebSocket] = {} # 存储每个会话ID对应的活动WebSocket连接

# --- 获取 API Key ---
# ZHIPUAI_API_KEY 是Agent初始化的关键依赖
API_KEY = os.environ.get("ZHIPUAI_API_KEY")
if not API_KEY:
    logger.critical("严重警告: 环境变量 ZHIPUAI_API_KEY 未设置！如果Agent核心需要此Key, 其功能将受限或失败.")
else:
    logger.info("成功获取 ZHIPUAI_API_KEY 环境变量 (其使用由Agent核心决定).")


# 函数: 根据会话 ID 获取或创建 Agent 实例
async def get_agent_instance(session_id: str) -> CircuitAgent:
    """
    根据会话 ID 获取或创建 Agent 实例。
    现在调用 Agent 的构造函数时，传递配置文件路径。
    """
    if session_id not in agent_sessions:
        logger.info(f"为 Session {session_id} 创建新的 Agent 实例 (V1.0.0 Refactored & Configurable)...")
        if AGENT_AVAILABLE: # 检查 Agent 核心代码是否可用
            try:
                # CircuitAgent 的构造函数现在期望配置文件路径
                # .env 文件路径可以不传，ConfigLoader 会尝试默认位置
                # API_KEY 和 verbose_mode 会由 Agent 内部的 ConfigLoader 处理
                
                # 确定配置文件的路径，通常相对于项目根目录
                # 假设 server.py 在项目根目录，config.yaml 也在项目根目录
                config_yaml_file_path = "config.yaml" 
                # .env 文件路径，如果想明确指定，否则 ConfigLoader 会自己找
                # dotenv_file_path = ".env" 
                dotenv_file_path = None # 让 ConfigLoader 默认查找

                # 实例化 Agent，传递配置文件路径
                new_agent = CircuitAgent(
                    config_yaml_path=config_yaml_file_path,
                    dotenv_path=dotenv_file_path
                )
                
                agent_sessions[session_id] = new_agent
                agent_locks[session_id] = asyncio.Lock() 
                logger.info(f"Agent 实例为 Session {session_id} 创建成功 (V1.0.0 Refactored & Configurable).")
            except ValueError as ve: # 例如 API Key 未找到时 Agent __init__ 抛出的 ValueError
                logger.error(f"创建真实的 Agent 实例因配置问题失败 (Session {session_id}): {ve}", exc_info=True)
                raise RuntimeError(f"无法为会话 {session_id} 创建真实的 Agent 实例: {ve}") from ve
            except Exception as e: # 其他可能的初始化错误
                logger.error(f"创建真实的 Agent 实例发生未知错误 (Session {session_id}): {e}", exc_info=True)
                raise RuntimeError(f"无法为会话 {session_id} 创建真实的 Agent 实例: {e}") from e
        # AGENT_AVAILABLE is False 的情况保持不变
        else: 
             logger.warning(f"Agent 核心代码不可用,为 Session {session_id} 创建了一个假的 Agent 实例 (get_agent_instance).")
             agent_sessions[session_id] = CircuitAgent(config_yaml_path="dummy_config.yaml") # 假Agent也需要匹配签名
             agent_locks[session_id] = asyncio.Lock()
    return agent_sessions[session_id]

# 函数: 获取会话对应的锁
async def get_session_lock(session_id: str) -> asyncio.Lock:
    """获取会话对应的锁。如果锁不存在则为该会话创建新锁。"""
    if session_id not in agent_locks:
        # 这通常在 get_agent_instance 中与 agent_sessions 一起创建
        # 但作为防御性措施，如果直接调用且锁不存在，也创建它
        logger.debug(f"锁在 get_session_lock 中为 Session {session_id} 创建 (可能表示调用顺序问题)。")
        agent_locks[session_id] = asyncio.Lock()
    return agent_locks[session_id]

# --- 根路径,提供 HTML 界面 ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """提供 Web UI 的入口 HTML 文件 (通常是 static/index.html)。"""
    logger.info(f"收到对根路径 '/' 的请求 (来自: {request.client.host if request.client else '未知客户端'}). 尝试提供静态主页.")
    # STATIC_DIR 在文件顶部定义
    html_file_path = os.path.join(STATIC_DIR, "index.html")
    
    if not os.path.exists(html_file_path):
        logger.error(f"错误: 未在静态文件目录 '{STATIC_DIR}' 下找到 'index.html' 文件！")
        # 返回一个更友好的错误页面或消息
        error_content = """
        <html><head><title>Error</title></head><body>
        <h1>500 - Internal Server Error</h1>
        <p>The User Interface file (index.html) could not be found on the server.</p>
        <p>Please check server logs for the configured static directory path.</p>
        </body></html>
        """
        return HTMLResponse(content=error_content, status_code=500)
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"读取 index.html 文件 ('{html_file_path}') 时出错: {e}", exc_info=True)
        return HTMLResponse(content="<h1>500 - Internal Server Error: Error loading UI.</h1>", status_code=500)


# --- WebSocket 端点 ---
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket 端点，处理前端与 Agent 的实时双向通信。
    支持会话管理、消息处理和状态更新。
    """
    await websocket.accept()
    logger.info(f"WebSocket 连接已接受 (来自: {websocket.client.host if websocket.client else '未知客户端'}:{websocket.client.port if websocket.client else '未知端口'}).")
    
    session_id: Optional[str] = None # 当前WebSocket连接的会话ID
    agent_instance: Optional[CircuitAgent] = None # 当前会话的Agent实例

    try:
        # 定义一个闭包函数，用于将Agent的状态更新通过此WebSocket连接发送回客户端
        async def send_status_update_to_client(status_data: Dict[str, Any]) -> None:
            """将Agent的状态信息通过WebSocket发送给当前连接的前端。"""
            nonlocal session_id # 引用外部作用域的 session_id
            if websocket.client_state.name == "CONNECTED": # 确保连接仍然有效
                try:
                    # 日志记录发送给客户端的数据 (注意不要记录敏感信息，如果 status_data 可能包含的话)
                    log_preview = json.dumps(status_data, ensure_ascii=False)
                    logger.debug(f"SERVER SENDING TO CLIENT (Session {session_id or 'N/A'}, WS: {websocket.scope.get('path', '')}): {log_preview[:500]}{'...' if len(log_preview) > 500 else ''}")
                    await websocket.send_json(status_data)
                except WebSocketDisconnect: # 在尝试发送时发现连接已断开
                    logger.warning(f"尝试发送状态更新到 Session {session_id or 'N/A'} 时WebSocket已断开 (send_status_update).")
                    # 可以抛出一个自定义异常或 CancelledError 来终止 Agent 的处理
                    raise asyncio.CancelledError("WebSocket connection lost during status update.")
                except Exception as e_send_status:
                    logger.error(f"通过WebSocket发送状态更新失败 (Session {session_id or 'N/A'}): {e_send_status}", exc_info=True)
                    # 根据错误严重性，可能也需要终止处理
            else:
                logger.warning(f"尝试发送状态更新到 Session {session_id or 'N/A'} 但WebSocket状态为 {websocket.client_state.name}。")
        
        # WebSocket 消息处理循环
        while True:
            data = await websocket.receive_text() # 等待接收文本消息
            try:
                message = json.loads(data) # 解析JSON消息
                msg_type = message.get("type") # 获取消息类型

                if msg_type == "init": # 初始化消息
                    temp_session_id = message.get("session_id")
                    if not temp_session_id or not isinstance(temp_session_id, str) or not temp_session_id.strip():
                        session_id = str(uuid.uuid4()) # 如果前端未提供或提供无效ID，则生成新的
                        logger.info(f"收到WebSocket初始化消息,未提供有效session_id,生成新的: {session_id}")
                    else:
                        session_id = temp_session_id.strip()
                        logger.info(f"收到WebSocket初始化消息,使用提供的session_id: {session_id}")
                    
                    # 将此WebSocket连接与session_id关联
                    active_websockets[session_id] = websocket
                    
                    try:
                        # 获取或创建Agent实例
                        agent_instance = await get_agent_instance(session_id)
                        await websocket.send_json({
                            "type": "init_success",
                            "session_id": session_id,
                            "message": "WebSocket连接建立成功,Agent (V1.0.0 Refactored)已准备就绪.",
                            "agent_available": AGENT_AVAILABLE # 告知前端Agent核心是否可用
                        })
                        logger.info(f"Session {session_id} WebSocket初始化成功并发送确认.")
                    except Exception as e_init_agent: # Agent初始化失败 (例如API Key问题)
                         logger.error(f"Session {session_id} Agent初始化失败: {e_init_agent}", exc_info=True)
                         await websocket.send_json({
                             "type": "init_error",
                             "session_id": session_id, # 仍然返回session_id
                             "message": f"Agent初始化失败: {str(e_init_agent)}",
                             "agent_available": AGENT_AVAILABLE # 可能仍然是True，但特定实例创建失败
                         })
                         # Agent 初始化失败是严重问题，应关闭连接
                         await websocket.close(code=1011) # 1011: Server error
                         break # 跳出消息接收循环

                elif msg_type == "message" and session_id and agent_instance: # 用户发送的聊天消息
                    user_message_content = message.get("content")
                    if not user_message_content or not isinstance(user_message_content, str) or not user_message_content.strip():
                         logger.warning(f"Session {session_id} 收到空消息内容或非字符串内容.")
                         # 回复一个错误或忽略
                         await send_status_update_to_client({"type": "error", "message": "收到空消息或无效消息内容,已忽略.", "request_id": agent_instance.current_request_id or f"err_req_{str(uuid.uuid4())[:6]}"})
                         continue

                    logger.info(f"Session {session_id} 收到用户消息: '{user_message_content[:100]}{'...' if len(user_message_content)>100 else ''}'")
                    
                    lock = await get_session_lock(session_id) # 获取此会话的锁
                    async with lock: # 确保同一会话的请求被串行处理
                        logger.info(f"Session {session_id} 获取到锁,开始处理用户消息...")
                        start_time_process = time.monotonic()
                        try:
                            # 调用Agent的核心处理方法，并传入 send_status_update_to_client 作为回调
                            await agent_instance.process_user_request(
                                user_message_content, 
                                status_callback=send_status_update_to_client
                            )
                            duration_process = time.monotonic() - start_time_process
                            logger.info(f"Session {session_id} (ReqID: {agent_instance.current_request_id or 'N/A'}) 消息处理流程调用完成,耗时: {duration_process:.3f} 秒.")
                        except asyncio.CancelledError: # 如果在 process_user_request 中因为WebSocket断开而取消
                             logger.warning(f"Session {session_id} (ReqID: {agent_instance.current_request_id or 'N/A'}) Agent消息处理任务被取消 (可能由于WebSocket断开).")
                             # 不需要再发送消息，因为连接可能已断
                        except Exception as e_process: # Agent处理过程中发生未捕获的顶层错误
                            logger.error(f"Session {session_id} (ReqID: {agent_instance.current_request_id or 'N/A'}) Agent消息处理时发生内部顶层错误: {e_process}", exc_info=True)
                            error_details_str = str(e_process)
                            # 尝试通过回调发送错误状态
                            # 需要确保 current_request_id 是最新的
                            current_req_id_for_error = agent_instance.current_request_id if agent_instance and agent_instance.current_request_id else f"error_req_{str(uuid.uuid4())[:6]}"
                            try:
                                await send_status_update_to_client({
                                    "type": "general_status", 
                                    "request_id": current_req_id_for_error,
                                    "stage": "fatal_processing_error", 
                                    "status": "error", 
                                    "message": "处理您的消息时服务器内部发生了严重错误.", 
                                    "details": {"error_type": type(e_process).__name__, "error_message": error_details_str}
                                })
                                await send_status_update_to_client({
                                    "type": "final_response", 
                                    "request_id": current_req_id_for_error,
                                    "llm_interaction_id": f"fatal_err_llm_id_{str(uuid.uuid4())[:6]}",
                                    "content": f"抱歉,处理您的消息时服务器内部发生了严重错误: {error_details_str[:100]}...",
                                    "final_json_if_success": None
                                })
                            except asyncio.CancelledError: # 回调发送时连接断开
                                logger.warning(f"Session {session_id} 发送顶层处理错误回调时WebSocket已断开。")
                            except Exception as e_send_fatal:
                                logger.error(f"Session {session_id} 发送顶层处理错误回调本身失败: {e_send_fatal}")
                        finally:
                             logger.info(f"Session {session_id} (ReqID: {agent_instance.current_request_id if agent_instance else 'N/A'}) 处理完毕,释放锁.")
                
                elif not session_id or not agent_instance: # 收到消息但会话未初始化
                    logger.warning(f"收到消息 (type: {msg_type}) 但 session_id ('{session_id}') 或 agent_instance ({'存在' if agent_instance else '不存在'}) 未完全初始化。忽略。")
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_json({"type": "error", "message": "会话未初始化或Agent实例创建失败,请先发送有效的 'init' 消息."})

                elif msg_type: # 收到其他未知类型的消息
                    logger.warning(f"Session {session_id or '未知'} 收到未知消息类型: '{msg_type}'. 消息内容(部分): {data[:100]}")
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_json({"type": "error", "message": f"服务器收到未知消息类型: '{msg_type}'"})
                
                # else: msg_type is None or empty, json.loads 成功但没有 type 字段

            except json.JSONDecodeError: # 接收到的不是有效的JSON文本
                logger.warning(f"Session {session_id or '未知'} 收到非JSON格式或无效JSON消息: {data[:100]}...")
                if websocket.client_state.name == "CONNECTED":
                    try: 
                        await websocket.send_json({"type": "error", "message": "服务器收到无效消息格式,请发送JSON.", "details": f"原始消息(部分): {data[:100]}"})
                    except WebSocketDisconnect: pass # 如果此时连接也断了，忽略
            except WebSocketDisconnect: # 在 await websocket.receive_text() 时连接断开
                 logger.info(f"Session {session_id or '未知'} WebSocket连接已断开 (在主接收循环中).")
                 break # 跳出消息接收循环
            except asyncio.CancelledError: # 如果此任务被外部取消
                 logger.info(f"Session {session_id or '未知'} WebSocket消息处理任务被取消。")
                 break
            except Exception as e_loop: # 捕获消息处理循环中的其他所有未预期错误
                logger.error(f"Session {session_id or '未知'} 在消息接收/处理循环中发生未预期错误: {e_loop}", exc_info=True)
                if websocket.client_state.name == "CONNECTED":
                    try:
                        # 发送一个通用的服务器错误消息
                        await websocket.send_json({"type": "error", "message": f"服务器内部错误: {str(e_loop)[:100]}...", "details": "详细错误已记录在服务器日志中。"})
                        # 发生严重错误后，主动关闭连接可能更安全
                        await websocket.close(code=1011) # 1011: Internal Server Error
                    except Exception: pass # 忽略关闭连接时的任何错误
                break # 跳出消息接收循环

    except WebSocketDisconnect as e_ws_disconnect: # WebSocket连接在外部循环（例如accept后，循环前）断开
        logger.info(f"Session {session_id or '未知'} WebSocket连接已断开 (在主 try 块捕获): code={e_ws_disconnect.code}, reason='{e_ws_disconnect.reason}'")
    except Exception as e_websocket_main: # WebSocket 端点主逻辑中的其他未预期异常
        logger.critical(f"Session {session_id or '未知'} WebSocket连接处理发生顶层未预期异常: {e_websocket_main}", exc_info=True)
        if websocket.client_state.name == "CONNECTED": # 如果连接仍然存在
            try: 
                await websocket.send_json({"type":"error", "message":"WebSocket服务器遇到严重内部错误，连接将关闭。"})
                await websocket.close(code=1011)
            except Exception: pass # 忽略关闭时的错误
    finally:
        # 清理会话相关的资源
        if session_id:
            if session_id in active_websockets:
                del active_websockets[session_id]
                logger.info(f"Session {session_id} 的WebSocket连接已从活动列表中移除.")
            # 考虑是否在此处清理 agent_sessions 和 agent_locks 中的条目
            # 如果希望会话状态在WebSocket重连后保留，则不应在此处删除
            # 如果每次WebSocket连接都是全新的会话（除非前端传递相同session_id），则可以考虑删除
            # 目前的 get_agent_instance 逻辑是如果session_id已存在，则复用，所以这里暂时不删除
            # if session_id in agent_sessions:
            #     del agent_sessions[session_id]
            #     logger.info(f"Session {session_id} 的Agent实例已从会话中移除.")
            # if session_id in agent_locks:
            #     del agent_locks[session_id]
            #     logger.info(f"Session {session_id} 的锁已从会话中移除.")
        
        client_addr = f"{websocket.client.host if websocket.client else '未知'}:{websocket.client.port if websocket.client else '未知'}"
        logger.info(f"Session {session_id or '未知'} WebSocket连接处理结束 (客户端: {client_addr}).")


# --- 用于直接运行服务器进行测试 ---
if __name__ == "__main__":
    import uvicorn
    # 配置顶层日志，确保 Uvicorn 和 FastAPI 的日志也能被捕获并格式化
    # 这部分可以根据需要调整，或者完全依赖 Uvicorn 的日志配置
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # 可以为 uvicorn 和 fastapi 的 logger 单独设置级别
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING) # access 日志通常很冗余
    logging.getLogger("fastapi").setLevel(logging.INFO)

    server_logger = logging.getLogger("server_main") # __main__ logger
    server_logger.info("直接运行 server.py, 启动 Uvicorn 开发服务器 (V1.0.0 Refactored)...")

    # 确保API_KEY已设置，否则真实Agent无法工作
    if not API_KEY and AGENT_AVAILABLE: # 如果Agent代码存在但Key缺失
        server_logger.critical("！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！")
        server_logger.critical("警告: ZHIPUAI_API_KEY 环境变量未设置，真实的 CircuitAgent 将无法初始化与LLM的连接！")
        server_logger.critical("服务器仍会启动，但Agent功能将依赖于其内部的API Key处理逻辑（可能失败）。")
        server_logger.critical("！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！")
    elif not AGENT_AVAILABLE:
        server_logger.warning("警告: Agent核心模块 (circuitmanus.agent) 未能加载。服务器将使用备用的假Agent。")


    uvicorn.run(
        "server:app", # 指向 FastAPI 应用实例 (文件名:app对象名)
        host="127.0.0.1",
        port=8000,
        reload=True, # 开发时启用自动重载
        log_level="debug" # Uvicorn 的日志级别，会影响其自身日志输出
                          # 注意：这与我们自己配置的 logger 级别是独立的，但都可能输出到控制台
    )