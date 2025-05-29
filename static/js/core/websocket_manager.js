// ==========================================================================
// [ START OF FILE core/websocket_manager.js ]
// WebSocket Connection and Message Handling
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from './state.js';
// 【老板，修改！】从 session_handler.js 导入的函数现在包含 showHistoricalLogsForRequest
import { initializeCurrentSessionUI, addMessageToCurrentSession, renderSessionList, saveSessions as saveSessionData, showHistoricalLogsForRequest } from '../modules/session_handler.js'; 
import { appendMessage, appendWelcomeMessage, showToast, hideTypingIndicator, setLoadingState, appendLogItem, appendLogItemWithThink } from './ui_updater.js';
import { showProcessLogSidebar } from '../modules/layout_handler.js';
import { generateClientRequestId, summarizeArguments, parseItemClasses, APP_PREFIX, formatLogDetails } from '../utils/helpers.js'; 
import { populateLLMModelSelect, updateChineseDeepThinkingToggleState } from '../modules/settings_handler.js';


let websocket = null;
const websocketUrl = `ws://${window.location.host}/ws/chat`;
let wsReconnectAttempts = 0;
const MAX_WS_RECONNECT_ATTEMPTS = 3; 
const WS_RECONNECT_INTERVAL = 3000; 

export function connectWebSocket() {
    if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
        console.log("WebSocket: 已连接或正在连接中。");
        return;
    }
    console.log(`WebSocket: 尝试连接 (第 ${wsReconnectAttempts + 1} 次) 到 ${websocketUrl}`);
    if (dom.loader && wsReconnectAttempts === 0 && !dom.loader.classList.contains('loader-fatal-error')) {
        const loadingText = dom.loader.querySelector('.loading-text');
        if (loadingText) loadingText.textContent = "同步光绘墨迹流 (V1.1.1 Lumina)..."; 
    }

    websocket = new WebSocket(websocketUrl);

    websocket.onopen = (event) => {
        console.log("WebSocket: 连接已建立。", event);
        wsReconnectAttempts = 0;
        showToast("光绘墨迹数据流 ACTIVE (V1.1.1 Lumina).", "success", 4000); 
        sendWebSocketMessage({
            type: 'init',
            session_id: state.currentSessionId 
        });
        if (dom.loader && !dom.loader.classList.contains('loader-fatal-error')) dom.loader.classList.add('hidden');
        if (dom.mainContainer) dom.mainContainer.classList.add('loaded');
    };

    websocket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            console.log("WS RX:", message);
            handleWebSocketMessage(message);
        } catch (e) {
            console.error("WebSocket: 解析消息失败。", e, "原始数据:", event.data);
            showToast("收到损坏的数据包流 (JSON解析失败).", "error");
        }
    };

    websocket.onerror = (event) => {
        console.error("WebSocket: 发生错误。", event);
    };

    websocket.onclose = (event) => {
        console.log("WebSocket: 连接已关闭。", event);
        hideTypingIndicator();
        setLoadingState(false);
        
        const reason = event.reason ? `原因: ${event.reason}` : (event.wasClean ? '连接正常关闭.' : '连接异常断开.');
        const codeMsg = `(代码: ${event.code})`;

        if (!event.wasClean && wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
            wsReconnectAttempts++;
            showToast(`墨迹数据链接不稳定. 尝试重新校准 (${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})... ${codeMsg}`, "warning", WS_RECONNECT_INTERVAL + 500);
            setTimeout(connectWebSocket, WS_RECONNECT_INTERVAL);
        } else if (!event.wasClean) {
            websocket = null; 
            if (dom.mainContainer) dom.mainContainer.style.display = 'none';
            if (dom.toastContainer) dom.toastContainer.innerHTML = '';
            if (dom.loader) {
                dom.loader.classList.add('loader-fatal-error');
                dom.loader.classList.remove('hidden');
                dom.loader.innerHTML = ''; 

                const fatalErrorCore = document.createElement('div');
                fatalErrorCore.className = 'lumina-loader-core error-state';
                fatalErrorCore.innerHTML = `<div class="lumina-loader-center-pulse"></div>`;

                const fatalErrorLogo = document.createElement('div');
                fatalErrorLogo.className = 'loader-logo-text';
                fatalErrorLogo.innerHTML = `<span>CIRCUIT</span>MANUS<span class="loader-version-pro">PRO</span> - 链接故障`;

                const fatalErrorHeading = document.createElement('p');
                fatalErrorHeading.className = 'loading-text';
                fatalErrorHeading.textContent = "通信链接已断开且无法恢复";

                const fatalErrorDetails = document.createElement('p');
                fatalErrorDetails.className = 'error-details-text';
                fatalErrorDetails.textContent = `与后端核心的连接已彻底中断 (${MAX_WS_RECONNECT_ATTEMPTS} 次校准尝试失败)。请检查您的网络连接或服务器状态。${codeMsg} ${reason}`;

                const refreshButton = document.createElement('button');
                refreshButton.id = 'refresh-page-button';
                refreshButton.className = 'lumina-button lumina-button-primary refresh-button';
                refreshButton.innerHTML = '<i class="fas fa-sync-alt"></i> 刷新页面';
                refreshButton.onclick = () => window.location.reload();

                dom.loader.appendChild(fatalErrorCore);
                dom.loader.appendChild(fatalErrorLogo);
                dom.loader.appendChild(fatalErrorHeading);
                dom.loader.appendChild(fatalErrorDetails);
                dom.loader.appendChild(refreshButton);
            }
        } else { 
            websocket = null; 
            showToast(`通信链接已终止. ${codeMsg} ${reason}`, "info", 6000);
        }
    };
}

