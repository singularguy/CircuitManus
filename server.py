# IDT_AGENT_Pro/server.py
import os
import uuid
import asyncio
import logging
import json 
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Callable, Awaitable, Any, Optional, Union
import time
import traceback 

try:
    from circuitmanus.agent import CircuitAgent
    AGENT_AVAILABLE = True 
    logger = logging.getLogger("server") 
    logger.info("CircuitAgent 模块从 'circuitmanus.agent' 导入成功.")
except ImportError as e:
    logger = logging.getLogger("server_fallback") 
    logger.critical(f"严重错误: 无法导入 Agent 类 'CircuitAgent' 从 'circuitmanus.agent'. 错误信息: {e}", exc_info=True)
    AGENT_AVAILABLE = False
    class CircuitAgent: 
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            logger.warning("Agent核心代码不可用,使用假的CircuitAgent实例 (server.py fallback).")
            self.verbose_mode = kwargs.get('verbose', False) 
            self.current_request_id: str | None = None 
            class FakeConfigLoader:
                def get_config(self, key, default): return default
                def get_env_var(self, key, default=None): return default if key != "ZHIPUAI_API_KEY" else "fake_key_for_init_pass"
            self.config_loader = FakeConfigLoader()
            self.default_llm_identifier = "zhipu-ai"
            self.default_enable_chinese_thinking = False
            # 【新增】为假的Agent也模拟 model_availability_details
            self.model_availability_details = [
                {"id": "zhipu-ai", "name": "智谱清言 (GLM) - Fallback", "available": False},
                {"id": "deepseek", "name": "DeepSeek 大模型 - Fallback", "available": False}
            ]


        async def process_user_request(self, 
                                     user_request: str, 
                                     status_callback: Callable[[Dict[str, Any]], Awaitable[None]],
                                     selected_llm_identifier_from_frontend: Optional[str] = None,
                                     enable_chinese_thinking_from_frontend: Optional[bool] = None
                                     ) -> None:
            error_msg_content = "错误: 后端Agent核心模块未能加载,无法处理您的请求. 请联系管理员检查服务器日志 (V1.1.1-Fallback)." # 版本更新
            logger.error("假的Agent (server.py fallback): 收到请求,返回错误信息.")
            if status_callback:
                 request_id_fallback = f"fallback_req_{str(uuid.uuid4())[:6]}"
                 llm_interaction_id_fallback = f"fallback_llm_interaction_id_{str(uuid.uuid4())[:6]}"
                 
                 await status_callback({
                     "type": "general_status", 
                     "request_id": request_id_fallback,
                     "stage": "fatal_error_handler", 
                     "status": "error", 
                     "message": "Agent核心模块未加载,无法提供服务.",
                     "details": {"error_type": "AGENT_UNAVAILABLE", "technicalMessage": "Agent core module CircuitManusCore or circuitmanus.agent failed to load."}
                    })
                 await status_callback({
                     "type": "thinking_log", 
                     "request_id": request_id_fallback,
                     "llm_interaction_id": llm_interaction_id_fallback,
                     "stage": "error_synthesis",
                     "content": "Agent核心代码未加载 (V1.1.1 Fallback). 无法处理请求。" # 版本更新
                    })
                 await status_callback({
                     "type": "final_response", 
                     "request_id": request_id_fallback,
                     "llm_interaction_id": llm_interaction_id_fallback,
                     "content": error_msg_content,
                     "final_camelcase_json_if_success": None 
                    })


app = FastAPI(title="CircuitManus Agent API - V1.1.1 (Dynamic Model Availability)", version="1.4.1_dyn_model") # 版本更新

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.isdir(STATIC_DIR):
    logger.warning(f"默认静态文件目录 '{STATIC_DIR}' 未找到。尝试上一级目录的 'static'...")
    alt_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.isdir(alt_static_dir):
        STATIC_DIR = alt_static_dir
        logger.info(f"使用备用静态文件目录: {STATIC_DIR}")
    else:
        logger.error(f"静态文件目录 'static' 在 {STATIC_DIR} 或 {alt_static_dir} 均未找到。Web UI可能无法加载。")
try:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"静态文件目录 '{STATIC_DIR}' 已尝试挂载到 '/static'.")
except RuntimeError as e:
    logger.error(f"挂载静态文件目录 '{STATIC_DIR}' 失败: {e}. 请确保 'static' 目录存在于正确的位置.", exc_info=True)


