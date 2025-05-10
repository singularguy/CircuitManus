// 启用 JavaScript 严格模式，有助于捕捉常见错误，提高代码质量
"use strict";

// 当整个 HTML 文档加载完成并解析完毕后执行回调函数
document.addEventListener('DOMContentLoaded', () => {
    // ======== DOM 元素获取 (集中管理，方便维护) ========
    const dom = {
        // 加载动画相关
        loader: document.getElementById('loader'),
        loaderProgress: document.querySelector('.loader-progress'),
        mainContainer: document.getElementById('main-container'),

        // 聊天核心区域
        chatBox: document.getElementById('chat-box'),
        userInput: document.getElementById('user-input'),
        sendButton: document.getElementById('send-button'),
        sendIcon: document.querySelector('.send-icon'),
        sendLoadingIcon: document.querySelector('.send-loading-icon'),

        // 头部与主题
        themeToggleButton: document.getElementById('theme-toggle'),
        themeToggleIcon: document.querySelector('#theme-toggle i'),
        clearChatButton: document.getElementById('clear-chat'),
        manageSessionsToggle: document.getElementById('manage-sessions-toggle'),
        toggleProcessLogVisibilityButton: document.getElementById('toggle-process-log-visibility'), // New button

        // 侧边栏与会话管理
        sidebar: document.getElementById('sidebar'),
        sidebarButtons: document.querySelectorAll('.sidebar-button'),
        sessionManager: document.getElementById('session-manager'),
        sessionManagerToggle: document.getElementById('session-manager-toggle'),
        sessionListContainer: document.getElementById('session-list-container'),
        sessionList: document.getElementById('session-list'),
        createNewSessionButton: document.getElementById('create-new-session'),
        currentSessionNameDisplay: document.getElementById('current-session-name'),
        editSessionNameButton: document.getElementById('edit-session-name-btn'),

        // 输入区域与文件上传
        attachButton: document.getElementById('attach-button'),
        micButton: document.getElementById('mic-button'),
        charCounter: document.getElementById('char-counter'),
        fileInput: document.getElementById('file-input'),
        filePreviewArea: document.getElementById('file-preview'),
        filePreviewContent: document.getElementById('file-preview-content'),
        closeFilePreviewButton: document.getElementById('close-preview'),

        // Toast 通知
        toastContainer: document.getElementById('toast-container'),

        // Agent 处理过程日志区域
        processLogContainer: document.getElementById('process-log-container'),
        processLogContent: document.getElementById('process-log-content'),
        toggleProcessLogCollapseButton: document.getElementById('toggle-process-log-collapse'), // Renamed for clarity

        // 设置模态框相关
        settingsModal: document.getElementById('settings-modal'),
        openSettingsButton: document.querySelector('.sidebar-button[data-mode="settings"]'),
        closeSettingsButton: document.getElementById('close-settings'),
        themeSelect: document.getElementById('theme-select'),
        fontSizeInput: document.getElementById('font-size'),
        fontSizeValue: document.getElementById('font-size-value'),
        animationLevelSelect: document.getElementById('animation-level'),
        autoScrollToggle: document.getElementById('auto-scroll'),
        soundEnabledToggle: document.getElementById('sound-enabled'),
        showChatBubblesThinkToggle: document.getElementById('show-chat-bubbles-think'), // Specific for chat
        showLogBubblesThinkToggle: document.getElementById('show-log-bubbles-think'), // Specific for log
        autoSubmitQuickActionsToggle: document.getElementById('auto-submit-quick-actions'), // New setting
        resetSettingsButton: document.getElementById('reset-settings'),
        saveSettingsButton: document.getElementById('save-settings'),
    };

    // ======== 应用状态与配置 ========
    const APP_PREFIX = 'IDTAgentPro_v8.2_PJS_'; // Updated prefix for new version
    let state = {
        sessions: {},
        currentSessionId: null,
        currentTheme: 'auto',
        autoScroll: true,
        soundEnabled: false,
        showChatBubblesThink: true, // Controls if thinking appears in chat bubble
        showLogBubblesThink: true,  // Controls if thinking appears in process log items
        animationLevel: 'full',
        currentMode: 'chat', // Default mode
        uploadedFiles: [], // For file attachments (conceptual)
        isAgentTyping: false,
        isLoading: false, // General loading state for send button
        isSidebarExpanded: window.innerWidth > 768, // Default based on screen width
        isSessionManagerCollapsed: false,
        isProcessLogVisible: false, // New state for overall visibility of process log
        isProcessLogCollapsed: true, // Default process log to collapsed
        maxInputChars: 4000, // Increased max input characters
        currentClientRequestId: null, // Stores the ID of the currently active user request
        lastResponseThinking: null, // Stores the thinking process string for the latest agent response
        autoSubmitQuickActions: true, // New setting
        pendingToolCalls: {} // Stores tool_call_id -> {name, args_summary, ui_hints} for rendering in log
    };

    // ======== WebSocket 相关 ========
    let websocket = null;
    const websocketUrl = `ws://${window.location.host}/ws/chat`;
    let wsReconnectAttempts = 0;
    const MAX_WS_RECONNECT_ATTEMPTS = 5;
    const WS_RECONNECT_INTERVAL = 3000; // 3 seconds

    function connectWebSocket() {
        if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
            console.log("WebSocket is already connected or connecting.");
            return;
        }
        console.log(`Attempting to connect WebSocket (Attempt ${wsReconnectAttempts + 1}): ${websocketUrl}`);
        if (dom.loader && wsReconnectAttempts === 0) { // Only show loader fully on first connect attempt
            const loadingText = dom.loader.querySelector('.loading-text');
            if (loadingText) loadingText.textContent = "Establishing secure link...";
        }

        websocket = new WebSocket(websocketUrl);

        websocket.onopen = (event) => {
            console.log("WebSocket connection established", event);
            wsReconnectAttempts = 0; // Reset attempts on successful connection
            showToast("Communication link active.", "success", 3000);
            // Send init message with current session ID
            sendWebSocketMessage({
                type: 'init',
                session_id: state.currentSessionId // Send current, could be null if first load
            });
        };

        websocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                // Log every message from backend for easier debugging
                console.log("WS RX:", message);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error("Failed to parse WebSocket message:", e, "Raw data:", event.data);
                showToast("Received invalid data format from server.", "error");
            }
        };

        websocket.onerror = (event) => {
            console.error("WebSocket error:", event);
            // Don't show toast here, onclose will handle it with more details
        };

        websocket.onclose = (event) => {
            console.log("WebSocket connection closed:", event);
            hideTypingIndicator();
            setLoadingState(false);
            websocket = null; // Clear the instance

            const reason = event.reason ? `Reason: ${event.reason}` : (event.wasClean ? 'Connection closed cleanly.' : 'Connection lost unexpectedly.');
            const codeMsg = `(Code: ${event.code})`;

            if (!event.wasClean && wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                wsReconnectAttempts++;
                showToast(`Link lost. Attempting to re-establish (${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})... ${codeMsg}`, "warning", WS_RECONNECT_INTERVAL);
                setTimeout(connectWebSocket, WS_RECONNECT_INTERVAL);
            } else if (!event.wasClean) {
                showToast(`Communication link permanently lost after ${MAX_WS_RECONNECT_ATTEMPTS} attempts. Please refresh. ${codeMsg} ${reason}`, "error", 10000);
                if (dom.loader) { // Show loader with error message if connection totally fails
                    const loadingText = dom.loader.querySelector('.loading-text');
                    if (loadingText) loadingText.textContent = "Connection Error. Please refresh.";
                    dom.loaderProgress.style.width = '0%';
                    dom.loader.classList.remove('hidden');
                }
            } else { // Clean close
                showToast(`Communication link closed. ${codeMsg} ${reason}`, "info", 5000);
            }
        };
    }

    function sendWebSocketMessage(message) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            const messageStr = JSON.stringify(message);
            console.log("WS TX:", message); // Log before sending
            websocket.send(messageStr);
        } else {
            console.error("WebSocket connection not open. Cannot send message:", message);
            showToast("Communication link not active. Please wait or try reconnecting.", "warning");
            if (!websocket || websocket.readyState === WebSocket.CLOSED || websocket.readyState === WebSocket.CLOSING) {
                // Only try to reconnect if fully closed or closing, not if just connecting
                if (wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                    connectWebSocket();
                } else {
                    showToast("Cannot send: Max reconnection attempts reached. Please refresh.", "error");
                }
            }
        }
    }

    // --- Message Handling ---
    function handleWebSocketMessage(message) {
        // Validate if the message is for the current client_request_id if applicable
        // For now, assume all messages for this websocket are relevant if session matches
        // (Backend should echo client_request_id if it's used for this)

        switch (message.type) {
            case 'init_success':
                state.currentSessionId = message.session_id; // Backend confirms/assigns session_id
                localStorage.setItem(APP_PREFIX + 'lastSessionId', state.currentSessionId);

                const agentStatusMessage = message.agent_available === false
                    ? 'Agent core module not loaded. Functionality limited.'
                    : 'Communication link established. Agent ready!';
                const agentStatusType = message.agent_available === false ? 'warning' : 'success';
                showToast(agentStatusMessage, agentStatusType, message.agent_available ? 4000 : 7000);

                // Ensure local session state exists or is created
                if (!state.sessions[state.currentSessionId]) {
                    const now = Date.now();
                    state.sessions[state.currentSessionId] = {
                        id: state.currentSessionId,
                        name: `Session ${Object.keys(state.sessions).length + 1}`, // Generic name
                        messages: [],
                        createdAt: now,
                        lastActivity: now,
                    };
                    saveSessions(); // Save the new session stub
                }
                initializeCurrentSessionUI(true); // Refresh UI for the current session

                if (dom.loader) dom.loader.classList.add('hidden');
                if (dom.mainContainer) dom.mainContainer.classList.add('loaded');
                updateSidebarState(state.isSidebarExpanded, true);
                updateSessionManagerState(state.isSessionManagerCollapsed, true);
                break;

            case 'init_error':
                showToast(`Agent initialization failed: ${message.message}`, 'error', 10000);
                if (dom.loader) dom.loader.classList.add('hidden');
                if (dom.mainContainer) dom.mainContainer.classList.add('loaded');
                if (message.agent_available === false) {
                    appendMessage("Apologies, the Agent's core module failed to load. I am unable to process your requests at this time.", 'error-system', false, null, false, [], "System Error");
                }
                setLoadingState(false);
                break;

            case 'error': // General server-side error unrelated to a specific agent process
                console.error("Server-reported error:", message);
                showToast(`Server error: ${message.message}`, 'error', 6000);
                if (message.details) {
                    appendMessage(`Server error (${message.message}): ${message.details}`, 'error-system', false, null, false, [], "Server Error");
                }
                setLoadingState(false); // Ensure loading state is reset
                break;

            // Agent Process Callbacks (V8.1.1 structure)
            case 'general_status':
                handleGeneralStatus(message);
                break;
            case 'llm_communication_status':
                handleLlmCommStatus(message);
                break;
            case 'thinking_log':
                handleThinkingLog(message);
                break;
            case 'plan_details':
                handlePlanDetails(message);
                break;
            case 'tool_status_update':
                handleToolStatusUpdate(message);
                break;
            case 'interim_response':
                handleInterimResponse(message);
                break;
            case 'final_response':
                handleFinalResponse(message);
                break;

            default:
                console.warn("Received unknown WebSocket message type:", message.type, message);
        }
    }

    function handleGeneralStatus(msg) {
        const { stage, status, message: msgText, details, request_id } = msg;
        // Ensure this status is for the current client request if client_request_id is implemented and matched
        // if (state.currentClientRequestId && request_id !== state.currentClientRequestId) return;

        let logIconClass = 'fas fa-info-circle log-info'; // Default
        let logItemClasses = `type-general_status stage-${stage} status-${status}`;

        if (status === 'started' || status === 'llm_retry_needed' || status === 'llm_error_retrying') logIconClass = 'fas fa-spinner fa-spin log-info';
        else if (status === 'completed' || status === 'received' || status === 'completed_and_validated') logIconClass = 'fas fa-check-circle log-success';
        else if (status === 'error' || status === 'failed' || status === 'failed_after_llm_retries' || status === 'tool_failure_detected') {
            logIconClass = 'fas fa-times-circle log-error';
        }
        else if (status === 'ignored') logIconClass = 'fas fa-eye-slash log-muted';

        let fullLogMessage = msgText;
        // Details will be formatted by appendLogItem, so no need to manually append to fullLogMessage here
        // if (details && Object.keys(details).length > 0) { ... }

        appendLogItem(fullLogMessage, logIconClass, logItemClasses, details);
        if (state.isProcessLogVisible) showProcessLog(false); // Ensure log is visible if not already
    }

    function handleLlmCommStatus(msg) {
        const { llm_phase, status, message: msgText, details, request_id } = msg;
        // if (state.currentClientRequestId && request_id !== state.currentClientRequestId) return;

        let logIconClass = 'fas fa-brain log-info';
        let logItemClasses = `type-llm_communication_status phase-${llm_phase} status-${status}`;

        if (status === 'started') logIconClass = 'fas fa-brain fa-fade log-info'; // Different animation for LLM thinking
        else if (status === 'completed') logIconClass = 'fas fa-check log-success';
        else if (status === 'error') logIconClass = 'fas fa-exclamation-triangle log-error';

        appendLogItem(msgText, logIconClass, logItemClasses, details);
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handleThinkingLog(msg) {
        const { stage, content, llm_interaction_id, request_id } = msg;
        // if (state.currentClientRequestId && request_id !== state.currentClientRequestId) return;

        // If it's for the response generation stage, cache it for the chat bubble
        if (stage === 'response_generation' || stage === 'final_summary') {
            state.lastResponseThinking = content;
        }

        if (state.showLogBubblesThink) { // Check setting for process log
            const thinkLabel = `Agent Thinking (${stage.replace('_', ' ')})`;
            appendLogItemWithThink(thinkLabel, 'fas fa-comment-dots log-think', `type-thinking_log stage-${stage}`, content, "Detailed Thought Process:");
        } else {
            appendLogItem(`Thinking log received (${stage}) - ${content.substring(0, 70)}...`, 'fas fa-comment-dots log-muted', `type-thinking_log stage-${stage} muted`);
        }
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handlePlanDetails(msg) {
        const { plan, llm_interaction_id, request_id } = msg;
        // if (state.currentClientRequestId && request_id !== state.currentClientRequestId) return;

        state.pendingToolCalls = {}; // Clear previous pending calls for this request
        plan.forEach(toolCall => {
            state.pendingToolCalls[toolCall.tool_call_id] = {
                name: toolCall.tool_name,
                args_summary: summarizeArguments(toolCall.tool_arguments),
                ui_hints: toolCall.ui_hints || {},
                order: toolCall.order
            };
            const displayName = toolCall.ui_hints?.display_name_for_tool || toolCall.tool_name;
            appendLogItem(
                `Plan item #${toolCall.order}: ${displayName} (ID: ${toolCall.tool_call_id}) - Status: Pending`,
                'fas fa-list-check log-info',
                `type-plan_details tool-${toolCall.tool_name} status-pending`,
                { arguments: toolCall.tool_arguments, tool_call_id: toolCall.tool_call_id } // Pass full details for formatting
            );
        });
        if (state.isProcessLogVisible) showProcessLog(true); // Expand if collapsed, ensure visible
    }

    function handleToolStatusUpdate(msg) {
        const { tool_call_id, tool_name, tool_arguments_summary_str, status, message: msgText, details, request_id } = msg;
        // if (state.currentClientRequestId && request_id !== state.currentClientRequestId) return;

        let logIconClass = 'fas fa-cog log-info';
        if (status === 'running') logIconClass = 'fas fa-cog fa-spin log-info';
        else if (status === 'retrying') logIconClass = 'fas fa-history log-info';
        else if (status === 'succeeded') logIconClass = 'fas fa-check-circle log-success';
        else if (status === 'failed') logIconClass = 'fas fa-times-circle log-error';
        else if (status === 'aborted_due_to_previous_failure') logIconClass = 'fas fa-ban log-warning';

        const pendingToolInfo = state.pendingToolCalls[tool_call_id];
        const displayName = pendingToolInfo?.ui_hints?.display_name_for_tool || tool_name;

        let fullLogMessage = `Tool: ${displayName} (ID: ${tool_call_id}) - ${status.replace(/_/g, ' ')}: ${msgText}`;

        appendLogItem(fullLogMessage, logIconClass, `type-tool_status_update tool-${tool_name} status-${status}`, details);
        if (state.isProcessLogVisible) showProcessLog(false);

        if (status === 'succeeded' || status === 'failed' || status === 'aborted_due_to_previous_failure') {
            if (state.pendingToolCalls[tool_call_id]) {
                delete state.pendingToolCalls[tool_call_id]; // Remove from pending
            }
        }
    }

    function handleInterimResponse(msg) {
        const { content, llm_interaction_id, request_id } = msg;
        // if (state.currentClientRequestId && request_id !== state.currentClientRequestId) return;

        // Display as a temporary/muted agent message in chat box
        appendMessage(content, 'agent-interim', false, null, false, [], "Interim Update"); // New sender type for styling

        // Also log it
        appendLogItem(`Agent interim update: "${content.substring(0, 100)}..."`, 'fas fa-hourglass-half log-muted', 'type-interim_response');
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handleFinalResponse(msg) {
        hideTypingIndicator();
        setLoadingState(false);
        state.currentClientRequestId = null; // Clear current request ID after final response
        state.pendingToolCalls = {}; // Clear any pending tool calls display

        const { content, llm_interaction_id, final_v8_1_json_if_success, request_id } = msg;
        // if (state.currentClientRequestId && request_id !== state.currentClientRequestId) {
        // This check might be problematic if currentClientRequestId was cleared too soon
        // For final_response, assume it's for the last initiated request.
        // }

        appendMessage(content, 'agent', false, state.lastResponseThinking, false, [], final_v8_1_json_if_success ? null : "ErrorResponse");

        addMessageToCurrentSession({
            content: content,
            sender: 'agent',
            timestamp: Date.now(),
            isHTML: false, // Assuming content is plain text, Markdown handled by appendMessage
            rawResponseV8_1: final_v8_1_json_if_success, // Store the full V8.1 JSON if successful
            thinking: state.lastResponseThinking,
        });
        state.lastResponseThinking = null; // Clear after use

        if (state.sessions[state.currentSessionId]) {
            state.sessions[state.currentSessionId].lastActivity = Date.now();
        }
        saveSessions();
        renderSessionList();

        appendLogItem(`Agent final response delivered (LLM_ID: ${llm_interaction_id || 'N/A'})`, 'fas fa-flag-checkered log-success', 'type-final_response');
        if (state.isProcessLogVisible) showProcessLog(true); // Expand to show final log state
    }


    function setLoadingState(isLoading) {
        state.isLoading = isLoading;
        dom.sendButton.disabled = isLoading;
        dom.userInput.disabled = isLoading; // Disable input while loading
        dom.sendIcon.style.display = isLoading ? 'none' : 'inline-block';
        dom.sendLoadingIcon.style.display = isLoading ? 'inline-block' : 'none';
        if (isLoading) {
            dom.sendButton.title = "Processing...";
        } else {
            dom.sendButton.title = "Send message";
        }
    }

    function summarizeArguments(argsObj) {
        if (!argsObj || typeof argsObj !== 'object' || Object.keys(argsObj).length === 0) {
            return "(No args)";
        }
        try {
            return JSON.stringify(argsObj, (key, value) => {
                if (typeof value === 'string' && value.length > 30) {
                    return value.substring(0, 27) + "...";
                }
                return value;
            }).substring(0, 150); // Max length for summary
        } catch (e) {
            return "(Error summarizing args)";
        }
    }

    // Helper to parse itemClasses string into type, stage, status
    function parseItemClasses(itemClassesStr) {
        const classes = itemClassesStr ? itemClassesStr.split(' ') : [];
        const parsed = { type: null, stage: null, status: null };
        classes.forEach(cls => {
            if (cls.startsWith('type-')) parsed.type = cls.substring(5);
            else if (cls.startsWith('stage-')) parsed.stage = cls.substring(6);
            else if (cls.startsWith('status-')) parsed.status = cls.substring(7);
            else if (cls.startsWith('phase-')) parsed.stage = cls.substring(6); // llm_comm uses phase (treat as stage)
        });
        return parsed;
    }


    // Enhanced formatter for log item details
    function formatLogDetails(details, type, stage, status) {
        let html = '';

        // Helper to add a key-value pair to the HTML output
        const addDetailKeyValue = (key, value, indentLevel = 0) => {
            const sanitizedValue = String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
            const paddingLeftStyle = `padding-left: ${indentLevel * 10}px;`;
            // Uppercase first letter of each word in key, replace underscores with spaces
            const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
            return `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>${formattedKey}:</strong> <span>${sanitizedValue}</span></div>`;
        };

        // Recursive helper to format complex objects
        const formatRecursive = (obj, currentType, currentStage, currentStatus, indentLevel = 0) => {
            let partHtml = '';
            for (const key in obj) {
                if (Object.prototype.hasOwnProperty.call(obj, key)) {
                    const value = obj[key];
                    const displayKey = key.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                    const paddingLeftStyle = `padding-left: ${indentLevel * 10}px;`;

                    // Skip tool_call_id for plan_details as it's usually in the main message
                    if (currentType === 'plan_details' && key === 'tool_call_id') {
                        continue;
                    }

                    // Specific key handling (these are common patterns within details)
                    if (key === 'ui_hints' && typeof value === 'object' && value !== null) {
                        const dn = String(value.display_name_for_tool || 'N/A').replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        const ed = String(value.estimated_duration_category || 'N/A').replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>UI Hints:</strong> <span>Display Name: ${dn}, Estimated Duration: ${ed}</span></div>`;
                    } else if (key === 'result_data_preview' && typeof value === 'string') {
                        let previewContent = '';
                        try {
                            const parsedResult = JSON.parse(value);
                            let resultItems = [];
                            for (const resKey in parsedResult) {
                                resultItems.push(`${resKey}: ${String(parsedResult[resKey]).replace(/</g, "&lt;").replace(/>/g, "&gt;")}`);
                            }
                            previewContent = resultItems.join('; ');
                        } catch (e) {
                            previewContent = `(Raw Text) ${String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;")}`;
                        }
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>Result Preview:</strong> <span>${previewContent}</span></div>`;
                    } else if (currentType === 'plan_details' && key === 'arguments' && typeof value === 'object' && value !== null) {
                        let argItems = [];
                        for (const argKey in value) {
                            const formattedArgKey = argKey.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                            argItems.push(`<em>${formattedArgKey}</em>: ${String(value[argKey]).replace(/</g, "&lt;").replace(/>/g, "&gt;")}`);
                        }
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>Arguments:</strong> <span>${argItems.join('; ')}</span></div>`;
                    }
                    // Generic handling for other objects, arrays, or primitives
                    else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>${displayKey}:</strong></div>`;
                        partHtml += formatRecursive(value, currentType, currentStage, currentStatus, indentLevel + 1); // Recurse
                    } else if (Array.isArray(value)) {
                        const arrayItems = value.map(item => {
                            if (typeof item === 'object' && item !== null) return '(Object)'; // Simplified for arrays of objects
                            return String(item).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        });
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>${displayKey}:</strong> <span>[${arrayItems.join(', ')}]</span></div>`;
                    } else { // Simple key-value primitive
                        partHtml += addDetailKeyValue(key, value, indentLevel);
                    }
                }
            }
            return partHtml;
        };

        // Top-level specific handlers based on type, stage, and status
        if (type === 'general_status') {
            if (stage === 'user_instruction_received' && details.user_request_preview) {
                html += addDetailKeyValue('User Request Preview', details.user_request_preview);
            } else if (stage === 'planning_and_analysis' && status === 'started' && typeof details.attempt_number !== 'undefined') {
                html += addDetailKeyValue('Attempt', details.attempt_number);
                if (typeof details.max_replanning_attempts !== 'undefined') {
                    html += addDetailKeyValue('Max Replanning Attempts', details.max_replanning_attempts);
                }
            } else if (stage === 'planning_and_analysis' && status === 'completed_and_validated' && details.plan_llm_id) {
                html += addDetailKeyValue('Plan LLM ID', details.plan_llm_id);
            } else if (stage === 'tool_execution_phase' && status === 'started' && typeof details.tool_count !== 'undefined') {
                html += addDetailKeyValue('Tool Count', details.tool_count);
            } else if (stage === 'response_generation_phase' && status === 'started' && details.reason) {
                html += addDetailKeyValue('Reason', details.reason);
            } else {
                // Fallback to recursive formatter for other general_status details if no specific handler matched
                html = formatRecursive(details, type, stage, status, 0);
            }
        } else if (type === 'llm_communication_status') {
            if (typeof details.duration_seconds !== 'undefined') {
                html += addDetailKeyValue('Duration', `${parseFloat(details.duration_seconds).toFixed(2)}s`);
                const otherDetails = { ...details };
                delete otherDetails.duration_seconds;
                if (Object.keys(otherDetails).length > 0) {
                    html += formatRecursive(otherDetails, type, stage, status, 0);
                }
            } else {
                html = formatRecursive(details, type, stage, status, 0);
            }
        } else {
            // Default for plan_details, tool_status_update, and any other types: use the recursive formatter
            html = formatRecursive(details, type, stage, status, 0);
        }

        return html || null; // Return null if html is empty, to allow fallback to raw JSON
    }


    // Appends a log item to the process log area.
    // details can be an object that will be stringified or formatted for display.
    function appendLogItem(messageText, iconClass, itemClasses = '', details = null) {
        const logItemDiv = document.createElement('div');
        logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
        logItemDiv.style.setProperty('--animate-duration', '0.3s');
        if (itemClasses) logItemDiv.classList.add(...itemClasses.split(' '));

        const iconEl = document.createElement('i');
        iconEl.className = iconClass;

        const textWrapperEl = document.createElement('div');
        textWrapperEl.className = 'log-item-text-wrapper';

        const messageEl = document.createElement('span');
        messageEl.className = 'log-item-message';
        messageEl.textContent = messageText;
        textWrapperEl.appendChild(messageEl);

        if (details && Object.keys(details).length > 0) {
            const detailsEl = document.createElement('div');
            detailsEl.className = 'log-item-details';

            const { type, stage, status } = parseItemClasses(itemClasses);
            const formattedDetailsHtml = formatLogDetails(details, type, stage, status);

            if (formattedDetailsHtml) {
                detailsEl.innerHTML = formattedDetailsHtml;
            } else { // Fallback to raw JSON for unhandled or explicitly skipped cases
                try {
                    let detailsText;
                    if (typeof details === 'object') {
                        detailsText = JSON.stringify(details, null, 2);
                        // Ensure pre/code doesn't mess up flex layout of .log-item-details
                        detailsEl.innerHTML = `<pre><code>${detailsText.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>`;
                    } else {
                        detailsText = String(details);
                        detailsEl.textContent = detailsText; // Plain text if not object
                    }
                } catch (e) {
                    detailsEl.textContent = String(details); // Ultimate fallback
                }
            }
            textWrapperEl.appendChild(detailsEl);
        }

        logItemDiv.appendChild(iconEl);
        logItemDiv.appendChild(textWrapperEl);
        dom.processLogContent.appendChild(logItemDiv);
        scrollToProcessLogBottom();
    }


    // Appends a log item that specifically includes a "thought process" bubble.
    function appendLogItemWithThink(headerText, headerIconClass, itemClasses, thinkContent, thinkBubbleLabel = "Thought Process") {
        const logItemDiv = document.createElement('div');
        logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
        logItemDiv.style.setProperty('--animate-duration', '0.3s');
        if (itemClasses) logItemDiv.classList.add(...itemClasses.split(' '));

        const headerDiv = document.createElement('div'); // Wrapper for icon and header text
        headerDiv.style.display = 'flex';
        headerDiv.style.alignItems = 'center';
        headerDiv.style.gap = 'var(--spacing-unit)';

        const iconEl = document.createElement('i');
        iconEl.className = headerIconClass;
        headerDiv.appendChild(iconEl);

        const textEl = document.createElement('span');
        textEl.className = 'log-item-message'; // Use same class for consistent styling
        textEl.textContent = headerText;
        headerDiv.appendChild(textEl);
        logItemDiv.appendChild(headerDiv);

        if (thinkContent) {
            const thinkDiv = document.createElement('div');
            thinkDiv.classList.add('log-think-content'); // This class has specific styling for thought bubbles

            let formattedThink = thinkContent.replace(/\n/g, '<br>'); // Basic newline to <br>
            // Attempt to find and format JSON within the thought process
            try {
                // Regex to find ```json ... ``` blocks, case-insensitive, multiline
                const jsonBlockRegex = /```json([\s\S]*?)```/gi;
                formattedThink = formattedThink.replace(jsonBlockRegex, (match, jsonContentStr) => {
                    const trimmedJson = jsonContentStr.trim();
                    try {
                        const parsedJson = JSON.parse(trimmedJson);
                        // Escape HTML in the stringified JSON before putting in pre/code
                        const escapedJsonString = JSON.stringify(parsedJson, null, 2)
                            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        return `<pre><code class="language-json">${escapedJsonString}</code></pre>`;
                    } catch (jsonErr) {
                        console.warn("Log area: JSON parsing for pretty print failed within thought:", jsonErr);
                        const escapedOriginalJson = trimmedJson
                            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        return `<pre><code class="language-json error">${escapedOriginalJson}<br>(JSON Parse Error for pretty print)</code></pre>`;
                    }
                });
            } catch (e) { console.error("Error processing JSON blocks in thought content for log:", e); }

            thinkDiv.innerHTML = `<strong>${thinkBubbleLabel}:</strong><div class="think-bubble">${formattedThink}</div>`;
            logItemDiv.appendChild(thinkDiv);
        }
        dom.processLogContent.appendChild(logItemDiv);
        scrollToProcessLogBottom();
    }

    function scrollToProcessLogBottom(instant = false) {
        if (!dom.processLogContent) return; // Ensure element exists
        const container = dom.processLogContainer; // The scrollable container
        const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth'; // 'auto' for instant
        container.scrollTo({ top: container.scrollHeight, behavior });
    }

    function showProcessLog(ensureExpanded = false) {
        if (!dom.processLogContainer) return;
        state.isProcessLogVisible = true;
        dom.processLogContainer.style.display = 'flex'; // Changed to flex for better internal layout
        dom.processLogContainer.style.flexDirection = 'column';

        if (state.animationLevel !== 'none' && !dom.processLogContainer.classList.contains('animate__fadeInDown')) {
            dom.processLogContainer.classList.remove('animate__fadeOutUp');
            dom.processLogContainer.classList.add('animate__animated', 'animate__fadeInDown');
            dom.processLogContainer.style.setProperty('--animate-duration', '0.3s');
        }
        if (ensureExpanded && state.isProcessLogCollapsed) {
            toggleProcessLogCollapse(true); // Pass instant true if needed
        }
    }

    function hideProcessLog() {
        if (!dom.processLogContainer) return;
        state.isProcessLogVisible = false;
        if (state.animationLevel !== 'none') {
            dom.processLogContainer.classList.remove('animate__fadeInDown');
            dom.processLogContainer.classList.add('animate__animated', 'animate__fadeOutUp');
            dom.processLogContainer.addEventListener('animationend', () => {
                if (!state.isProcessLogVisible) { // Check again in case it was re-shown
                    dom.processLogContainer.style.display = 'none';
                }
                dom.processLogContainer.classList.remove('animate__animated', 'animate__fadeOutUp');
            }, { once: true });
        } else {
            dom.processLogContainer.style.display = 'none';
        }
    }

    function toggleProcessLogCollapse(instant = false) {
        state.isProcessLogCollapsed = !state.isProcessLogCollapsed;
        dom.processLogContainer.classList.toggle('collapsed', state.isProcessLogCollapsed);
        const iconElement = dom.toggleProcessLogCollapseButton.querySelector('i');
        if (iconElement) {
            iconElement.className = state.isProcessLogCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
        }
        localStorage.setItem(APP_PREFIX + 'processLogCollapsed', state.isProcessLogCollapsed.toString());
        if (!instant && state.animationLevel !== 'none') {
            dom.processLogContainer.style.transition = 'max-height 0.3s ease-in-out, padding 0.3s ease-in-out';
        } else if (dom.processLogContainer.style.transition !== 'none') {
            dom.processLogContainer.style.transition = 'none';
        }
    }

    function updateProcessLogCollapseState(collapse, instant = false) { // Used on load
        state.isProcessLogCollapsed = collapse;
        dom.processLogContainer.classList.toggle('collapsed', state.isProcessLogCollapsed);
        const iconElement = dom.toggleProcessLogCollapseButton.querySelector('i');
        if (iconElement) {
            iconElement.className = state.isProcessLogCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
        }
        if (instant || state.animationLevel === 'none') {
            if (dom.processLogContainer.style.transition !== 'none') dom.processLogContainer.style.transition = 'none';
        }
    }

    function initializeApp() {
        console.log("IDT Agent Pro V8.2 Initializing...");
        updateLoaderProgress(10);

        loadSettings(); // Load all settings first
        updateLoaderProgress(25);

        applyCurrentTheme(); // Apply theme based on loaded or default state.currentTheme
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16'); // Apply loaded font size
        applyAnimationLevel(state.animationLevel); // Apply loaded animation level
        updateLoaderProgress(40);

        loadSessions(); // Load session data
        updateLoaderProgress(55);

        setupEventListeners(); // Setup all event listeners
        updateLoaderProgress(70);

        adjustTextareaHeight(); // Initial adjustment for textarea
        updateCharCounter();    // Initial char count
        updateLoaderProgress(85);

        // Apply UI states based on loaded settings
        updateSidebarState(state.isSidebarExpanded, true);
        updateSessionManagerState(state.isSessionManagerCollapsed, true);
        updateProcessLogCollapseState(state.isProcessLogCollapsed, true);

        // Initial Process Log Visibility
        if (localStorage.getItem(APP_PREFIX + 'isProcessLogVisible') === 'true') {
            showProcessLog(true); // Show and expand if it was visible last time
        } else {
            hideProcessLog(); // Ensure it's hidden if it was hidden last time
        }

        connectWebSocket(); // Connect WebSocket, which will trigger init_success and session loading
        updateLoaderProgress(95);

        // Simulate final loading step after a short delay
        setTimeout(() => {
            if (dom.loaderProgress) dom.loaderProgress.style.width = '100%';
            // Loader will be hidden by init_success or init_error
        }, 200);
        console.log("IDT Agent Pro V8.2 initialization sequence complete, awaiting WebSocket confirmation.");
    }

    function updateLoaderProgress(percentage) {
        if (dom.loaderProgress) {
            dom.loaderProgress.style.width = `${percentage}%`;
        }
        const loadingTextEl = dom.loader.querySelector('.loading-text');
        if (loadingTextEl) {
            if (percentage < 30) loadingTextEl.textContent = "Calibrating settings...";
            else if (percentage < 60) loadingTextEl.textContent = "Loading session data...";
            else if (percentage < 90) loadingTextEl.textContent = "Preparing interface...";
            else loadingTextEl.textContent = "Establishing secure link...";
        }
    }

    function setupEventListeners() {
        dom.sendButton.addEventListener('click', handleSendMessage);
        dom.userInput.addEventListener('keypress', handleUserInputKeypress);
        dom.userInput.addEventListener('input', () => {
            adjustTextareaHeight();
            updateCharCounter();
        });

        dom.themeToggleButton.addEventListener('click', () => {
            const themes = ['auto', 'light', 'dark'];
            const currentIndex = themes.indexOf(state.currentTheme);
            const nextTheme = themes[(currentIndex + 1) % themes.length];
            applyTheme(nextTheme); // This now also saves
            showToast(`Theme set to: ${getThemeDisplayName(state.currentTheme)}`, 'info');
        });

        dom.clearChatButton.addEventListener('click', handleClearCurrentChat);
        dom.manageSessionsToggle.addEventListener('click', () => updateSidebarState(!state.isSidebarExpanded));
        dom.toggleProcessLogVisibilityButton.addEventListener('click', () => { // New button for log visibility
            if (state.isProcessLogVisible) {
                hideProcessLog();
            } else {
                showProcessLog(true); // Show and expand
            }
            localStorage.setItem(APP_PREFIX + 'isProcessLogVisible', state.isProcessLogVisible.toString());
        });


        dom.sidebarButtons.forEach(button => {
            button.addEventListener('click', () => {
                const mode = button.dataset.mode;
                if (mode === 'settings') openSettingsModal();
                else handleModeChange(mode);
            });
        });

        dom.sessionManagerToggle.addEventListener('click', () => updateSessionManagerState(!state.isSessionManagerCollapsed));
        dom.createNewSessionButton.addEventListener('click', () => createNewSession());
        dom.editSessionNameButton.addEventListener('click', handleEditSessionName);

        dom.attachButton.addEventListener('click', () => dom.fileInput.click());
        dom.fileInput.addEventListener('change', handleFileSelection);
        dom.closeFilePreviewButton.addEventListener('click', closeFilePreview);

        dom.micButton.addEventListener('click', () => showToast('Voice input module under calibration...', 'info'));

        // Settings Modal
        if (dom.openSettingsButton) dom.openSettingsButton.addEventListener('click', openSettingsModal);
        if (dom.closeSettingsButton) dom.closeSettingsButton.addEventListener('click', () => closeSettingsModal(true));
        if (dom.saveSettingsButton) dom.saveSettingsButton.addEventListener('click', () => {
            collectAndSaveSettings();
            closeSettingsModal(false);
            showToast('Personalization parameters calibrated and saved!', 'success');
        });
        if (dom.resetSettingsButton) dom.resetSettingsButton.addEventListener('click', resetToDefaultSettings);

        if (dom.fontSizeInput) dom.fontSizeInput.addEventListener('input', () => { // Live preview for font size
            const newSize = dom.fontSizeInput.value;
            if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${newSize}px`;
            document.body.style.fontSize = `${newSize}px`;
        });
        if (dom.animationLevelSelect) dom.animationLevelSelect.addEventListener('change', (e) => { // Live preview for animation
            applyAnimationLevel(e.target.value);
        });
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.addEventListener('change', (e) => { // Live preview for chat think
            state.showChatBubblesThink = e.target.checked;
            // No immediate visual change, affects next agent message
        });
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.addEventListener('change', (e) => { // Live preview for log think
            state.showLogBubblesThink = e.target.checked;
            // No immediate visual change, affects next log thinking item
        });

        if (dom.settingsModal) dom.settingsModal.addEventListener('click', (e) => { // Close modal on backdrop click
            if (e.target === dom.settingsModal) closeSettingsModal(true);
        });

        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (state.currentTheme === 'auto') applyCurrentTheme(); // Re-apply if in auto mode
        });

        if (dom.toggleProcessLogCollapseButton) dom.toggleProcessLogCollapseButton.addEventListener('click', () => toggleProcessLogCollapse());
    }

    function updateCharCounter() {
        const currentLength = dom.userInput.value.length;
        dom.charCounter.textContent = `${currentLength}/${state.maxInputChars}`;
        dom.charCounter.classList.remove('warn', 'error');
        if (currentLength > state.maxInputChars) {
            dom.charCounter.classList.add('error');
        } else if (currentLength > state.maxInputChars * 0.9) {
            dom.charCounter.classList.add('warn');
        }
    }

    function generateSessionId() {
        // More robust unique ID generation
        return `session_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 11)}`;
    }

    function generateClientRequestId() {
        return `creq_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 9)}`;
    }

    function initializeCurrentSessionUI(isInitialLoadOrConnect = false) {
        const lastSessionId = localStorage.getItem(APP_PREFIX + 'lastSessionId');
        let targetSessionId = state.currentSessionId; // currentSessionId might be set by init_success

        if (!targetSessionId) { // If WS init didn't provide one (e.g., first ever load)
            if (lastSessionId && state.sessions[lastSessionId]) {
                targetSessionId = lastSessionId;
            } else if (Object.keys(state.sessions).length > 0) {
                // Fallback to most recent if lastSessionId is invalid or missing
                const sortedSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
                targetSessionId = sortedSessions[0].id;
            }
        }

        // If still no valid target session, create a brand new one
        if (!targetSessionId || !state.sessions[targetSessionId]) {
            targetSessionId = createNewSession(true); // Pass true for initial, less UI noise
        }

        // Switch to the determined session
        // `isInitialLoadOrConnect` is true, so it won't try to re-init WebSocket
        switchSession(targetSessionId, isInitialLoadOrConnect);
    }


    function createNewSession(isInitialCreation = false) {
        const newId = generateSessionId();
        const now = Date.now();
        const sessionCount = Object.keys(state.sessions).length + 1;
        state.sessions[newId] = {
            id: newId,
            name: `Conversation ${sessionCount}`,
            messages: [],
            createdAt: now,
            lastActivity: now,
        };
        saveSessions(); // Save immediately

        if (!isInitialCreation) {
            // For user-initiated new session, switch to it and re-init WebSocket for this new session
            switchSession(newId, false); // false indicates it's not the initial load
            showToast('New communication link established for new session!', 'success');
            if (!state.isSidebarExpanded) updateSidebarState(true); // Expand sidebar to show new session
            if (state.isSessionManagerCollapsed) updateSessionManagerState(false); // Expand session list
        }
        return newId; // Return ID for initial creation case
    }

    function switchSession(sessionId, isInitialLoadOrConnect = false) {
        if (!state.sessions[sessionId]) {
            console.error(`Attempt to switch to non-existent session: ${sessionId}. Creating a new one.`);
            const fallbackId = createNewSession(true);
            state.currentSessionId = fallbackId;
            if (!isInitialLoadOrConnect) { // Only re-init if not part of initial load/connect sequence
                sendWebSocketMessage({ type: 'init', session_id: fallbackId });
            }
            // Basic UI update until WS confirms
            dom.chatBox.innerHTML = '';
            appendWelcomeMessage(); // Append welcome, not "loading"
            dom.currentSessionNameDisplay.textContent = state.sessions[fallbackId]?.name || "New Session";
            renderSessionList();
            return;
        }

        // If it's a user-initiated switch to a *different* session, and not initial load
        if (!isInitialLoadOrConnect && state.currentSessionId !== sessionId) {
            state.currentSessionId = sessionId; // Update state.currentSessionId first
            sendWebSocketMessage({ type: 'init', session_id: sessionId });
            // Clear chat and show loading indicator, actual content loads on init_success from WS
            dom.chatBox.innerHTML = '';
            // Use a less intrusive loading message in chatbox
            appendMessage("Loading conversation...", 'system-info', false, null, true, [], "System Loading");
            dom.currentSessionNameDisplay.textContent = state.sessions[sessionId]?.name || "Loading...";
            renderSessionList(); // Update selection in list
            return;
        }

        // This part runs if it's an initial load/connect OR if switching to the *same* session (no WS re-init needed)
        // OR after init_success for a switched session
        state.currentSessionId = sessionId;
        if (state.sessions[sessionId]) {
            state.sessions[sessionId].lastActivity = Date.now();
        }
        localStorage.setItem(APP_PREFIX + 'lastSessionId', sessionId);
        saveSessions();

        dom.currentSessionNameDisplay.textContent = state.sessions[sessionId]?.name || "Session";
        dom.chatBox.innerHTML = ''; // Clear previous content

        if (state.sessions[sessionId]?.messages.length === 0) {
            appendWelcomeMessage();
        } else {
            state.sessions[sessionId]?.messages.forEach(msg => {
                // Pass all relevant fields to appendMessage
                appendMessage(msg.content, msg.sender, msg.isHTML, msg.thinking, true, msg.attachments, msg.errorType);
            });
        }
        scrollToBottom(true); // Instant scroll on session switch
        renderSessionList(); // Highlight active session
        dom.userInput.focus();

        // Reset process log for the new session view
        dom.processLogContent.innerHTML = '';
        if (state.isProcessLogVisible && !state.isProcessLogCollapsed) {
            // If log was open, keep it open but content is cleared
        } else if (state.isProcessLogVisible && state.isProcessLogCollapsed) {
            // If log was visible but collapsed, keep it that way
        } else {
            // If log was hidden, ensure it remains hidden or apply default
            hideProcessLog(); // Default to hidden for new session unless globally set to visible
        }
        console.log(`Switched to session: ${state.sessions[sessionId]?.name} (ID: ${sessionId})`);
    }


    function deleteSession(sessionId, event) {
        if (event) event.stopPropagation();
        if (!state.sessions[sessionId]) return;

        const sessionName = state.sessions[sessionId].name;
        if (!confirm(`Are you sure you want to archive (delete) session "${sessionName}"? This action cannot be undone.`)) {
            return;
        }

        const listItem = dom.sessionList.querySelector(`li[data-session-id="${sessionId}"]`);
        if (listItem) {
            if (state.animationLevel !== 'none') {
                listItem.classList.add('animate__animated', 'animate__fadeOutLeft');
                listItem.style.setProperty('--animate-duration', '0.4s');
                listItem.addEventListener('animationend', () => listItem.remove(), { once: true });
            } else {
                listItem.remove();
            }
        }

        delete state.sessions[sessionId];

        if (state.currentSessionId === sessionId) {
            const remainingSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
            if (remainingSessions.length > 0) {
                switchSession(remainingSessions[0].id, false); // false to trigger WS re-init for new active session
            } else {
                const newSessId = createNewSession(false); // Create new, and switchSession inside will handle WS
            }
        } else {
            saveSessions();
            renderSessionList(); // Just update the list if deleted session wasn't active
        }
        showToast(`Session "${sessionName}" has been archived.`, 'info');
        if (Object.keys(state.sessions).length === 0 && dom.sessionList) renderSessionList(); // Re-render to show empty state
    }

    function handleEditSessionName() {
        const currentSession = state.sessions[state.currentSessionId];
        if (!currentSession) return;

        const newName = prompt("Enter new name for this session:", currentSession.name);
        if (newName && newName.trim() !== "" && newName.trim() !== currentSession.name) {
            currentSession.name = newName.trim().substring(0, 50); // Max 50 chars
            currentSession.lastActivity = Date.now();
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            saveSessions();
            renderSessionList(); // Update name in the list
            showToast("Session name updated.", "success");
        }
    }

    function renderSessionList() {
        if (!dom.sessionList) return;
        dom.sessionList.innerHTML = '';
        const sortedSessions = Object.values(state.sessions)
            .sort((a, b) => b.lastActivity - a.lastActivity);

        if (sortedSessions.length === 0) {
            const emptyItem = document.createElement('li');
            emptyItem.classList.add('session-list-empty');
            emptyItem.textContent = 'No past conversations';
            dom.sessionList.appendChild(emptyItem);
            return;
        }

        sortedSessions.forEach(session => {
            const listItem = document.createElement('li');
            listItem.classList.add('session-list-item');
            if (state.animationLevel === 'full' && !listItem.classList.contains('active-session')) {
                listItem.classList.add('animate__animated', 'animate__fadeInRight');
                listItem.style.setProperty('--animate-duration', '0.3s');
            }
            if (session.id === state.currentSessionId) {
                listItem.classList.add('active-session');
            }
            listItem.dataset.sessionId = session.id;

            const lastActivityDate = new Date(session.lastActivity);
            const createdDate = new Date(session.createdAt);
            const timeSinceLastActivity = formatTimeSince(session.lastActivity);

            listItem.title = `Last active: ${timeSinceLastActivity}\n(${lastActivityDate.toLocaleString()})\nCreated: ${createdDate.toLocaleDateString()}`;

            const contentWrapper = document.createElement('div');
            contentWrapper.classList.add('session-item-content');

            const nameSpan = document.createElement('span');
            nameSpan.classList.add('session-name');
            nameSpan.textContent = session.name;

            const timeSpan = document.createElement('span');
            timeSpan.classList.add('session-time');
            timeSpan.textContent = timeSinceLastActivity;

            contentWrapper.appendChild(nameSpan);
            contentWrapper.appendChild(timeSpan);

            const deleteBtn = document.createElement('button');
            deleteBtn.classList.add('session-delete-btn', 'icon-btn');
            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
            deleteBtn.title = "Delete this session";
            deleteBtn.addEventListener('click', (e) => deleteSession(session.id, e));

            listItem.appendChild(contentWrapper);
            listItem.appendChild(deleteBtn);
            listItem.addEventListener('click', () => {
                if (state.currentSessionId !== session.id) switchSession(session.id, false); // User initiated switch
            });
            dom.sessionList.appendChild(listItem);
        });
    }

    function formatTimeSince(dateTimestamp) {
        const now = new Date();
        const secondsPast = (now.getTime() - dateTimestamp) / 1000;

        if (secondsPast < 60) return 'Just now';
        if (secondsPast < 3600) return `${Math.round(secondsPast / 60)}m ago`;
        if (secondsPast <= 86400) return `${Math.round(secondsPast / 3600)}h ago`;

        const date = new Date(dateTimestamp);
        if (now.getFullYear() === date.getFullYear()) {
            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        }
        return date.toLocaleDateString(undefined, { year: '2-digit', month: 'short', day: 'numeric' });
    }


    function saveSessions() {
        try {
            localStorage.setItem(APP_PREFIX + 'sessions', JSON.stringify(state.sessions));
        } catch (e) {
            console.error("Error saving sessions to localStorage (possibly full):", e);
            showToast("Could not save session data. Storage might be full.", "error");
        }
    }

    function loadSessions() {
        const storedSessions = localStorage.getItem(APP_PREFIX + 'sessions');
        if (storedSessions) {
            try {
                const parsedSessions = JSON.parse(storedSessions);
                Object.keys(parsedSessions).forEach(id => {
                    const s = parsedSessions[id];
                    if (s && typeof s.id === 'string' && typeof s.name === 'string' && Array.isArray(s.messages)) {
                        state.sessions[id] = {
                            id: s.id,
                            name: s.name || "Untitled Session",
                            messages: s.messages.map(m => ({
                                content: m.content || "",
                                sender: m.sender || "system",
                                timestamp: m.timestamp || Date.now(),
                                isHTML: m.isHTML || false,
                                attachments: m.attachments || [],
                                thinking: m.thinking || null,
                                rawResponseV8_1: m.rawResponseV8_1, // Load stored V8.1 JSON
                                errorType: m.errorType, // Load stored error type
                            })),
                            createdAt: s.createdAt || Date.now(),
                            lastActivity: s.lastActivity || Date.now(),
                        };
                    } else {
                        console.warn("Found invalid session data, skipping:", id, s);
                    }
                });
            } catch (e) {
                console.error("Failed to load or parse session data:", e);
                state.sessions = {};
                localStorage.removeItem(APP_PREFIX + 'sessions'); // Clear corrupted data
            }
        } else {
            state.sessions = {}; // No sessions stored
        }
    }

    function updateSidebarState(expand, instant = false) {
        state.isSidebarExpanded = expand;
        dom.sidebar.classList.toggle('expanded', state.isSidebarExpanded);
        dom.manageSessionsToggle.setAttribute('aria-expanded', state.isSidebarExpanded.toString());
        dom.manageSessionsToggle.querySelector('i').className = state.isSidebarExpanded ? 'fas fa-chevron-left' : 'fas fa-bars'; // Icon reflects action

        if (!instant && state.animationLevel !== 'none') {
            dom.sidebar.style.transition = 'width var(--transition-duration-medium) var(--transition-timing-function)';
        } else {
            dom.sidebar.style.transition = 'none'; // Apply instantly
        }
        localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());

        // If sidebar collapses, also collapse session manager if it's expanded
        if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
            updateSessionManagerState(true, instant);
        }
    }

    function updateSessionManagerState(collapse, instant = false) {
        state.isSessionManagerCollapsed = collapse;
        dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
        dom.sessionManagerToggle.setAttribute('aria-expanded', (!state.isSessionManagerCollapsed).toString());

        if (!instant && state.animationLevel !== 'none') {
            dom.sessionListContainer.style.transition = 'max-height var(--transition-duration-medium) var(--transition-timing-function), padding var(--transition-duration-medium) var(--transition-timing-function)';
        } else {
            dom.sessionListContainer.style.transition = 'none';
        }
        localStorage.setItem(APP_PREFIX + 'sessionManagerCollapsed', state.isSessionManagerCollapsed.toString());
    }

    async function handleSendMessage() {
        if (state.isLoading) {
            showToast("Processing previous message, please wait...", "warning");
            return;
        }
        const messageText = dom.userInput.value.trim();
        const filesToSend = [...state.uploadedFiles];

        if (messageText === '' && filesToSend.length === 0) {
            showToast("Please enter a message or select a file.", "warning");
            return;
        }
        if (dom.userInput.value.length > state.maxInputChars) {
            showToast(`Input too long. Max ${state.maxInputChars} characters.`, "error");
            return;
        }

        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
            showToast("Communication link inactive. Attempting to reconnect...", "warning");
            connectWebSocket(); // Attempt to reconnect
            return; // Don't proceed with sending message yet
        }

        setLoadingState(true);
        state.currentClientRequestId = generateClientRequestId(); // Generate new client request ID
        state.lastResponseThinking = null;

        const currentUserMessage = {
            content: messageText,
            sender: 'user',
            timestamp: Date.now(),
            isHTML: false,
            attachments: filesToSend.map(f => ({ name: f.name, size: f.size, type: f.type })) // Store summary
        };
        addMessageToCurrentSession(currentUserMessage);
        appendMessage(messageText, 'user', false, null, false, currentUserMessage.attachments);

        const currentSession = state.sessions[state.currentSessionId];
        // Auto-name session based on first user message if it's a default "Conversation X"
        if (currentSession && currentSession.name.startsWith("Conversation ") && currentSession.messages.filter(m => m.sender === 'user').length === 1) {
            const autoName = messageText.substring(0, 30).trim() || "New Chat";
            currentSession.name = autoName + (messageText.length > 30 ? "..." : "");
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            renderSessionList(); // Update list with new name
        }

        dom.userInput.value = '';
        adjustTextareaHeight();
        updateCharCounter();
        closeFilePreview();

        dom.processLogContent.innerHTML = '';
        showProcessLog(true); // Show and expand log for new request

        // For now, backend doesn't handle base64 file content via WebSocket message directly.
        // Conceptual: If files were to be sent, they'd be processed here.
        // For V8.2, we just mention them in the text content.
        let backendMessageContent = messageText;
        if (filesToSend.length > 0) {
            backendMessageContent += `\n[User conceptually attached files: ${filesToSend.map(f => f.name).join(', ')}. Please process the text query based on these filenames.]`;
        }

        sendWebSocketMessage({
            type: 'message',
            session_id: state.currentSessionId,
            request_id: state.currentClientRequestId, // Send client-generated request ID
            content: backendMessageContent,
            mode: state.currentMode // Send current UI mode
            // attachments: [] // Actual file data would go here if supported
        });
    }

    function addMessageToCurrentSession(messageObject) {
        if (state.sessions[state.currentSessionId]) {
            if (messageObject.sender !== 'agent') {
                delete messageObject.rawResponseV8_1; // Only agent messages might have this
            }
            if (messageObject.sender !== 'agent' || !messageObject.thinking) {
                delete messageObject.thinking;
            }
            if (!messageObject.errorType) { // Don't add errorType if not present
                delete messageObject.errorType;
            }
            state.sessions[state.currentSessionId].messages.push(messageObject);
            saveSessions();
        } else {
            console.error("Attempted to add message to non-existent session:", state.currentSessionId);
        }
    }

    function handleUserInputKeypress(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleSendMessage();
        }
    }

    // errorType can be: "System Error", "Server Error", "Agent Logic Error", null for normal agent replies
    function appendMessage(content, sender, isHTML = false, thinkContent = null, isSwitchingSession = false, attachments = [], errorType = null) {
        const messageDiv = document.createElement('div');
        const messageSenderClass = `message-${sender}`; // e.g., message-user, message-agent, message-system-info
        messageDiv.classList.add('message', messageSenderClass);

        // Add specific error class if errorType is provided
        if (errorType) {
            const errorClassSuffix = errorType.toLowerCase().replace(/\s+/g, '-');
            messageDiv.classList.add(`message-error-type-${errorClassSuffix}`);
        }
        // Special class for system info messages for different styling
        if (sender === 'system-info' || sender === 'error-system') {
            messageDiv.classList.add('system-message'); // Base system styling
            if (sender === 'error-system') messageDiv.classList.add('error-message'); // Specific error styling
        }


        if (!isSwitchingSession && state.animationLevel !== 'none') {
            const animationClass = state.animationLevel === 'full' ? 'animate__fadeInUp' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
            if (animationClass) {
                messageDiv.classList.add('animate__animated', animationClass);
                messageDiv.style.setProperty('--animate-duration', state.animationLevel === 'full' ? '0.4s' : '0.25s');
            }
        }

        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('message-avatar');
        let avatarIcon = 'fas fa-info-circle'; // Default for system
        if (sender === 'user') avatarIcon = 'fas fa-user-astronaut';
        else if (sender === 'agent') avatarIcon = 'fas fa-robot';
        else if (sender === 'agent-interim') avatarIcon = 'fas fa-spinner fa-pulse'; // Interim messages
        else if (sender === 'error-system') avatarIcon = 'fas fa-shield-virus'; // Specific error icon

        avatarDiv.innerHTML = `<i class="${avatarIcon}"></i>`;

        // For user messages, avatar is appended last due to flex-direction: row-reverse
        if (sender !== 'user' && sender !== 'system-message') { // system-message is full width, no avatar needed in flex
            messageDiv.appendChild(avatarDiv);
        }


        const messageBubbleDiv = document.createElement('div');
        messageBubbleDiv.classList.add('message-bubble');

        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.classList.add('message-content-wrapper');

        if (sender === 'agent' && thinkContent && state.showChatBubblesThink) {
            const thinkPrefixDiv = document.createElement('div');
            thinkPrefixDiv.classList.add('message-thought-prefix');
            let formattedThink = thinkContent.replace(/\n/g, '<br>');
            const jsonBlockRegex = /```json([\s\S]*?)```/gi;
            formattedThink = formattedThink.replace(jsonBlockRegex, (match, jsonContentStr) => {
                const trimmedJson = jsonContentStr.trim();
                try {
                    const parsedJson = JSON.parse(trimmedJson);
                    const escapedJsonString = JSON.stringify(parsedJson, null, 2).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    return `<pre class="embedded-json"><code>${escapedJsonString}</code></pre>`;
                } catch (e) {
                    const escapedOriginalJson = trimmedJson.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    return `<pre class="embedded-json error"><code>${escapedOriginalJson}<br>(Invalid JSON for formatting)</code></pre>`;
                }
            });
            thinkPrefixDiv.innerHTML = `<strong>Agent's Reasoning:</strong> ${formattedThink}`;
            messageContentWrapper.appendChild(thinkPrefixDiv);
        }


        const textContentDiv = document.createElement('div');
        textContentDiv.classList.add('message-text-content');

        if (isHTML) {
            textContentDiv.innerHTML = content; // Use with caution, ensure HTML is sanitized if from untrusted source
        } else {
            // Basic URL linking and newline to <br>
            const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
            const linkedContent = content
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") // Basic XSS protection
                .replace(/"/g, "&quot;").replace(/'/g, "&#039;")
                .replace(/\n/g, '<br>')
                .replace(urlRegex, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
            textContentDiv.innerHTML = linkedContent;
        }
        messageContentWrapper.appendChild(textContentDiv);

        if (attachments && attachments.length > 0) {
            const attachmentsDiv = document.createElement('div');
            attachmentsDiv.classList.add('message-attachments-summary');
            attachmentsDiv.innerHTML = `<i class="fas fa-paperclip"></i> Attachments (${attachments.length}): `;
            attachments.forEach(file => {
                const fileChip = document.createElement('span');
                fileChip.classList.add('filename-chip');
                fileChip.textContent = file.name;
                fileChip.title = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
                attachmentsDiv.appendChild(fileChip);
            });
            messageContentWrapper.appendChild(attachmentsDiv);
        }

        messageBubbleDiv.appendChild(messageContentWrapper);
        messageDiv.appendChild(messageBubbleDiv);

        if (sender === 'user') { // Append avatar last for user
            messageDiv.appendChild(avatarDiv);
        }

        dom.chatBox.appendChild(messageDiv);

        if (!isSwitchingSession) {
            scrollToBottom();
        }
    }

    function appendWelcomeMessage() {
        const lastMessage = dom.chatBox.lastElementChild;
        if (lastMessage && lastMessage.classList.contains('message-system-initial')) {
            return; // Welcome message already exists
        }
        if (lastMessage && lastMessage.classList.contains('message-system-info') && lastMessage.textContent.includes("Loading conversation...")) {
            lastMessage.remove();
        }


        const welcomeHTML = `
            <div class="message-content">
                <div class="welcome-header">
                    <i class="fas fa-robot robot-icon animate__animated animate__pulse animate__infinite" style="--animate-duration: 2s;"></i>
                    <h2>IDT 智能助手 <span class="version-pro">Pro <span class="version-number">v8.2</span></span></h2>
                </div>
                <p>我是您的电路设计与编程高级助理。已准备就绪，随时为您服务！</p>
                <div class="capabilities">
                    <div class="capability"><i class="fas fa-bolt"></i><span>快速响应</span></div>
                    <div class="capability"><i class="fas fa-brain"></i><span>深度分析</span></div>
                    <div class="capability"><i class="fas fa-cogs"></i><span>工具调用</span></div>
                    <div class="capability"><i class="fas fa-sync-alt"></i><span>迭代优化</span></div>
                </div>
                 <div class="quick-actions">
                    <p>您可以尝试以下指令开始：</p>
                    <ul>
                        <li><a href="#" class="quick-action-btn" data-message="添加一个1kΩ的电阻R1">添加电阻R1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="添加一个LED，命名为LED1，红色">添加红色LED1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="将R1与LED1的正极连接，再将LED1的负极连接到GND">连接R1-LED1-GND</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="当前电路状态如何？">描述电路</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="清空电路">清空电路</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="什么是串联和并联电路？">串联与并联</a></li>
                    </ul>
                 </div>
            </div>
        `;
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'message system-message system-message-initial animate__animated animate__fadeInUp';
        welcomeDiv.innerHTML = welcomeHTML;
        dom.chatBox.appendChild(welcomeDiv);
        attachQuickActionButtonListeners(welcomeDiv); // Attach listeners to newly added buttons
    }


    function scrollToBottom(instant = false) {
        if (state.autoScroll) {
            const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth';
            dom.chatBox.scrollTo({ top: dom.chatBox.scrollHeight, behavior });
        }
    }

    function showTypingIndicator() {
        if (state.isAgentTyping) return;
        state.isAgentTyping = true;

        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        const animationClass = state.animationLevel !== 'none' ? 'animate__fadeInUp' : '';
        typingDiv.classList.add('message', 'message-agent', 'typing-indicator');
        if (animationClass) {
            typingDiv.classList.add('animate__animated', animationClass);
            typingDiv.style.setProperty('--animate-duration', '0.3s');
        }

        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('message-avatar');
        avatarDiv.innerHTML = '<i class="fas fa-robot"></i>';

        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('message-bubble');

        const contentWrapper = document.createElement('div');
        contentWrapper.classList.add('message-content-wrapper');

        const textContent = document.createElement('div');
        textContent.classList.add('message-text-content');

        let dotsHTML = Array(3).fill('<span class="typing-dot"></span>').join('');
        textContent.innerHTML = `IDT Agent Pro is processing<span class="typing-dots">${dotsHTML}</span>`; // Changed text

        contentWrapper.appendChild(textContent);
        bubbleDiv.appendChild(contentWrapper);
        typingDiv.appendChild(avatarDiv);
        typingDiv.appendChild(bubbleDiv);

        dom.chatBox.appendChild(typingDiv);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        if (!state.isAgentTyping) return;
        state.isAgentTyping = false;

        const typingElement = document.getElementById('typing-indicator');
        if (typingElement) {
            if (state.animationLevel !== 'none') {
                const animationOutClass = state.animationLevel === 'full' ? 'animate__fadeOutDown' : 'animate__fadeOut';
                typingElement.classList.remove('animate__fadeInUp', 'animate__fadeIn');
                typingElement.classList.add('animate__animated', animationOutClass);
                typingElement.addEventListener('animationend', () => typingElement.remove(), { once: true });
            } else {
                typingElement.remove();
            }
        }
    }

    function adjustTextareaHeight() {
        dom.userInput.style.height = 'auto';
        let scrollHeight = dom.userInput.scrollHeight;
        const maxHeight = parseInt(getComputedStyle(dom.userInput).maxHeight, 10) || state.input_area_max_height; // Use state var
        const minHeight = parseInt(getComputedStyle(dom.userInput).minHeight, 10) || state.input_area_min_height; // Use state var

        // Add padding to scrollHeight to avoid scrollbar appearing too early for single line
        const singleLinePadding = 5;
        if (dom.userInput.value.split('\n').length <= 1) {
            scrollHeight += singleLinePadding;
        }

        if (scrollHeight > maxHeight) {
            dom.userInput.style.height = maxHeight + 'px';
            dom.userInput.style.overflowY = 'auto';
        } else {
            dom.userInput.style.height = Math.max(scrollHeight, minHeight) + 'px';
            dom.userInput.style.overflowY = 'hidden';
        }
    }

    function handleClearCurrentChat() {
        if (!state.currentSessionId || !state.sessions[state.currentSessionId]) return;

        if (!confirm(`Are you sure you want to clear all messages in session "${state.sessions[state.currentSessionId].name}"? This will also clear the Agent's process log for this session view.`)) {
            return;
        }

        state.sessions[state.currentSessionId].messages = [];
        state.sessions[state.currentSessionId].lastActivity = Date.now();
        saveSessions();

        dom.chatBox.innerHTML = '';
        appendWelcomeMessage();

        dom.processLogContent.innerHTML = ''; // Clear process log content
        if (state.isProcessLogVisible && !state.isProcessLogCollapsed) {
            // If log was visible and expanded, keep it that way (but now empty)
        } else if (state.isProcessLogVisible && state.isProcessLogCollapsed) {
            // If visible and collapsed, keep collapsed
        } else {
            hideProcessLog(); // If it was hidden, ensure it stays hidden
        }


        showToast('Current conversation cleared!', 'info');
        renderSessionList();
    }

    function handleModeChange(newMode) {
        if (state.currentMode === newMode) return;
        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === newMode));
        state.currentMode = newMode;
        localStorage.setItem(APP_PREFIX + 'currentMode', state.currentMode); // Persist mode
        console.log(`Mode switched to: ${newMode}`);
        showToast(`Switched to ${getModeDisplayName(newMode)} mode`, 'info');
        const sessionName = state.sessions[state.currentSessionId]?.name || 'current session';
        dom.userInput.placeholder = `Message in ${getModeDisplayName(newMode)} mode (${sessionName})...`;
    }

    function getModeDisplayName(mode) {
        const names = { chat: 'Conversation', code: 'Programming', circuit: 'Circuit Design', settings: 'Settings' };
        return names[mode] || 'Unknown';
    }

    function handleFileSelection(event) { // Conceptual, no actual upload logic to backend yet
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        const MAX_FILES = 5, MAX_SIZE_MB = 2; // Reduced max size for conceptual demo

        files.forEach(file => {
            if (state.uploadedFiles.length >= MAX_FILES) {
                showToast(`Maximum ${MAX_FILES} files allowed.`, 'warning'); return;
            }
            if (file.size > MAX_SIZE_MB * 1024 * 1024) {
                showToast(`File "${file.name}" exceeds ${MAX_SIZE_MB}MB limit.`, 'warning'); return;
            }
            if (!state.uploadedFiles.find(f => f.name === file.name && f.size === file.size)) {
                state.uploadedFiles.push(file);
                addFileToPreview(file);
            } else {
                showToast(`File "${file.name}" is already in the list.`, 'info');
            }
        });
        if (state.uploadedFiles.length > 0) dom.filePreviewArea.classList.add('active');
        dom.fileInput.value = '';
    }

    function addFileToPreview(file) {
        const fileItem = document.createElement('div');
        fileItem.classList.add('file-item');
        if (state.animationLevel !== 'none') fileItem.classList.add('animate__animated', 'animate__bounceIn');
        fileItem.style.setProperty('--animate-duration', '0.4s');
        fileItem.dataset.fileName = file.name;
        fileItem.dataset.fileSize = file.size;

        const iconClass = getFileIconClass(file.type, file.name);
        fileItem.innerHTML = `
            <i class="fas ${iconClass} file-icon"></i>
            <span class="file-name" title="${file.name} (${(file.size / 1024).toFixed(1)}KB)">${file.name}</span>
            <button class="file-remove icon-btn" title="Remove file"><i class="fas fa-times-circle"></i></button>`;

        fileItem.querySelector('.file-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            removeFileFromPreview(file.name, file.size);
        });
        dom.filePreviewContent.appendChild(fileItem);
    }

    function getFileIconClass(fileType, fileName) {
        if (fileType.startsWith('image/')) return 'fa-file-image';
        if (fileType.startsWith('audio/')) return 'fa-file-audio';
        if (fileType.startsWith('video/')) return 'fa-file-video';
        if (fileType === 'application/pdf') return 'fa-file-pdf';
        if (fileType === 'application/zip' || fileName.endsWith('.zip') || fileName.endsWith('.rar') || fileName.endsWith('.7z')) return 'fa-file-archive';
        const codeExtensions = ['.js', '.ts', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bat', '.v', '.sv', '.vhd', '.md', '.txt']; // Added .txt
        if (codeExtensions.some(ext => fileName.toLowerCase().endsWith(ext)) || fileType.includes('text')) return 'fa-file-code'; // text/plain etc.
        if (fileName.endsWith('.doc') || fileName.endsWith('.docx')) return 'fa-file-word';
        if (fileName.endsWith('.xls') || fileName.endsWith('.xlsx')) return 'fa-file-excel';
        if (fileName.endsWith('.ppt') || fileName.endsWith('.pptx')) return 'fa-file-powerpoint';
        return 'fa-file-alt'; // Default icon
    }

    function removeFileFromPreview(fileName, fileSize) {
        state.uploadedFiles = state.uploadedFiles.filter(f => !(f.name === fileName && f.size === fileSize));
        const fileItemElement = dom.filePreviewContent.querySelector(`.file-item[data-file-name="${CSS.escape(fileName)}"][data-file-size="${fileSize}"]`);
        if (fileItemElement) {
            if (state.animationLevel !== 'none') {
                fileItemElement.classList.remove('animate__bounceIn');
                fileItemElement.classList.add('animate__animated', 'animate__bounceOut'); // Ensure bounceOut is added
                fileItemElement.addEventListener('animationend', () => {
                    fileItemElement.remove();
                    if (state.uploadedFiles.length === 0) closeFilePreview();
                }, { once: true });
            } else {
                fileItemElement.remove();
                if (state.uploadedFiles.length === 0) closeFilePreview();
            }
        }
    }
    function closeFilePreview() {
        dom.filePreviewArea.classList.remove('active');
        // Do not clear state.uploadedFiles here, clear it when message is sent or user explicitly clears all.
        // This allows user to close preview but files remain "staged" until send or explicit removal.
        // If you want to clear on close preview:
        // state.uploadedFiles = [];
        // dom.filePreviewContent.innerHTML = '';
    }

    function applyCurrentTheme() {
        applyTheme(state.currentTheme, true); // Pass true for initialLoad
    }

    function applyTheme(themeName, initialLoad = false) {
        let effectiveTheme = themeName;
        document.body.classList.remove('light-theme', 'dark-theme');

        const themeIcon = dom.themeToggleButton.querySelector('i');

        if (themeName === 'auto') {
            effectiveTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            if (themeIcon) themeIcon.className = 'fas fa-desktop';
        }

        if (effectiveTheme === 'dark') {
            document.body.classList.add('dark-theme');
            if (themeIcon && themeName !== 'auto') themeIcon.className = 'fas fa-sun'; // Sun for dark mode selected
        } else {
            document.body.classList.add('light-theme');
            if (themeIcon && themeName !== 'auto') themeIcon.className = 'fas fa-moon'; // Moon for light mode selected
        }
        state.currentTheme = themeName; // Store the user's *selected* theme (auto, light, or dark)

        if (dom.themeSelect) dom.themeSelect.value = themeName; // Update dropdown

        if (!initialLoad) saveSettings(); // Save if not initial load
        console.log(`Theme applied: ${themeName} (Effective: ${effectiveTheme})`);
    }

    function getThemeDisplayName(theme) { return { 'light': 'Light Mode', 'dark': 'Dark Mode', 'auto': 'System Default' }[theme] || 'Unknown'; }

    function applyFontSize(size) {
        const newSize = parseInt(size, 10);
        if (isNaN(newSize) || newSize < 12 || newSize > 20) {
            document.body.style.fontSize = '16px'; // Default
            if (dom.fontSizeInput) dom.fontSizeInput.value = '16';
            if (dom.fontSizeValue) dom.fontSizeValue.textContent = '16px';
            return;
        }
        document.body.style.fontSize = `${newSize}px`;
        if (dom.fontSizeInput) dom.fontSizeInput.value = newSize;
        if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${newSize}px`;
    }

    function applyAnimationLevel(level) {
        document.body.dataset.animationLevel = level;
        state.animationLevel = level;
        if (dom.animationLevelSelect && dom.animationLevelSelect.value !== level) {
            dom.animationLevelSelect.value = level;
        }
        console.log(`Animation level set to: ${level}`);
    }

    function openSettingsModal() {
        // Populate modal with current settings from state
        if (dom.themeSelect) dom.themeSelect.value = state.currentTheme;
        const currentFontSize = parseFloat(getComputedStyle(document.body).fontSize);
        if (dom.fontSizeInput) dom.fontSizeInput.value = currentFontSize;
        if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${currentFontSize.toFixed(0)}px`;
        if (dom.animationLevelSelect) dom.animationLevelSelect.value = state.animationLevel;
        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;


        dom.settingsModal.style.display = 'flex';
        const modalContent = dom.settingsModal.querySelector('.modal-content');
        modalContent.classList.remove('animate__fadeOutDown', 'animate__zoomOut', 'animate__fadeOut'); // Clean up previous out animations
        const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInUp' : 'animate__fadeIn') : '';
        if (animIn) modalContent.classList.add('animate__animated', animIn);
        if (state.animationLevel !== 'none') modalContent.style.setProperty('--animate-duration', '0.3s');
    }

    function closeSettingsModal(revertChanges = true) {
        if (revertChanges) {
            // Revert settings to previously saved values from localStorage
            applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
            applyAnimationLevel(localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full');
            state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || 'true') === 'true';
            state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || 'false') === 'true';
            state.showChatBubblesThink = (localStorage.getItem(APP_PREFIX + 'showChatBubblesThink') || 'true') === 'true';
            state.showLogBubblesThink = (localStorage.getItem(APP_PREFIX + 'showLogBubblesThink') || 'true') === 'true';
            state.autoSubmitQuickActions = (localStorage.getItem(APP_PREFIX + 'autoSubmitQuickActions') || 'true') === 'true';

            // Update UI elements to reflect reverted state
            if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
            if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
            if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
            if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
            if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;
        }

        const modalContent = dom.settingsModal.querySelector('.modal-content');
        modalContent.classList.remove('animate__fadeInUp', 'animate__zoomIn', 'animate__fadeIn');
        const animOut = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeOutDown' : 'animate__fadeOut') : '';

        const animationEndHandler = () => {
            dom.settingsModal.style.display = 'none';
            if (animOut) modalContent.classList.remove('animate__animated', animOut); // Clean up
        };

        if (state.animationLevel !== 'none' && animOut) {
            modalContent.classList.add('animate__animated', animOut);
            modalContent.addEventListener('animationend', animationEndHandler, { once: true });
        } else {
            animationEndHandler(); // No animation, just hide
        }
    }

    function collectAndSaveSettings() {
        applyTheme(dom.themeSelect.value); // This also saves theme to state and localStorage
        applyFontSize(dom.fontSizeInput.value); // This also updates body style
        applyAnimationLevel(dom.animationLevelSelect.value); // This also saves to state

        state.autoScroll = dom.autoScrollToggle.checked;
        state.soundEnabled = dom.soundEnabledToggle.checked;
        state.showChatBubblesThink = dom.showChatBubblesThinkToggle.checked;
        state.showLogBubblesThink = dom.showLogBubblesThinkToggle.checked;
        state.autoSubmitQuickActions = dom.autoSubmitQuickActionsToggle.checked;

        saveSettings(); // Save all collected settings to localStorage
    }

    function saveSettings() {
        localStorage.setItem(APP_PREFIX + 'theme', state.currentTheme);
        localStorage.setItem(APP_PREFIX + 'fontSize', document.body.style.fontSize.replace('px', ''));
        localStorage.setItem(APP_PREFIX + 'animationLevel', state.animationLevel);
        localStorage.setItem(APP_PREFIX + 'autoScroll', state.autoScroll.toString());
        localStorage.setItem(APP_PREFIX + 'soundEnabled', state.soundEnabled.toString());
        localStorage.setItem(APP_PREFIX + 'showChatBubblesThink', state.showChatBubblesThink.toString());
        localStorage.setItem(APP_PREFIX + 'showLogBubblesThink', state.showLogBubblesThink.toString());
        localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());
        localStorage.setItem(APP_PREFIX + 'sessionManagerCollapsed', state.isSessionManagerCollapsed.toString());
        localStorage.setItem(APP_PREFIX + 'processLogVisible', state.isProcessLogVisible.toString()); // Save log visibility
        localStorage.setItem(APP_PREFIX + 'processLogCollapsed', state.isProcessLogCollapsed.toString());
        localStorage.setItem(APP_PREFIX + 'autoSubmitQuickActions', state.autoSubmitQuickActions.toString());
        localStorage.setItem(APP_PREFIX + 'currentMode', state.currentMode);
        console.log("Settings saved to localStorage.");
    }

    function loadSettings() {
        state.currentTheme = localStorage.getItem(APP_PREFIX + 'theme') || 'auto';
        state.animationLevel = localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full';

        state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || 'true') === 'true';
        state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || 'false') === 'true';
        state.showChatBubblesThink = (localStorage.getItem(APP_PREFIX + 'showChatBubblesThink') || 'true') === 'true';
        state.showLogBubblesThink = (localStorage.getItem(APP_PREFIX + 'showLogBubblesThink') || 'true') === 'true';
        state.isSidebarExpanded = (localStorage.getItem(APP_PREFIX + 'sidebarExpanded') || (window.innerWidth > 768).toString()) === 'true';
        state.isSessionManagerCollapsed = (localStorage.getItem(APP_PREFIX + 'sessionManagerCollapsed') || 'false') === 'true';
        state.isProcessLogVisible = (localStorage.getItem(APP_PREFIX + 'isProcessLogVisible') || 'false') === 'true';
        state.isProcessLogCollapsed = (localStorage.getItem(APP_PREFIX + 'processLogCollapsed') || 'true') === 'true';
        state.autoSubmitQuickActions = (localStorage.getItem(APP_PREFIX + 'autoSubmitQuickActions') || 'true') === 'true';
        state.currentMode = localStorage.getItem(APP_PREFIX + 'currentMode') || 'chat';


        // Update modal UI elements if they exist (called after DOM elements are certain to be there)
        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;

        // Apply current mode to sidebar buttons
        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === state.currentMode));
        const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || 'current session';
        dom.userInput.placeholder = `Message in ${getModeDisplayName(state.currentMode)} mode (${sessionNameForPlaceholder})...`;

    }

    function resetToDefaultSettings() {
        const defaults = {
            theme: 'auto',
            fontSize: '16',
            animationLevel: 'full',
            autoScroll: true,
            soundEnabled: false,
            showChatBubblesThink: true,
            showLogBubblesThink: true,
            sidebarExpanded: window.innerWidth > 768,
            sessionManagerCollapsed: false,
            isProcessLogVisible: false,
            processLogCollapsed: true,
            autoSubmitQuickActions: true,
            currentMode: 'chat',
        };
        applyTheme(defaults.theme); // This saves state.currentTheme
        applyFontSize(defaults.fontSize); // This styles body
        applyAnimationLevel(defaults.animationLevel); // This saves state.animationLevel
        state.autoScroll = defaults.autoScroll;
        state.soundEnabled = defaults.soundEnabled;
        state.showChatBubblesThink = defaults.showChatBubblesThink;
        state.showLogBubblesThink = defaults.showLogBubblesThink;
        state.autoSubmitQuickActions = defaults.autoSubmitQuickActions;
        state.currentMode = defaults.currentMode;

        updateSidebarState(defaults.sidebarExpanded, true);
        updateSessionManagerState(defaults.sessionManagerCollapsed, true);
        state.isProcessLogVisible = defaults.isProcessLogVisible; // Update state before UI function
        if (state.isProcessLogVisible) showProcessLog(true); else hideProcessLog();
        updateProcessLogCollapseState(defaults.processLogCollapsed, true);


        // Update modal UI to reflect defaults
        if (dom.themeSelect) dom.themeSelect.value = defaults.theme;
        if (dom.fontSizeInput) dom.fontSizeInput.value = defaults.fontSize;
        if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${defaults.fontSize}px`;
        if (dom.animationLevelSelect) dom.animationLevelSelect.value = defaults.animationLevel;
        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = defaults.autoScroll;
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = defaults.soundEnabled;
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = defaults.showChatBubblesThink;
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = defaults.showLogBubblesThink;
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = defaults.autoSubmitQuickActions;

        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === defaults.currentMode));
        const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || 'current session';
        dom.userInput.placeholder = `Message in ${getModeDisplayName(defaults.currentMode)} mode (${sessionNameForPlaceholder})...`;

        saveSettings(); // Persist all default settings
        showToast('All parameters reset to factory settings!', 'success');
    }

    function showToast(message, type = 'info', duration = 3500) {
        const toast = document.createElement('div');
        toast.classList.add('toast', type);
        const animIn = state.animationLevel !== 'none' ? 'animate__fadeInRight' : ''; // Default In animation
        const animOut = state.animationLevel !== 'none' ? 'animate__fadeOutRight' : ''; // Default Out animation

        if (state.animationLevel !== 'none' && animIn) {
            toast.classList.add('animate__animated', animIn);
            toast.style.setProperty('--animate-duration', '0.4s');
        }

        const icons = { 'info': 'fa-info-circle', 'success': 'fa-check-circle', 'warning': 'fa-exclamation-triangle', 'error': 'fa-times-circle' };
        const iconClass = icons[type] || 'fa-info-circle';

        toast.innerHTML = `
            <i class="fas ${iconClass} toast-icon"></i>
            <span class="toast-message">${message.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</span>
            <button class="toast-close icon-btn"><i class="fas fa-times"></i></button>`;

        toast.querySelector('.toast-close').addEventListener('click', () => removeToast(toast, animOut));
        dom.toastContainer.appendChild(toast);

        setTimeout(() => removeToast(toast, animOut), duration);
    }

    function removeToast(toast, animOut) {
        if (toast.parentElement) { // Check if still in DOM
            if (state.animationLevel !== 'none' && animOut && toast.classList.contains('animate__animated')) {
                toast.classList.remove(toast.classList.contains('animate__fadeInRight') ? 'animate__fadeInRight' : 'animate__fadeIn'); // Remove specific in-animation
                toast.classList.add(animOut);
                toast.addEventListener('animationend', () => toast.remove(), { once: true });
            } else {
                toast.remove();
            }
        }
    }

    function attachQuickActionButtonListeners(container) {
        container.querySelectorAll('.quick-action-btn').forEach(button => {
            // Remove existing listener to prevent duplicates if re-attaching
            button.removeEventListener('click', handleQuickActionButtonClick);
            button.addEventListener('click', handleQuickActionButtonClick);
        });
    }

    function handleQuickActionButtonClick(e) {
        e.preventDefault();
        const messageToSend = e.target.dataset.message;
        if (messageToSend) {
            dom.userInput.value = messageToSend;
            adjustTextareaHeight();
            updateCharCounter();
            dom.userInput.focus();
            if (state.autoSubmitQuickActions) { // New setting check
                handleSendMessage();
            }
        }
    }

    // ======== Initialize Application ========
    initializeApp();
    // Initial attachment for welcome message quick actions (if any are rendered initially)
    attachQuickActionButtonListeners(dom.chatBox);
});