export function sendWebSocketMessage(message) {
    if (message.type === 'message') {
        message.selected_llm = state.selectedLLM; 
        message.enable_chinese_thinking = state.enableChineseDeepThinking; 
    }

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const messageStr = JSON.stringify(message);
        console.log("WS TX:", message); 
        websocket.send(messageStr);
    } else {
        console.error("WebSocket: 连接未打开。无法发送消息:", message);
        showToast("通信链接不活跃. 尝试重新建立链接...", "warning");
        if (!websocket || websocket.readyState === WebSocket.CLOSED || websocket.readyState === WebSocket.CLOSING) {
            if (wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                connectWebSocket(); 
            } else {
                showToast("无法发送: 达到最大重连尝试次数. 请刷新页面.", "error");
            }
        }
    }
}

function handleWebSocketMessage(message) {
    try {
        switch (message.type) {
            case 'init_success':
                try {
                    state.currentSessionId = message.session_id;
                    localStorage.setItem(APP_PREFIX + 'lastSessionId', state.currentSessionId);

                    if (message.agent_default_settings) {
                        state.agentDefaultSettings = { ...state.agentDefaultSettings, ...message.agent_default_settings };
                        state.selectedLLM = localStorage.getItem(APP_PREFIX + 'selectedLLM') || state.agentDefaultSettings.default_llm_identifier;
                        if (state.agentDefaultSettings.globally_enable_chinese_thinking === false) {
                            state.enableChineseDeepThinking = false;
                        } else {
                            state.enableChineseDeepThinking = (localStorage.getItem(APP_PREFIX + 'enableChineseDeepThinking') || state.agentDefaultSettings.default_enable_chinese_thinking.toString()) === 'true';
                        }
                        console.log("从后端同步了Agent默认设置: ", JSON.parse(JSON.stringify(state.agentDefaultSettings))); 
                        console.log("初始化后当前选择的模型:", state.selectedLLM, "中文思考:", state.enableChineseDeepThinking);
                        populateLLMModelSelect(); 
                        updateChineseDeepThinkingToggleState(); 
                    }
                    
                    const agentStatusMessage = message.agent_available === false
                        ? 'Lumina AI核心 OFFLINE. 功能受限. (V1.1.1 Lumina)' 
                        : 'Lumina核心 (V1.1.1 Lumina) 已同步到光绘网络!'; 
                    const agentStatusType = message.agent_available === false ? 'warning' : 'success';
                    showToast(agentStatusMessage, agentStatusType, message.agent_available ? 4500 : 8000);

                    if (!state.sessions[state.currentSessionId]) {
                        const now = Date.now();
                        state.sessions[state.currentSessionId] = {
                            id: state.currentSessionId,
                            name: `光绘墨迹项目 ${Object.keys(state.sessions).length + 1}`,
                            messages: [],
                            createdAt: now,
                            lastActivity: now,
                            executionLogs: [], // 确保新会话也有此属性
                        };
                        saveSessionData(); 
                    }
                    initializeCurrentSessionUI(true); 
                } catch (e) {
                    console.error(`处理 init_success 消息时出错:`, e, message); 
                    showToast(`处理初始化成功消息时出错: ${e.message}`, 'error');
                }
                break;
            case 'init_error':
                try {
                    showToast(`AI核心同步失败: ${message.message}`, 'error', 10000);
                    if (dom.loader && !dom.loader.classList.contains('loader-fatal-error')) dom.loader.classList.add('hidden');
                    if (dom.mainContainer) dom.mainContainer.classList.add('loaded');
                    if (message.agent_available === false) {
                        appendMessage("CRITICAL SYSTEM ALERT: Lumina AI核心未能初始化. 子系统无响应. (V1.1.1 Lumina)", 'error-system', false, null, false, [], "System Error");
                    }
                    setLoadingState(false);
                } catch (e) {
                    console.error(`处理 init_error 消息时出错:`, e, message);
                    showToast(`处理初始化错误消息时出错: ${e.message}`, 'error');
                }
                break;
            case 'error': 
                try {
                    console.error("服务器报告错误:", message);
                    showToast(`服务器异常: ${message.message}`, 'error', 7000);
                    if (message.details) {
                        appendMessage(`SERVER ERROR (${message.message}): ${message.details}`, 'error-system', false, null, false, [], "Server Error");
                    }
                    setLoadingState(false);
                } catch (e) {
                    console.error(`处理服务器 'error' 消息时出错:`, e, message);
                    showToast(`处理服务器错误报告时出错: ${e.message}`, 'error');
                }
                break;
            case 'general_status': handleGeneralStatus(message); break;
            case 'llm_communication_status': handleLlmCommStatus(message); break;
            case 'thinking_log': handleThinkingLog(message); break;
            case 'plan_details': handlePlanDetails(message); break;
            case 'tool_status_update': handleToolStatusUpdate(message); break;
            case 'interim_response': handleInterimResponse(message); break;
            case 'final_response':
                try {
                    handleFinalResponse(message);
                } catch (e_final_resp) {
                    console.error(`处理 final_response 时发生错误:`, e_final_resp, message);
                    showToast(`处理最终响应时发生内部错误: ${e_final_resp.message}`, 'error');
                    hideTypingIndicator();
                    setLoadingState(false);
                }
                break;
            default:
                console.warn("收到未知数据包类型:", message.type, message);
                showToast(`未知数据包类型: ${message.type}`, 'warning');
        }
    } catch (e_outer_switch) {
        console.error("处理WebSocket消息switch逻辑时发生严重错误。", e_outer_switch, "原始消息:", message);
        showToast("处理服务器消息时发生严重内部错误。", "error");
        hideTypingIndicator();
        setLoadingState(false);
    }
}

