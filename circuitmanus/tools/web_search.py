# IDT_AGENT_NATIVE/circuitmanus/tools/web_search.py
import os # 需要导入 os 来读取环境变量
import asyncio
import json
import logging
import traceback
from typing import Dict, Any, List, TYPE_CHECKING, Optional # 导入 Optional 和 List

from duckduckgo_search import DDGS # 仅导入 DDGS，这是核心功能

# --- SerpApi 相关导入和可用性检查 ---
SERPAPI_AVAILABLE = False
GoogleSearch = None # 初始化为None
try:
    from serpapi import GoogleSearch # type: ignore
    SERPAPI_AVAILABLE = True
    logger_serp_init = logging.getLogger(__name__) # 在 try 块内获取 logger
    logger_serp_init.info("SerpApi client (google-search-results) 导入成功。serpapi_google_search_tool 将可用 (如果配置了API Key)。")
except ImportError:
    # 如果导入失败，也需要一个 logger 实例来记录警告
    # 确保 logger 在任何情况下都已初始化
    logging.getLogger(__name__).warning( # 直接使用 logging.getLogger
        "SerpApi client (google-search-results) 未安装。"
        "serpapi_google_search_tool 将不可用。"
        "请运行 'pip install google-search-results' 来安装它。"
    )
    # GoogleSearch 保持为 None

from .base import register_tool

if TYPE_CHECKING:
    from ..agent import CircuitAgent 
    from ..utils.config_loader import ConfigLoader # 导入 ConfigLoader 类型提示

logger = logging.getLogger(__name__) # 模块级 logger