agent_sessions: Dict[str, CircuitAgent] = {} 
agent_locks: Dict[str, asyncio.Lock] = {}   
active_websockets: Dict[str, WebSocket] = {} 


async def get_agent_instance(session_id: str) -> CircuitAgent:
    if session_id not in agent_sessions:
        logger.info(f"为 Session {session_id} 创建新的 Agent 实例 (V1.1.1 Multi-LLM & Configurable)...") # 版本更新
        if AGENT_AVAILABLE: 
            try:
                config_yaml_file_path = "config.yaml" 
                dotenv_file_path = ".env" 
                
                new_agent = CircuitAgent(
                    config_yaml_path=config_yaml_file_path,
                    dotenv_path=dotenv_file_path
                )
                
                agent_sessions[session_id] = new_agent
                agent_locks[session_id] = asyncio.Lock() 
                logger.info(f"Agent 实例为 Session {session_id} 创建成功 (V1.1.1).") # 版本更新
            except ValueError as ve: 
                logger.error(f"创建真实的 Agent 实例因配置问题失败 (Session {session_id}): {ve}", exc_info=True)
                raise RuntimeError(f"无法为会话 {session_id} 创建真实的 Agent 实例: {ve}") from ve
            except Exception as e: 
                logger.error(f"创建真实的 Agent 实例发生未知错误 (Session {session_id}): {e}", exc_info=True)
                raise RuntimeError(f"无法为会话 {session_id} 创建真实的 Agent 实例: {e}") from e
        else: 
             logger.warning(f"Agent 核心代码不可用,为 Session {session_id} 创建了一个假的 Agent 实例 (get_agent_instance).")
             agent_sessions[session_id] = CircuitAgent(config_yaml_path="dummy_config.yaml", dotenv_path=None) 
             agent_locks[session_id] = asyncio.Lock()
    return agent_sessions[session_id]