function handleGeneralStatus(msg) {
    const { stage, status, message: msgText, details, request_id } = msg; // 【老板，新增！】获取 request_id
    let logIconClass = 'fas fa-info-circle log-info';
    let logItemClasses = `type-general_status stage-${stage} status-${status}`;

    if (status === 'started' || status === 'llm_retry_needed' || status === 'llm_error_retrying') logIconClass = 'fas fa-sync-alt fa-spin log-processing';
    else if (status === 'completed' || status === 'received' || status === 'completed_and_validated') logIconClass = 'fas fa-check-circle log-success';
    else if (status === 'error' || status === 'failed' || status === 'failed_after_llm_retries' || status === 'tool_failure_detected' || status === 'fatal_error_handler' || status === 'fatal_error_capture' || status === 'llm_selection_override') { 
        logIconClass = 'fas fa-exclamation-triangle log-error';
        if (status === 'llm_selection_override') logIconClass = 'fas fa-random log-warning'; 
    }
    else if (status === 'ignored') logIconClass = 'fas fa-eye-slash log-muted';

    appendLogItem(msgText, logIconClass, logItemClasses, details);
    
    // 【老板，新增！】如果 general_status 消息中包含 request_id，且与当前处理的请求匹配，则更新日志集合的 agentRequestId
    if (request_id && state.currentRequestLogCollection && state.currentRequestLogCollection.clientRequestId === request_id && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id; // 通常 clientRequestId 和 agentRequestId 相同，但这里做了区分
    } else if (request_id && state.currentRequestLogCollection && !state.currentRequestLogCollection.agentRequestId) {
        // 如果 clientRequestId 不匹配，但 agentRequestId 尚未设置，也尝试设置 (预防万一)
        state.currentRequestLogCollection.agentRequestId = request_id;
    }


    if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
}

