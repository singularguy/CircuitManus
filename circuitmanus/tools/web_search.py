# IDT_AGENT_NATIVE/circuitmanus/tools/web_search.py
import os
import asyncio
import json
import logging
import traceback
from typing import Dict, Any, List, TYPE_CHECKING, Optional

from duckduckgo_search import DDGS # 仅导入 DDGS，这是核心功能

# 尝试导入 SerpApi 的库
SERPAPI_AVAILABLE = False
try:
    from serpapi import GoogleSearch 
    SERPAPI_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning(
        "SerpApi client (google-search-results) 未安装。"
        "serpapi_google_search_tool 将不可用。"
        "请运行 'pip install google-search-results' 来安装它。"
    )
    GoogleSearch = None 

from .base import register_tool

if TYPE_CHECKING:
    from ..agent import CircuitAgent 

logger = logging.getLogger(__name__)

@register_tool(
    description="使用 DuckDuckGo 搜索引擎在互联网上搜索与给定查询词相关的信息。用于获取通用知识、技术细节或背景资料。如果遇到速率限制，可能会失败。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要搜索的关键词或问题。"},
            "num_results": {"type": "integer", "description": "期望返回的搜索结果数量 (例如: 1 到 5)。如果未提供或无效,默认为3。"}
        },
        "required": ["query"]
    }
)
async def duckduckgo_search_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-DuckDuckGoSearchTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行 DuckDuckGo 搜索操作。")
    query = arguments.get("query")
    num_results_req = arguments.get("num_results")
    logger.debug(f"{tool_call_logger_prefix} 收到搜索查询: '{query}', 期望结果数 (原始请求): {num_results_req}。")

    tool_result = {
        "status": "failure", 
        "message": "DuckDuckGo 搜索工具初始化失败或发生未知错误。", 
        "error": {
            "error_type": "UNEXPECTED_TOOL_ERROR", 
            "error_code": "DUCKDUCKGO_UNKNOWN_FAILURE", 
            "technical_message": "Tool did not complete successfully."
            }
    }

    if not query or not isinstance(query, str) or not query.strip():
        err_msg = "必须提供一个有效的、非空的搜索查询词。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        tool_result["message"] = f"错误: {err_msg}"
        tool_result["error"] = {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_SEARCH_QUERY", "technical_message": err_msg}
        return tool_result

    num_results_actual = 3 
    if num_results_req is not None:
        if isinstance(num_results_req, int) and 1 <= num_results_req <= 10:
            num_results_actual = num_results_req
        else:
            logger.warning(f"{tool_call_logger_prefix} num_results 参数 '{num_results_req}' 无效或超出范围(1-10), 将使用默认值 {num_results_actual}。")
    else:
        logger.debug(f"{tool_call_logger_prefix} 未提供 num_results 参数, 将使用默认值 {num_results_actual}。")
            
    search_results_raw_list: List[Dict[str, Any]] = []
    try:
        def sync_ddgs_operation(current_query: str, max_r: int) -> list:
            _internal_results = []
            logger.debug(f"{tool_call_logger_prefix} [sync_ddgs_op_internal] 开始执行DDGS同步搜索 for '{current_query}', max_results={max_r}")
            # 确保DDGS实例在使用时是活动的，使用 with 语句是一个好习惯
            with DDGS(timeout=20) as ddgs_instance: 
                fetched_results_iterator = ddgs_instance.text(keywords=current_query, max_results=max_r)
                count = 0
                for r_item in fetched_results_iterator:
                    if count >= max_r: # 手动确保不超过请求数量
                        break
                    _internal_results.append({
                        "title": r_item.get('title', 'N/A'),
                        "snippet": r_item.get('body', 'N/A'), 
                        "link": r_item.get('href', '#')      
                    })
                    count += 1
            logger.debug(f"{tool_call_logger_prefix} [sync_ddgs_op_internal] DDGS.text 内部处理后得到 {len(_internal_results)} 个结果条目。")
            return _internal_results

        logger.debug(f"{tool_call_logger_prefix} 准备将同步DDGS操作 (query: '{query}', num_results: {num_results_actual}) 提交到线程池...")
        search_results_raw_list = await asyncio.to_thread(sync_ddgs_operation, query, num_results_actual)
        logger.debug(f"{tool_call_logger_prefix} 同步DDGS操作完成，从线程返回了 {len(search_results_raw_list)} 个结果。")

        search_results_json_str = json.dumps(search_results_raw_list, ensure_ascii=False)
        success_message = f"已成功完成对“{query}”的 DuckDuckGo 搜索,找到 {len(search_results_raw_list)} 条相关信息。"
        logger.info(f"{tool_call_logger_prefix} {success_message}")
        
        self.memory_manager.add_to_long_term(f"执行了 DuckDuckGo 搜索,查询词: '{query}', 返回了 {len(search_results_raw_list)} 条结果 (请求ID: {self.current_request_id or 'N/A'})。")
        
        tool_result = {
            "status": "success",
            "message": success_message,
            "data": { 
                "query": query,
                "num_results_requested": num_results_actual, 
                "num_results_returned": len(search_results_raw_list), 
                "results_json_string": search_results_json_str 
            }
        }
        return tool_result
    
    except Exception as e_search: # 捕获所有可能的异常
        err_msg = f"使用 DuckDuckGo 搜索时发生错误: {e_search}"
        logger.error(f"{tool_call_logger_prefix} {err_msg}", exc_info=True) # 记录完整traceback
        
        error_code = "DUCKDUCKGO_SEARCH_UNEXPECTED_FAILURE"
        error_type = "UNEXPECTED_TOOL_ERROR"

        # 尝试从错误消息中识别 Ratelimit
        if "Ratelimit" in str(e_search) or "202" in str(e_search):
            error_code = "DUCKDUCKGO_RATELIMIT_ERROR"
            error_type = "EXTERNAL_SERVICE_ERROR"
            err_msg = f"DuckDuckGo 搜索请求过于频繁或服务受限。({e_search})" # 更新用户友好的消息

        tool_result["message"] = f"错误: {err_msg}" # 将更具体的错误消息返回
        tool_result["error"] = {
            "error_type": error_type, 
            "error_code": error_code, 
            "technical_message": str(e_search), 
            "exception_details": traceback.format_exc(limit=3) # 限制堆栈深度，避免过长
            }
        return tool_result

# --- SerpApi Google 搜索工具 (保持不变) ---
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

    tool_result = {
        "status": "failure",
        "message": "SerpApi Google 搜索工具初始化或执行失败。",
        "error": {"error_type": "TOOL_SETUP_OR_EXECUTION_ERROR", "error_code": "SERPAPI_UNKNOWN_FAILURE", "technical_message": "Tool did not complete successfully."}
    }

    if not SERPAPI_AVAILABLE:
        err_msg = "SerpApi 客户端库 (google-search-results) 未安装或无法导入。"
        logger.error(f"{tool_call_logger_prefix} {err_msg}")
        tool_result["message"] = f"错误: {err_msg} Agent无法使用此工具。"
        tool_result["error"] = {"error_type": "TOOL_SETUP_ERROR", "error_code": "SERPAPI_LIBRARY_MISSING", "technical_message": err_msg}
        return tool_result

    serpapi_api_key = os.environ.get("SERPAPI_API_KEY")
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

    num_results_actual = 5 
    if num_results_req is not None:
        if isinstance(num_results_req, int) and 1 <= num_results_req <= 20: 
            num_results_actual = num_results_req
        else:
            logger.warning(f"{tool_call_logger_prefix} num_results 参数 '{num_results_req}' 无效或超出范围(1-20 for SerpApi), 将使用默认值 {num_results_actual}。")
    else:
        logger.debug(f"{tool_call_logger_prefix} 未提供 num_results 参数, 将使用默认值 {num_results_actual}。")

    search_params = {
        "q": query,
        "api_key": serpapi_api_key,
        "num": str(num_results_actual),  
        "hl": "zh-cn", 
        "gl": "cn",     
    }

    search_results_processed: List[Dict[str, Any]] = []
    try:
        def sync_serpapi_operation(params: Dict[str, str]) -> dict:
            logger.debug(f"{tool_call_logger_prefix} [sync_serpapi_op_internal] 开始执行SerpApi同步搜索 with params: {params.get('q')}, num: {params.get('num')}")
            if GoogleSearch is None: 
                raise RuntimeError("SerpApi GoogleSearch class is not available.")
            search = GoogleSearch(params)
            results = search.get_dict() 
            logger.debug(f"{tool_call_logger_prefix} [sync_serpapi_op_internal] SerpApi返回了原始字典。")
            return results

        logger.debug(f"{tool_call_logger_prefix} 准备将同步SerpApi操作提交到线程池...")
        raw_serpapi_results = await asyncio.to_thread(sync_serpapi_operation, search_params)
        logger.debug(f"{tool_call_logger_prefix} 同步SerpApi操作完成。")

        if raw_serpapi_results and "organic_results" in raw_serpapi_results:
            for res_item in raw_serpapi_results["organic_results"][:num_results_actual]: 
                search_results_processed.append({
                    "title": res_item.get("title", "N/A"),
                    "snippet": res_item.get("snippet", res_item.get("link_type_result", {}).get("snippet", "N/A")), 
                    "link": res_item.get("link", "#"),
                    "source": "Google (via SerpApi)" 
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
        elif raw_serpapi_results and "error" in raw_serpapi_results:
            api_error_message = raw_serpapi_results["error"]
            logger.error(f"{tool_call_logger_prefix} SerpApi 返回错误: {api_error_message}")
            tool_result["message"] = f"SerpApi 错误: {api_error_message}"
            tool_result["error"] = {"error_type": "EXTERNAL_SERVICE_API_ERROR", "error_code": "SERPAPI_API_ERROR_RESPONSE", "technical_message": api_error_message}
            return tool_result
        else:
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