@register_tool(
    description="使用 DuckDuckGo 搜索引擎在互联网上搜索与给定查询词相关的信息。用于获取通用知识、技术细节或背景资料。如果遇到速率限制，可能会失败。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要搜索的关键词或问题。"},
            "num_results": {"type": "integer", "description": "期望返回的搜索结果数量 (例如: 1 到 10)。如果未提供或无效,将使用配置文件中的默认值 (通常是3)。"}
        },
        "required": ["query"]
    }
)
async def duckduckgo_search_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Agent工具：使用 DuckDuckGo 进行网络搜索。
    现在会从配置中读取默认结果数和超时时间。
    """
    tool_call_logger_prefix = f"[Action-DuckDuckGoSearchTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行 DuckDuckGo 搜索操作 (Configurable)...")
    
    query = arguments.get("query")
    num_results_from_llm = arguments.get("num_results") 
    
    logger.debug(f"{tool_call_logger_prefix} 收到搜索查询: '{query}', LLM请求结果数: {num_results_from_llm}。")

    tool_result = { 
        "status": "failure", 
        "message": "DuckDuckGo 搜索工具发生未知内部错误。", 
        "error": { "error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DUCKDUCKGO_TOOL_UNKNOWN_FAILURE", 
                   "technical_message": "Tool did not complete successfully." }
    }

    if not query or not isinstance(query, str) or not query.strip():
        err_msg = "必须提供一个有效的、非空的搜索查询词。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        tool_result["message"] = f"错误: {err_msg}"
        tool_result["error"] = {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_SEARCH_QUERY", "technical_message": err_msg}
        return tool_result

    config_loader: 'ConfigLoader' = self.config_loader 
    
    default_num_results_cfg = config_loader.get_config(
        "agent_settings.tools.specific_tools.duckduckgo_search.default_num_results", 3
    )
    timeout_seconds_cfg = config_loader.get_config(
        "agent_settings.tools.specific_tools.duckduckgo_search.timeout_seconds", 20
    )
    # (可选) 如果需要从配置读取 region 和 safesearch
    # region_cfg = config_loader.get_config("agent_settings.tools.specific_tools.duckduckgo_search.region", "wt-wt")
    # safe_search_cfg = config_loader.get_config("agent_settings.tools.specific_tools.duckduckgo_search.safe_search", "moderate")


    num_results_to_fetch: int
    if num_results_from_llm is not None:
        if isinstance(num_results_from_llm, int) and 1 <= num_results_from_llm <= 10:
            num_results_to_fetch = num_results_from_llm
            logger.debug(f"{tool_call_logger_prefix} 使用LLM提供的结果数: {num_results_to_fetch}.")
        else:
            logger.warning(f"{tool_call_logger_prefix} LLM提供的 num_results ('{num_results_from_llm}') 无效或超出范围(1-10)。将使用配置的默认值: {default_num_results_cfg}.")
            num_results_to_fetch = default_num_results_cfg
    else: 
        num_results_to_fetch = default_num_results_cfg
        logger.debug(f"{tool_call_logger_prefix} LLM未提供结果数，使用配置的默认值: {num_results_to_fetch}.")
            
    search_results_list: List[Dict[str, Any]] = [] # 明确类型提示
    try:
        def sync_ddgs_operation(current_query: str, max_r: int, timeout_s: int) -> List[Dict[str, Any]]: # 返回类型调整
            _internal_results: List[Dict[str, Any]] = []
            logger.debug(f"{tool_call_logger_prefix} [sync_ddgs_op_internal] 开始DDGS同步搜索: query='{current_query}', max_results={max_r}, timeout={timeout_s}s")
            
            with DDGS(timeout=float(timeout_s)) as ddgs_instance: 
                # ddgs_params_for_sdk = {}
                # if region_cfg: ddgs_params_for_sdk["region"] = region_cfg
                # if safe_search_cfg: ddgs_params_for_sdk["safesearch"] = safe_search_cfg
                # # ... 其他可能的参数
                # fetched_results_iterator = ddgs_instance.text(keywords=current_query, max_results=max_r, **ddgs_params_for_sdk)
                fetched_results_iterator = ddgs_instance.text(keywords=current_query, max_results=max_r) # 保持简单
                
                count = 0
                for r_item in fetched_results_iterator:
                    if count >= max_r: 
                        break
                    _internal_results.append({
                        "title": str(r_item.get('title', 'N/A')), 
                        "snippet": str(r_item.get('body', 'N/A')), 
                        "link": str(r_item.get('href', '#'))      
                    })
                    count += 1
            logger.debug(f"{tool_call_logger_prefix} [sync_ddgs_op_internal] DDGS内部处理后得到 {len(_internal_results)} 个结果。")
            return _internal_results

        logger.debug(f"{tool_call_logger_prefix} 准备将同步DDGS操作 (query='{query}', num_results={num_results_to_fetch}, timeout={timeout_seconds_cfg}s) 提交到线程池...")
        search_results_list = await asyncio.to_thread(sync_ddgs_operation, query, num_results_to_fetch, timeout_seconds_cfg)
        logger.debug(f"{tool_call_logger_prefix} 同步DDGS操作完成，从线程返回了 {len(search_results_list)} 个结果。")

        search_results_json_str = json.dumps(search_results_list, ensure_ascii=False)
        success_message = f"已成功完成对“{query}”的 DuckDuckGo 搜索,找到 {len(search_results_list)} 条相关信息。"
        logger.info(f"{tool_call_logger_prefix} {success_message}")
        
        self.memory_manager.add_to_long_term(f"执行了 DuckDuckGo 搜索,查询词: '{query}', 返回了 {len(search_results_list)} 条结果 (请求ID: {self.current_request_id or 'N/A'})。")
        
        tool_result = {
            "status": "success",
            "message": success_message,
            "data": { 
                "query": query,
                "num_results_requested": num_results_to_fetch, 
                "num_results_returned": len(search_results_list), 
                "results_json_string": search_results_json_str 
            }
        }
        return tool_result
    
    except Exception as e_search: 
        err_msg = f"使用 DuckDuckGo 搜索时发生错误: {e_search}"
        logger.error(f"{tool_call_logger_prefix} {err_msg}", exc_info=True) 
        
        error_code = "DUCKDUCKGO_SEARCH_UNEXPECTED_FAILURE"
        error_type = "UNEXPECTED_TOOL_ERROR"

        # 尝试从错误消息中识别 Ratelimit (与您原版一致)
        # 注意：这种基于字符串匹配的错误识别可能不够稳健，如果库的错误消息格式改变，这里可能失效。
        # 更稳健的方式是捕获库抛出的特定异常类型（如果库有定义的话）。
        if "Ratelimit" in str(e_search).lower() or "rate limit" in str(e_search).lower() or \
           "429" in str(e_search) or "202" in str(e_search): # 扩展匹配条件
            error_code = "DUCKDUCKGO_RATELIMIT_ERROR"
            error_type = "EXTERNAL_SERVICE_ERROR"
            # 提供更具体的错误消息给用户或LLM
            err_msg = f"DuckDuckGo 搜索请求可能过于频繁或服务暂时受限。请稍后再试。 (原始错误: {e_search})"

        tool_result["message"] = f"错误: {err_msg}" 
        tool_result["error"] = {
            "error_type": error_type, 
            "error_code": error_code, 
            "technical_message": str(e_search), 
            "exception_details": traceback.format_exc(limit=3) 
            }
        return tool_result

# --- SerpApi Google 搜索工具 (保持与您原版一致的逻辑) ---
@register_tool(
    description="使用 SerpApi 通过 Google 搜索引擎在互联网上搜索信息。需要有效的 SerpApi API Key 配置。用于获取通用知识、技术细节或当 DuckDuckGo 不可用时作为备选。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要搜索的关键词或问题。"},
            "num_results": {"type": "integer", "description": "期望返回的搜索结果数量 (例如: 1 到 10)。如果未提供或无效,默认为5。SerpApi的 'num' 参数控制返回结果。"}
        },
        "required": ["query"]
    }
)
async def serpapi_google_search_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-SerpApiGoogleSearchTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行 SerpApi Google 搜索操作。")
    
    query = arguments.get("query")
    num_results_req = arguments.get("num_results")
    logger.debug(f"{tool_call_logger_prefix} 收到搜索查询: '{query}', 期望结果数 (原始请求): {num_results_req}。")

    tool_result = { # 标准返回结构
        "status": "failure",
        "message": "SerpApi Google 搜索工具初始化或执行失败。",
        "error": {"error_type": "TOOL_SETUP_OR_EXECUTION_ERROR", "error_code": "SERPAPI_UNKNOWN_FAILURE", "technical_message": "Tool did not complete successfully."}
    }

    if not SERPAPI_AVAILABLE: # 检查库是否成功导入
        err_msg = "SerpApi 客户端库 (google-search-results) 未安装或无法导入。"
        logger.error(f"{tool_call_logger_prefix} {err_msg}")
        tool_result["message"] = f"错误: {err_msg} Agent无法使用此工具。"
        tool_result["error"] = {"error_type": "TOOL_SETUP_ERROR", "error_code": "SERPAPI_LIBRARY_MISSING", "technical_message": err_msg}
        return tool_result

    # 从环境变量（由 ConfigLoader 辅助加载）获取 SerpApi Key
    # 注意：self.config_loader 是 Agent 的属性
    serpapi_api_key = self.config_loader.get_env_var("SERPAPI_API_KEY") 
    if not serpapi_api_key:
        err_msg = "SerpApi API Key (SERPAPI_API_KEY) 未在环境变量中设置。"
        logger.error(f"{tool_call_logger_prefix} {err_msg}")
        tool_result["message"] = f"错误: {err_msg} Agent无法使用此工具。"
        tool_result["error"] = {"error_type": "TOOL_SETUP_ERROR", "error_code": "SERPAPI_API_KEY_MISSING", "technical_message": err_msg}
        return tool_result

    if not query or not isinstance(query, str) or not query.strip():
        err_msg = "必须提供一个有效的、非空的搜索查询词。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        tool_result["message"] = f"错误: {err_msg}"
        tool_result["error"] = {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_SEARCH_QUERY", "technical_message": err_msg}
        return tool_result

    # SerpApi 的结果数和超时也可以从配置中读取，如果需要的话
    # 例如： default_num_results_serpapi = self.config_loader.get_config("agent_settings.tools.specific_tools.serpapi_google.default_num_results", 5)
    # timeout_serpapi = self.config_loader.get_config("agent_settings.tools.specific_tools.serpapi_google.timeout_seconds", 30)
    # 这里暂时使用您原版的默认值和范围
    num_results_actual = 5 
    if num_results_req is not None:
        if isinstance(num_results_req, int) and 1 <= num_results_req <= 20: # SerpApi 的 'num' 通常支持到100，但这里保守一些
            num_results_actual = num_results_req
        else:
            logger.warning(f"{tool_call_logger_prefix} num_results 参数 '{num_results_req}' 无效或超出范围(1-20 for SerpApi), 将使用默认值 {num_results_actual}。")
    else:
        logger.debug(f"{tool_call_logger_prefix} 未提供 num_results 参数, 将使用默认值 {num_results_actual}。")

    search_params = {
        "q": query,
        "api_key": serpapi_api_key,
        "num": str(num_results_actual),  # SerpApi 的 num 参数期望是字符串
        "hl": "zh-cn", # 语言设置为中文（中国）
        "gl": "cn",     # 地理位置设置为中国
        # "engine": "google" # 默认为 google，可以显式指定
    }

    search_results_processed: List[Dict[str, Any]] = []
    try:
        def sync_serpapi_operation(params: Dict[str, str]) -> dict:
            logger.debug(f"{tool_call_logger_prefix} [sync_serpapi_op_internal] 开始执行SerpApi同步搜索: query='{params.get('q')}', num='{params.get('num')}'")
            if GoogleSearch is None: # 再次检查，尽管 SERPAPI_AVAILABLE 应该已经处理了
                raise RuntimeError("SerpApi GoogleSearch class is not available (GoogleSearch is None).")
            search = GoogleSearch(params) # 使用从 serpapi 导入的 GoogleSearch
            results = search.get_dict() # 获取原始字典结果
            logger.debug(f"{tool_call_logger_prefix} [sync_serpapi_op_internal] SerpApi返回了原始字典。")
            return results

        logger.debug(f"{tool_call_logger_prefix} 准备将同步SerpApi操作提交到线程池...")
        raw_serpapi_results: Dict[str, Any] = await asyncio.to_thread(sync_serpapi_operation, search_params)
        logger.debug(f"{tool_call_logger_prefix} 同步SerpApi操作完成。")

        # 处理 SerpApi 返回的结果
        if raw_serpapi_results and "organic_results" in raw_serpapi_results:
            for res_item in raw_serpapi_results["organic_results"][:num_results_actual]: # 再次确保不超过请求数量
                snippet = res_item.get("snippet", "N/A")
                # 有时 snippet 可能在 link_type_result 中，如您原代码所示
                if snippet == "N/A" and "link_type_result" in res_item and isinstance(res_item["link_type_result"], dict):
                    snippet = res_item["link_type_result"].get("snippet", "N/A")
                
                search_results_processed.append({
                    "title": str(res_item.get("title", "N/A")),
                    "snippet": str(snippet), 
                    "link": str(res_item.get("link", "#")),
                    "source": "Google (via SerpApi)" # 标明来源
                })
            
            search_results_json_str = json.dumps(search_results_processed, ensure_ascii=False)
            success_message = f"已成功通过 SerpApi 完成对“{query}”的 Google 搜索,找到 {len(search_results_processed)} 条相关信息。"
            logger.info(f"{tool_call_logger_prefix} {success_message}")
            
            self.memory_manager.add_to_long_term(f"执行了 SerpApi Google 搜索,查询词: '{query}', 返回了 {len(search_results_processed)} 条结果 (请求ID: {self.current_request_id or 'N/A'})。")

            tool_result = {
                "status": "success",
                "message": success_message,
                "data": {
                    "query": query,
                    "num_results_requested": num_results_actual,
                    "num_results_returned": len(search_results_processed),
                    "results_json_string": search_results_json_str
                }
            }
            return tool_result
        elif raw_serpapi_results and "error" in raw_serpapi_results: # SerpApi 返回了错误信息
            api_error_message = str(raw_serpapi_results["error"])
            logger.error(f"{tool_call_logger_prefix} SerpApi 返回错误: {api_error_message}")
            tool_result["message"] = f"SerpApi 错误: {api_error_message}"
            tool_result["error"] = {"error_type": "EXTERNAL_SERVICE_API_ERROR", "error_code": "SERPAPI_API_ERROR_RESPONSE", "technical_message": api_error_message}
            return tool_result
        else: # 返回结果结构不符合预期
            logger.warning(f"{tool_call_logger_prefix} SerpApi 搜索未返回 'organic_results' 或 'error' 字段。响应(部分): {str(raw_serpapi_results)[:500]}")
            tool_result["message"] = "SerpApi 搜索未返回预期的结果结构。"
            tool_result["error"] = {"error_type": "EXTERNAL_SERVICE_ERROR", "error_code": "SERPAPI_UNEXPECTED_RESPONSE_STRUCTURE", "technical_message": "No 'organic_results' or 'error' in SerpApi response."}
            return tool_result

    except Exception as e_serpapi:
        err_msg = f"使用 SerpApi Google 搜索时发生错误: {e_serpapi}"
        logger.error(f"{tool_call_logger_prefix} {err_msg}", exc_info=True)
        tool_result["message"] = f"错误: {err_msg}"
        tool_result["error"] = {
            "error_type": "EXTERNAL_SERVICE_ERROR", 
            "error_code": "SERPAPI_SEARCH_UNEXPECTED_FAILURE", 
            "technical_message": str(e_serpapi), 
            "exception_details": traceback.format_exc(limit=3)
        }
        return tool_result