function handleLlmCommStatus(msg) {
    const { llm_phase, status, message: msgText, details, request_id } = msg; // 【老板，新增！】获取 request_id
    let logIconClass = 'fas fa-brain log-processing';
    let logItemClasses = `type-llm_communication_status phase-${llm_phase} status-${status}`;

    if (status === 'started') logIconClass = 'fas fa-brain fa-beat-fade log-processing';
    else if (status === 'completed') logIconClass = 'fas fa-check log-success';
    else if (status === 'error') logIconClass = 'fas fa-bolt log-error';

    appendLogItem(msgText, logIconClass, logItemClasses, details);
    
    // 【老板，新增！】更新 agentRequestId
    if (request_id && state.currentRequestLogCollection && state.currentRequestLogCollection.clientRequestId === request_id && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    } else if (request_id && state.currentRequestLogCollection && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    }

    if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
}

function handleThinkingLog(msg) {
    const { stage, content, llm_interaction_id, request_id } = msg; // 【老板，新增！】获取 request_id
    if (content) {
        state.lastResponseThinking = content;
    }
    if (state.showLogBubblesThink) {
        const thinkLabel = `AI思维墨迹 (${stage.replace(/_/g, ' ').toUpperCase()})`;
        appendLogItemWithThink(thinkLabel, 'fas fa-lightbulb log-think', `type-thinking_log stage-${stage} llm-id-${llm_interaction_id}`, content, "详细思考投影:");
    } else {
        appendLogItem(`思维墨迹收到 (${stage}, LLM_ID: ${llm_interaction_id}) - ${String(content).substring(0, 80)}...`, 'fas fa-comment-dots log-muted', `type-thinking_log stage-${stage} muted`);
    }
    
    // 【老板，新增！】更新 agentRequestId
    if (request_id && state.currentRequestLogCollection && state.currentRequestLogCollection.clientRequestId === request_id && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    } else if (request_id && state.currentRequestLogCollection && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    }

    if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
}