async def get_session_lock(session_id: str) -> asyncio.Lock:
    if session_id not in agent_locks:
        logger.debug(f"锁在 get_session_lock 中为 Session {session_id} 创建。")
        agent_locks[session_id] = asyncio.Lock()
    return agent_locks[session_id]

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    logger.info(f"收到对根路径 '/' 的请求 (来自: {request.client.host if request.client else '未知客户端'}). 尝试提供静态主页.")
    html_file_path = os.path.join(STATIC_DIR, "index.html")
    
    if not os.path.exists(html_file_path):
        logger.error(f"错误: 未在静态文件目录 '{STATIC_DIR}' 下找到 'index.html' 文件！")
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


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info(f"WebSocket 连接已接受 (来自: {websocket.client.host if websocket.client else '未知客户端'}:{websocket.client.port if websocket.client else '未知端口'}).")
    
    session_id: Optional[str] = None 
    agent_instance: Optional[CircuitAgent] = None 

    try:
        async def send_status_update_to_client(status_data: Dict[str, Any]) -> None:
            nonlocal session_id 
            if websocket.client_state.name == "CONNECTED": 
                try:
                    log_preview = json.dumps(status_data, ensure_ascii=False, default=str) 
                    logger.debug(f"SERVER SENDING TO CLIENT (Session {session_id or 'N/A'}, WS: {websocket.scope.get('path', '')}): {log_preview[:500]}{'...' if len(log_preview) > 500 else ''}")
                    await websocket.send_json(status_data)
                except WebSocketDisconnect: 
                    logger.warning(f"尝试发送状态更新到 Session {session_id or 'N/A'} 时WebSocket已断开 (send_status_update).")
                    raise asyncio.CancelledError("WebSocket connection lost during status update.")
                except Exception as e_send_status:
                    logger.error(f"通过WebSocket发送状态更新失败 (Session {session_id or 'N/A'}): {e_send_status}", exc_info=True)
            else:
                logger.warning(f"尝试发送状态更新到 Session {session_id or 'N/A'} 但WebSocket状态为 {websocket.client_state.name}。")
        
        while True:
            data = await websocket.receive_text() 
            try:
                message = json.loads(data) 
                msg_type = message.get("type") 

                if msg_type == "init": 
                    temp_session_id = message.get("session_id")
                    if not temp_session_id or not isinstance(temp_session_id, str) or not temp_session_id.strip():
                        session_id = str(uuid.uuid4()) 
                        logger.info(f"收到WebSocket初始化消息,未提供有效session_id,生成新的: {session_id}")
                    else:
                        session_id = temp_session_id.strip()
                        logger.info(f"收到WebSocket初始化消息,使用提供的session_id: {session_id}")
                    
                    active_websockets[session_id] = websocket
                    
                    try:
                        agent_instance = await get_agent_instance(session_id)
                        
                        # 【修改】在 init_success 中发送更详细的模型可用性信息
                        agent_defaults_for_frontend = {
                            "default_llm_identifier": agent_instance.default_llm_identifier,
                            "default_enable_chinese_thinking": agent_instance.default_enable_chinese_thinking,
                            "globally_enable_chinese_thinking": agent_instance.config_loader.get_config("agent_settings.feature_flags.enable_chinese_deep_thinking_globally", True),
                            # 发送 agent_instance.model_availability_details 而不是简单的列表
                            "detailed_available_llms": agent_instance.model_availability_details 
                        }
                        
                        await websocket.send_json({
                            "type": "init_success",
                            "session_id": session_id,
                            "message": "WebSocket连接建立成功,Agent (V1.1.1 Dynamic Models)已准备就绪.", # 版本更新
                            "agent_available": AGENT_AVAILABLE,
                            "agent_default_settings": agent_defaults_for_frontend
                        })
                        logger.info(f"Session {session_id} WebSocket初始化成功并发送确认 (包含详细模型可用性)。")
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
                    
                    selected_llm_from_fe = message.get("selected_llm") 
                    enable_chinese_thinking_from_fe = message.get("enable_chinese_thinking") 

                    if not isinstance(selected_llm_from_fe, str) or not selected_llm_from_fe:
                        logger.warning(f"Session {session_id}: 前端未提供有效的 selected_llm，将使用Agent默认值。")
                        selected_llm_from_fe = None 
                    if not isinstance(enable_chinese_thinking_from_fe, bool):
                        logger.warning(f"Session {session_id}: 前端未提供有效的 enable_chinese_thinking (布尔型)，将使用Agent默认值。")
                        enable_chinese_thinking_from_fe = None 
                    
                    logger.info(f"Session {session_id} 收到用户消息 (内容预览: '{user_message_content[:100]}...', 模型选择: {selected_llm_from_fe}, 中文思考: {enable_chinese_thinking_from_fe})")
                    
                    if not user_message_content or not isinstance(user_message_content, str) or not user_message_content.strip():
                         logger.warning(f"Session {session_id} 收到空消息内容或非字符串内容.")
                         await send_status_update_to_client({"type": "error", "message": "收到空消息或无效消息内容,已忽略.", "request_id": agent_instance.current_request_id or f"err_req_{str(uuid.uuid4())[:6]}"})
                         continue

                    lock = await get_session_lock(session_id) 
                    async with lock: 
                        logger.info(f"Session {session_id} 获取到锁,开始处理用户消息 (模型: {selected_llm_from_fe or 'Agent默认'}, 中文思考: {enable_chinese_thinking_from_fe if enable_chinese_thinking_from_fe is not None else 'Agent默认'})...")
                        start_time_process = time.monotonic()
                        try:
                            await agent_instance.process_user_request(
                                user_request=user_message_content, 
                                status_callback=send_status_update_to_client,
                                selected_llm_identifier_from_frontend=selected_llm_from_fe,
                                enable_chinese_thinking_from_frontend=enable_chinese_thinking_from_fe
                            )
                            duration_process = time.monotonic() - start_time_process
                            logger.info(f"Session {session_id} (ReqID: {agent_instance.current_request_id or 'N/A'}) 消息处理流程调用完成,耗时: {duration_process:.3f} 秒.")
                        except asyncio.CancelledError: 
                             logger.warning(f"Session {session_id} (ReqID: {agent_instance.current_request_id or 'N/A'}) Agent消息处理任务被取消 (可能由于WebSocket断开).")
                        except Exception as e_process: 
                            logger.error(f"Session {session_id} (ReqID: {agent_instance.current_request_id or 'N/A'}) Agent消息处理时发生内部顶层错误: {e_process}", exc_info=True)
                            error_details_str = str(e_process)
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
                                    "final_camelcase_json_if_success": None
                                })
                            except asyncio.CancelledError: 
                                logger.warning(f"Session {session_id} 发送顶层处理错误回调时WebSocket已断开。")
                            except Exception as e_send_fatal:
                                logger.error(f"Session {session_id} 发送顶层处理错误回调本身失败: {e_send_fatal}")
                        finally:
                             logger.info(f"Session {session_id} (ReqID: {agent_instance.current_request_id if agent_instance else 'N/A'}) 处理完毕,释放锁.")
                
                elif not session_id or not agent_instance: 
                    logger.warning(f"收到消息 (type: {msg_type}) 但 session_id ('{session_id}') 或 agent_instance ({'存在' if agent_instance else '不存在'}) 未完全初始化。忽略。")
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_json({"type": "error", "message": "会话未初始化或Agent实例创建失败,请先发送有效的 'init' 消息."})

                elif msg_type: 
                    logger.warning(f"Session {session_id or '未知'} 收到未知消息类型: '{msg_type}'. 消息内容(部分): {data[:100]}")
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_json({"type": "error", "message": f"服务器收到未知消息类型: '{msg_type}'"})
                
            except json.JSONDecodeError: 
                logger.warning(f"Session {session_id or '未知'} 收到非JSON格式或无效JSON消息: {data[:100]}...")
                if websocket.client_state.name == "CONNECTED":
                    try: 
                        await websocket.send_json({"type": "error", "message": "服务器收到无效消息格式,请发送JSON.", "details": f"原始消息(部分): {data[:100]}"})
                    except WebSocketDisconnect: pass 
            except WebSocketDisconnect: 
                 logger.info(f"Session {session_id or '未知'} WebSocket连接已断开 (在主接收循环中).")
                 break 
            except asyncio.CancelledError: 
                 logger.info(f"Session {session_id or '未知'} WebSocket消息处理任务被取消。")
                 break
            except Exception as e_loop: 
                logger.error(f"Session {session_id or '未知'} 在消息接收/处理循环中发生未预期错误: {e_loop}", exc_info=True)
                if websocket.client_state.name == "CONNECTED":
                    try:
                        await websocket.send_json({"type": "error", "message": f"服务器内部错误: {str(e_loop)[:100]}...", "details": "详细错误已记录在服务器日志中。"})
                        await websocket.close(code=1011) 
                    except Exception: pass 
                break 

    except WebSocketDisconnect as e_ws_disconnect: 
        logger.info(f"Session {session_id or '未知'} WebSocket连接已断开 (在主 try 块捕获): code={e_ws_disconnect.code}, reason='{e_ws_disconnect.reason}'")
    except Exception as e_websocket_main: 
        logger.critical(f"Session {session_id or '未知'} WebSocket连接处理发生顶层未预期异常: {e_websocket_main}", exc_info=True)
        if websocket.client_state.name == "CONNECTED": 
            try: 
                await websocket.send_json({"type":"error", "message":"WebSocket服务器遇到严重内部错误，连接将关闭。"})
                await websocket.close(code=1011)
            except Exception: pass 
    finally:
        if session_id:
            if session_id in active_websockets:
                del active_websockets[session_id]
                logger.info(f"Session {session_id} 的WebSocket连接已从活动列表中移除.")
        
        client_addr = f"{websocket.client.host if websocket.client else '未知'}:{websocket.client.port if websocket.client else '未知'}"
        logger.info(f"Session {session_id or '未知'} WebSocket连接处理结束 (客户端: {client_addr}).")


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING) 
    logging.getLogger("fastapi").setLevel(logging.INFO)

    server_logger = logging.getLogger("server_main") 
    server_logger.info("直接运行 server.py, 启动 Uvicorn 开发服务器 (V1.1.1 Dynamic Model Availability)...") # 版本更新

    if not os.path.exists(".env") and not (os.environ.get("ZHIPUAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")):
        server_logger.warning("！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！")
        server_logger.warning("警告: 未找到 .env 文件，且 ZHIPUAI_API_KEY 和 DEEPSEEK_API_KEY 环境变量均未设置。")
        server_logger.warning("Agent 可能无法连接到任何 LLM 服务。")
        server_logger.warning("！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！")
    elif not AGENT_AVAILABLE:
        server_logger.warning("警告: Agent核心模块 (circuitmanus.agent) 未能加载。服务器将使用备用的假Agent。")


    uvicorn.run(
        "server:app", 
        host="127.0.0.1",
        port=8000,
        reload=True, 
        log_level="debug" 
    )