function handlePlanDetails(msg) {
    const { plan, request_id, llm_interaction_id } = msg; // 【老板，新增！】获取 request_id 和 llm_interaction_id
    state.pendingToolCalls = {}; 
    if (Array.isArray(plan)) { 
        plan.forEach(toolCall => {
            const toolCallId = toolCall.toolCallId || toolCall.tool_call_id; 
            const toolName = toolCall.toolName || toolCall.tool_name;     
            const toolArguments = toolCall.toolArguments || toolCall.tool_arguments || {}; 
            const uiHints = toolCall.uiHints || toolCall.ui_hints || {};
            const order = toolCall.order;

            if (!toolCallId || !toolName) {
                  console.warn("Plan details missing essential fields (toolCallId/tool_call_id or toolName/tool_name), skipping:", toolCall);
                  appendLogItem(
                      `收到无效计划项 (缺少ID或名称). Original: ${JSON.stringify(toolCall).substring(0,100)}...`, 
                      'fas fa-exclamation-circle log-warning',
                      'type-plan_details status-invalid',
                      toolCall 
                  );
                  return; 
             }
            state.pendingToolCalls[toolCallId] = {
                name: toolName, 
                args_summary: summarizeArguments(toolArguments), 
                ui_hints: uiHints, 
                order: order 
            };
            const displayName = uiHints.displayNameForTool || String(toolName).replace(/_tool$/, "").replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
            const logMessageText = `执行节点 #${order}: ${displayName} (ID: ${toolCallId}) - 状态: QUEUED`;
            const logItem = appendLogItem(
                logMessageText, 
                'fas fa-tasks log-info', 
                `type-plan_details tool-${toolName} status-pending tool-call-id-${toolCallId}`, 
                { arguments: toolArguments, tool_call_id: toolCallId, ui_hints: uiHints, llm_interaction_id_plan: llm_interaction_id } // 添加llm_interaction_id
            );
            if (logItem) logItem.dataset.toolCallId = toolCallId; 
        });
    } else {
        console.warn("Received plan_details message with non-array plan property:", plan);
        appendLogItem(
           `收到无效计划详情 (Plan不是数组).`,
           'fas fa-exclamation-circle log-error',
           'type-plan_details status-invalid',
           { raw_plan_data: plan, llm_interaction_id_plan: llm_interaction_id }
       );
    }
    
    // 【老板，新增！】更新 agentRequestId
    if (request_id && state.currentRequestLogCollection && state.currentRequestLogCollection.clientRequestId === request_id && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    } else if (request_id && state.currentRequestLogCollection && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    }

    showProcessLogSidebar(true); 
}


function handleToolStatusUpdate(msg) {
    const { tool_call_id, tool_name, status, message: msgText, details, request_id } = msg; // 【老板，新增！】获取 request_id
    if (!tool_call_id || !tool_name || status === undefined || msgText === undefined) {
         console.warn("Received invalid tool_status_update message (missing essential fields):", msg);
          appendLogItem(
             `收到无效工具状态更新 (缺少ID,名称,状态或消息).`,
             'fas fa-exclamation-circle log-error',
             'type-tool_status_update status-invalid',
             msg
         );
        return;
    }

    let logIconClass = 'fas fa-cog log-info';
    let itemStatusClass = `status-${status}`;

    if (status === 'running') logIconClass = 'fas fa-cogs fa-spin log-processing';
    else if (status === 'retrying') logIconClass = 'fas fa-history fa-spin log-processing';
    else if (status === 'succeeded') logIconClass = 'fas fa-check-double log-success';
    else if (status === 'failed') logIconClass = 'fas fa-times-circle log-error';
    else if (status === 'aborted_due_to_previous_failure') {
        logIconClass = 'fas fa-ban log-warning';
        itemStatusClass = 'status-aborted';
    }

    const pendingToolInfo = state.pendingToolCalls[tool_call_id];
    const displayName = pendingToolInfo?.ui_hints?.displayNameForTool || String(tool_name).replace(/_tool$/, "").replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
    let fullLogMessage = `工具模块: ${displayName} (ID: ${tool_call_id}) - ${status.replace(/_/g, ' ').toUpperCase()}: ${msgText}`;

    let existingLogItem = dom.processLogSidebarContent.querySelector(`.log-item[data-tool-call-id="${tool_call_id}"]`);

    if (existingLogItem) {
        existingLogItem.className = `log-item animate__animated type-tool_status_update tool-${tool_name} ${itemStatusClass} tool-call-id-${tool_call_id}`; 
        existingLogItem.dataset.toolCallId = tool_call_id; 
        existingLogItem.style.setProperty('--animate-duration', '0.5s');

        const iconEl = existingLogItem.querySelector('i:first-child');
        if (iconEl) iconEl.className = logIconClass;

        const messageEl = existingLogItem.querySelector('.log-item-message');
        if (messageEl) messageEl.textContent = fullLogMessage;
        
        const contentAreaWrapper = existingLogItem.querySelector('.log-item-content-area');
        if (contentAreaWrapper) {
             let detailsEl = contentAreaWrapper.querySelector('.log-item-details') || contentAreaWrapper.querySelector('.log-think-content');
             if (details && Object.keys(details).length > 0) {
                 if (!detailsEl) {
                      detailsEl = document.createElement('div');
                      contentAreaWrapper.appendChild(detailsEl);
                 }
                 detailsEl.classList.remove('log-think-content'); 
                 detailsEl.classList.add('log-item-details');

                 const { type, stage, status: parsedStatus } = parseItemClasses(existingLogItem.className);
                 detailsEl.innerHTML = formatLogDetails(details, type, stage, parsedStatus) || ''; 
                 if (!detailsEl.innerHTML) { 
                      detailsEl.innerHTML = `<span class="log-detail-item"><strong class="log-detail-key">详细信息:</strong> <span class="log-detail-value">(无或格式化失败)</span></span>`;
                      try {
                          let rawDetailsStr = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details);
                          detailsEl.innerHTML += `<pre class="log-detail-raw-json error"><code>${rawDetailsStr.replace(/</g, "<").replace(/>/g, ">")}<br>(原始数据)</code></pre>`;
                      } catch (e_raw) { /* Ignore */ }
                  }
             } else if (detailsEl) {
                 detailsEl.remove();
             }
        } else {
             console.error("Tool status update: Cannot find content area wrapper for details update.");
        }

        existingLogItem.classList.remove('animate__flash', 'animate__headShake', 'animate__pulse');
        if (status === 'failed') existingLogItem.classList.add('animate__headShake');
        else if (status === 'succeeded') existingLogItem.classList.add('animate__pulse');
        else existingLogItem.classList.add('animate__flash');

    } else {
        const logItemDiv = appendLogItem(fullLogMessage, logIconClass, `type-tool_status_update tool-${tool_name} ${itemStatusClass} tool-call-id-${tool_call_id}`, details);
        if (logItemDiv) logItemDiv.dataset.toolCallId = tool_call_id; 

        if (logItemDiv) { 
             logItemDiv.classList.remove('animate__fadeInUp'); 
             logItemDiv.classList.add('animate__animated'); 
             if (status === 'failed') logItemDiv.classList.add('animate__headShake');
             else if (status === 'succeeded') logItemDiv.classList.add('animate__pulse');
             else logItemDiv.classList.add('animate__flash');
            logItemDiv.style.setProperty('--animate-duration', '0.5s');
        }
    }
    
    // 【老板，新增！】更新 agentRequestId
    if (request_id && state.currentRequestLogCollection && state.currentRequestLogCollection.clientRequestId === request_id && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    } else if (request_id && state.currentRequestLogCollection && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    }


    if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);

    if (status === 'succeeded' || status === 'failed' || status === 'aborted_due_to_previous_failure') {
        if (state.pendingToolCalls[tool_call_id]) {
            delete state.pendingToolCalls[tool_call_id];
        }
    }
}

function handleInterimResponse(msg) {
    const { content, llm_interaction_id, request_id } = msg; // 【老板，新增！】获取 request_id
    appendLogItem(
        `AI意图墨迹: "${String(content).substring(0, 180)}${String(content).length > 180 ? '...' : ''}"`,
        'fas fa-feather-alt log-info',
        'type-agent_intention',
        { llm_interaction_id: llm_interaction_id, full_content: content }
    );

    // 【老板，新增！】更新 agentRequestId
    if (request_id && state.currentRequestLogCollection && state.currentRequestLogCollection.clientRequestId === request_id && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    } else if (request_id && state.currentRequestLogCollection && !state.currentRequestLogCollection.agentRequestId) {
        state.currentRequestLogCollection.agentRequestId = request_id;
    }

    if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
}

function handleFinalResponse(msg) {
    hideTypingIndicator();
    setLoadingState(false);
    
    const { content, llm_interaction_id, request_id } = msg; // 【老板，新增！】获取 request_id (这通常是Agent后端的 request_id)
    const finalCamelCaseJson = msg.final_camelcase_json_if_success || msg.final_v1_3_2_camelcase_json_if_success;


    let thinkingForBubble = null;
    let actualContentForBubble = content;

    if (finalCamelCaseJson && typeof finalCamelCaseJson === 'object' && finalCamelCaseJson.status === 'success') {
        if (finalCamelCaseJson.thoughtProcess) {
            thinkingForBubble = finalCamelCaseJson.thoughtProcess;
        }
        if (finalCamelCaseJson.decision && typeof finalCamelCaseJson.decision === 'object' &&
            finalCamelCaseJson.decision.responseToUser && typeof finalCamelCaseJson.decision.responseToUser === 'object' &&
            finalCamelCaseJson.decision.responseToUser.content !== undefined
        ) {
            actualContentForBubble = finalCamelCaseJson.decision.responseToUser.content || "";

            const suggestions = finalCamelCaseJson.decision.responseToUser.suggestionsForNextSteps;
            if (suggestions && Array.isArray(suggestions) && suggestions.length > 0) {
                let suggestionsText = "\n\n<div class=\"final-response-suggestions\"><strong>下一步行动投影:</strong><ul>";
                suggestions.forEach(sugg => {
                    if (sugg.textForUser) {
                        const escapedMessage = String(sugg.textForUser).replace(/"/g, '"'); 
                        const escapedTextForUser = String(sugg.textForUser).replace(/</g, "<").replace(/>/g, ">");
                        suggestionsText += `<li><a href="#" class="quick-action-btn lumina-button" data-message="${escapedMessage}"><i class="fas fa-arrow-right"></i> ${escapedTextForUser}</a></li>`;
                    }
                });
                suggestionsText += "</ul></div>";
                actualContentForBubble += suggestionsText;
                appendMessage(actualContentForBubble, 'agent', true, thinkingForBubble, false, [], null, state.currentClientRequestId, request_id);
            } else {
                if (!actualContentForBubble.trim()) {
                     actualContentForBubble = "(Agent返回的回复内容为空)";
                     console.warn("Final response JSON has empty content and no suggestions. Using fallback message.");
                }
                appendMessage(actualContentForBubble, 'agent', false, thinkingForBubble, false, [], null, state.currentClientRequestId, request_id);
            }
        } else {
            console.warn("Final response JSON structure missing decision.responseToUser.content or nested objects are invalid. Using fallback content.", finalCamelCaseJson);
            appendMessage(content || "(Agent返回的原始内容为空)", 'agent', false, thinkingForBubble, false, [], "ContentMissingIn_V1_PCP_JSON_Or_Structure_Invalid", state.currentClientRequestId, request_id);
            actualContentForBubble = content || "(Agent返回的原始内容为空)";
        }
    } else {
        thinkingForBubble = state.lastResponseThinking;
        const reasonForFallback = finalCamelCaseJson
            ? `JSON status is not 'success' (is '${finalCamelCaseJson.status}') or JSON is not an object (is '${typeof finalCamelCaseJson}').`
            : "final_camelcase_json_if_success (or versioned key) is missing.";
        console.warn(`Final response: ${reasonForFallback} Using fallback content and cached thinking. Raw message content: "${content}"`, finalCamelCaseJson);
        appendMessage(content || "(Agent返回的原始内容为空)", 'agent', false, thinkingForBubble, false, [], `ErrorResponseOrNo_V1_PCP_JSON_Reason:_${reasonForFallback.replace(/\s/g, '_').substring(0, 50)}`, state.currentClientRequestId, request_id);
        actualContentForBubble = content || "(Agent返回的原始内容为空)";
    }

    addMessageToCurrentSession({ 
        content: actualContentForBubble,
        sender: 'agent',
        timestamp: Date.now(),
        isHTML: (actualContentForBubble.includes('<div class="final-response-suggestions">')),
        rawResponseV1_PCP_CamelCase: finalCamelCaseJson, 
        thinking: thinkingForBubble,
        clientRequestId: state.currentClientRequestId, // 【老板，新增！】存储 clientRequestId
        agentRequestId: request_id // 【老板，新增！】存储 agentRequestId
    });
    
    // 【老板，关键！】当收到最终回复时，将当前请求的日志集合移到会话的永久日志中
    if (state.currentRequestLogCollection) {
        if (state.currentRequestLogCollection.clientRequestId === state.currentClientRequestId) { // 确保是同一个请求
            state.currentRequestLogCollection.finalStatus = (finalCamelCaseJson && finalCamelCaseJson.status === 'success') ? 'success' : 'failure';
            // 如果 agentRequestId 之前没有通过其他status消息获得，尝试从 final_response 的 request_id 获取
            if (!state.currentRequestLogCollection.agentRequestId && request_id) {
                state.currentRequestLogCollection.agentRequestId = request_id;
            }
            if (state.sessions[state.currentSessionId] && state.sessions[state.currentSessionId].executionLogs) {
                state.sessions[state.currentSessionId].executionLogs.push(state.currentRequestLogCollection);
                saveSessionData(); // 保存会话数据，现在包含了这次的执行日志
            }
        } else {
            console.warn("currentRequestLogCollection 的 clientRequestId 与当前的 state.currentClientRequestId 不匹配，日志可能未正确保存。");
        }
        state.currentRequestLogCollection = null; // 清空，为下一个请求做准备
    }


    state.lastResponseThinking = null;
    state.currentClientRequestId = null; // 【老板，重要！】在最终响应后清空当前客户端请求ID
    state.pendingToolCalls = {};


    if (state.sessions[state.currentSessionId]) {
        state.sessions[state.currentSessionId].lastActivity = Date.now();
    }
    saveSessionData(); 
    renderSessionList(); 

    const llmIdForLog = (finalCamelCaseJson && finalCamelCaseJson.llmInteractionId) ? finalCamelCaseJson.llmInteractionId : (llm_interaction_id || 'N/A_Final');
    appendLogItem(`AI最终回复已渲染 (LLM_ID: ${llmIdForLog})`, 'fas fa-flag-checkered log-success', 'type-final_response',
        finalCamelCaseJson ? { summary: (actualContentForBubble.includes('<div class="final-response-suggestions">') ? actualContentForBubble.substring(0, 120).split('<br>')[0] : actualContentForBubble.substring(0, 120)) + "...", raw_response_v1_pcp: finalCamelCaseJson } : { error_details: "响应生成指示失败或缺少有效JSON.", fallback_content_preview: (content || "(空)").substring(0,120) + "..."}
    );
    if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
    else if (state.isProcessLogSidebarCollapsed) showProcessLogSidebar(false);
    else showProcessLogSidebar(true);
}

// ==========================================================================
// [ END OF FILE core/websocket_manager.js ]
// ==========================================================================