// 当整个 HTML 文档加载完成并解析完毕后执行回调函数
document.addEventListener('DOMContentLoaded', () => {
    // ======== DOM 元素获取 (集中管理，方便维护) ========
    const dom = {
        // Page background
        pageBackgroundGradient: document.querySelector('.page-background-gradient'),

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
        appHeader: document.getElementById('app-header'),
        themeToggleButton: document.getElementById('theme-toggle'),
        themeToggleIcon: document.querySelector('#theme-toggle i'),
        clearChatButton: document.getElementById('clear-chat'),
        manageSessionsToggle: document.getElementById('manage-sessions-toggle'),
        toggleProcessLogVisibilityButton: document.getElementById('toggle-process-log-visibility'),

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
        inputArea: document.getElementById('input-area'),
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
        toggleProcessLogCollapseButton: document.getElementById('toggle-process-log-collapse'),

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
        showChatBubblesThinkToggle: document.getElementById('show-chat-bubbles-think'),
        showLogBubblesThinkToggle: document.getElementById('show-log-bubbles-think'),
        autoSubmitQuickActionsToggle: document.getElementById('auto-submit-quick-actions'),
        resetSettingsButton: document.getElementById('reset-settings'),
        saveSettingsButton: document.getElementById('save-settings'),
    };

    // ======== 应用状态与配置 ========
    // VERSION UPDATE: APP_PREFIX changed to reflect V8.3.2 CamelCase Reasoning
    const APP_PREFIX = 'IDTAgentPro_v8.3.2_CamelCaseReasoning_';
    let state = {
        sessions: {},
        currentSessionId: null,
        currentTheme: 'auto',
        autoScroll: true,
        soundEnabled: false,
        showChatBubblesThink: true,
        showLogBubblesThink: true,
        animationLevel: 'full',
        currentMode: 'chat',
        uploadedFiles: [],
        isAgentTyping: false,
        isLoading: false,
        isSidebarExpanded: window.innerWidth > 768,
        isSessionManagerCollapsed: false,
        isProcessLogVisible: false,
        isProcessLogCollapsed: true,
        maxInputChars: 4000,
        currentClientRequestId: null,
        lastResponseThinking: null, // This will store thinking log content for process log if needed
        autoSubmitQuickActions: true,
        pendingToolCalls: {} // Keyed by toolCallId (camelCase)
    };

    // ======== WebSocket 相关 ========
    let websocket = null;
    const websocketUrl = `ws://${window.location.host}/ws/chat`;
    let wsReconnectAttempts = 0;
    const MAX_WS_RECONNECT_ATTEMPTS = 5;
    const WS_RECONNECT_INTERVAL = 3000;

    function connectWebSocket() {
        if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
            console.log("WebSocket is already connected or connecting.");
            return;
        }
        console.log(`Attempting to connect WebSocket (Attempt ${wsReconnectAttempts + 1}): ${websocketUrl}`);
        if (dom.loader && wsReconnectAttempts === 0) {
            const loadingText = dom.loader.querySelector('.loading-text');
            // VERSION UPDATE: Loading text reflects V8.3.2
            if (loadingText) loadingText.textContent = "Establishing secure link (V8.3.2 CamelCase Reasoning)...";
        }

        websocket = new WebSocket(websocketUrl);

        websocket.onopen = (event) => {
            console.log("WebSocket connection established", event);
            wsReconnectAttempts = 0;
            // VERSION UPDATE: Toast message reflects V8.3.2
            showToast("Communication link active (V8.3.2 CamelCase Reasoning).", "success", 3000);
            sendWebSocketMessage({
                type: 'init',
                session_id: state.currentSessionId // Backend will expect session_id
            });
        };

        websocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                console.log("WS RX:", message);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error("Failed to parse WebSocket message:", e, "Raw data:", event.data);
                showToast("Received invalid data format from server.", "error");
            }
        };

        websocket.onerror = (event) => {
            console.error("WebSocket error:", event);
        };

        websocket.onclose = (event) => {
            console.log("WebSocket connection closed:", event);
            hideTypingIndicator();
            setLoadingState(false);
            websocket = null;

            const reason = event.reason ? `Reason: ${event.reason}` : (event.wasClean ? 'Connection closed cleanly.' : 'Connection lost unexpectedly.');
            const codeMsg = `(Code: ${event.code})`;

            if (!event.wasClean && wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                wsReconnectAttempts++;
                showToast(`Link lost. Attempting to re-establish (${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})... ${codeMsg}`, "warning", WS_RECONNECT_INTERVAL);
                setTimeout(connectWebSocket, WS_RECONNECT_INTERVAL);
            } else if (!event.wasClean) {
                showToast(`Communication link permanently lost after ${MAX_WS_RECONNECT_ATTEMPTS} attempts. Please refresh. ${codeMsg} ${reason}`, "error", 10000);
                if (dom.loader) {
                    const loadingText = dom.loader.querySelector('.loading-text');
                    if (loadingText) loadingText.textContent = "Connection Error. Please refresh.";
                    dom.loaderProgress.style.width = '0%';
                    dom.loader.classList.remove('hidden');
                }
            } else {
                showToast(`Communication link closed. ${codeMsg} ${reason}`, "info", 5000);
            }
        };
    }

    function sendWebSocketMessage(message) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            // Assuming backend expects snake_case keys for incoming messages like 'session_id', 'request_id'
            // If backend also expects camelCase for *incoming* messages, this would need adjustment.
            // For now, we assume the structure sent to backend remains with snake_case keys as per original.
            const messageStr = JSON.stringify(message);
            console.log("WS TX:", message); // Log the exact object being sent
            websocket.send(messageStr);
        } else {
            console.error("WebSocket connection not open. Cannot send message:", message);
            showToast("Communication link not active. Please wait or try reconnecting.", "warning");
            if (!websocket || websocket.readyState === WebSocket.CLOSED || websocket.readyState === WebSocket.CLOSING) {
                if (wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                    connectWebSocket();
                } else {
                    showToast("Cannot send: Max reconnection attempts reached. Please refresh.", "error");
                }
            }
        }
    }

    function handleWebSocketMessage(message) {
        // Assuming backend will send session_id, agent_available with snake_case keys for 'init_success'
        // and 'type', 'message', 'details' also with snake_case.
        // The primary change is for the 'final_response' and 'plan_details' type messages
        // where the nested JSON payload (e.g., final_v8_3_2_camelcase_json_if_success) uses camelCase.

        switch (message.type) {
            case 'init_success':
                // Assuming message.session_id and message.agent_available are sent as snake_case by backend
                state.currentSessionId = message.session_id;
                localStorage.setItem(APP_PREFIX + 'lastSessionId', state.currentSessionId);

                // VERSION UPDATE: Agent status message reflects V8.3.2
                const agentStatusMessage = message.agent_available === false
                    ? 'Agent core module not loaded. Functionality limited. (V8.3.2)'
                    : 'Communication link established. Agent (V8.3.2 CamelCase Reasoning) ready!';
                const agentStatusType = message.agent_available === false ? 'warning' : 'success';
                showToast(agentStatusMessage, agentStatusType, message.agent_available ? 4000 : 7000);

                if (!state.sessions[state.currentSessionId]) {
                    const now = Date.now();
                    state.sessions[state.currentSessionId] = {
                        id: state.currentSessionId,
                        name: `Session ${Object.keys(state.sessions).length + 1}`,
                        messages: [],
                        createdAt: now,
                        lastActivity: now,
                    };
                    saveSessions();
                }
                initializeCurrentSessionUI(true);

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
                     // VERSION UPDATE
                    appendMessage("Apologies, the Agent's core module failed to load. I am unable to process your requests at this time. (V8.3.2)", 'error-system', false, null, false, [], "System Error");
                }
                setLoadingState(false);
                break;

            case 'error': // General server-side errors
                console.error("Server-reported error:", message);
                showToast(`Server error: ${message.message}`, 'error', 6000);
                if (message.details) { // Assuming message.details is still snake_case or simple structure
                    appendMessage(`Server error (${message.message}): ${message.details}`, 'error-system', false, null, false, [], "Server Error");
                }
                setLoadingState(false);
                break;

            case 'general_status': // Assuming keys like stage, status, message, details remain snake_case from backend
                handleGeneralStatus(message);
                break;
            case 'llm_communication_status': // Assuming keys like llm_phase, status, message, details remain snake_case
                handleLlmCommStatus(message);
                break;
            case 'thinking_log': // Assuming keys like stage, content, llm_interaction_id remain snake_case
                handleThinkingLog(message);
                break;
            case 'plan_details': // This message's 'plan' array will contain objects with camelCase keys
                handlePlanDetails(message);
                break;
            case 'tool_status_update': // Assuming tool_call_id, tool_name, status, message, details remain snake_case
                                     // for the top-level keys of this message type. The *content* of 'details' might
                                     // need camelCase if it mirrors parts of the LLM's JSON output.
                handleToolStatusUpdate(message);
                break;
            case 'interim_response': // Assuming content, llm_interaction_id remain snake_case
                handleInterimResponse(message);
                break;
            case 'final_response':
                // KEY CHANGE: This function will now look for a key like `final_v8_3_2_camelcase_json_if_success`
                // (or whatever the backend confirms) which contains the camelCased JSON.
                // The top-level keys `content` and `llm_interaction_id` in the 'final_response' message itself
                // are assumed to remain snake_case as sent by the Python WebSocket handler.
                handleFinalResponse(message);
                break;

            default:
                console.warn("Received unknown WebSocket message type:", message.type, message);
        }
    }

    function handleGeneralStatus(msg) {
        // Assuming msg.stage, msg.status, msg.message, msg.details are snake_case from backend
        const { stage, status, message: msgText, details } = msg;
        let logIconClass = 'fas fa-info-circle log-info';
        // Keep snake_case for CSS class consistency if these are directly used
        let logItemClasses = `type-general_status stage-${stage} status-${status}`;

        if (status === 'started' || status === 'llm_retry_needed' || status === 'llm_error_retrying') logIconClass = 'fas fa-spinner fa-spin log-info';
        else if (status === 'completed' || status === 'received' || status === 'completed_and_validated') logIconClass = 'fas fa-check-circle log-success';
        else if (status === 'error' || status === 'failed' || status === 'failed_after_llm_retries' || status === 'tool_failure_detected') {
            logIconClass = 'fas fa-times-circle log-error';
        }
        else if (status === 'ignored') logIconClass = 'fas fa-eye-slash log-muted';

        appendLogItem(msgText, logIconClass, logItemClasses, details); // details here are top-level, might be snake_case
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handleLlmCommStatus(msg) {
        // Assuming msg.llm_phase, msg.status, msg.message, msg.details are snake_case
        const { llm_phase, status, message: msgText, details } = msg;
        let logIconClass = 'fas fa-brain log-info';
        let logItemClasses = `type-llm_communication_status phase-${llm_phase} status-${status}`;

        if (status === 'started') logIconClass = 'fas fa-brain fa-fade log-info';
        else if (status === 'completed') logIconClass = 'fas fa-check log-success';
        else if (status === 'error') logIconClass = 'fas fa-exclamation-triangle log-error';

        appendLogItem(msgText, logIconClass, logItemClasses, details); // details here top-level, might be snake_case
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handleThinkingLog(msg) {
        // Assuming msg.stage, msg.content, msg.llm_interaction_id are snake_case
        const { stage, content, llm_interaction_id } = msg; // Renaming for clarity if backend sends llmInteractionId
        if (content) {
            state.lastResponseThinking = content;
        }

        if (state.showLogBubblesThink) {
            const thinkLabel = `Agent Thinking (${stage.replace(/_/g, ' ')})`;
            appendLogItemWithThink(thinkLabel, 'fas fa-comment-dots log-think', `type-thinking_log stage-${stage} llm-id-${llm_interaction_id}`, content, "Detailed Thought Process:");
        } else {
            appendLogItem(`Thinking log received (${stage}, LLM_ID: ${llm_interaction_id}) - ${content.substring(0, 70)}...`, 'fas fa-comment-dots log-muted', `type-thinking_log stage-${stage} muted`);
        }
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handlePlanDetails(msg) {
        // CORE CHANGE: The `plan` array items are now expected to have camelCase keys
        // e.g., toolCallId, toolName, toolArguments, uiHints, order.
        const { plan } = msg; // `plan` is an array of objects
        state.pendingToolCalls = {}; // Reset pending calls
        plan.forEach(toolCall => { // toolCall is an object from the plan array
            // Access using camelCase keys
            const toolCallId = toolCall.toolCallId;
            const toolName = toolCall.toolName;
            const toolArguments = toolCall.toolArguments; // This is an object
            const uiHints = toolCall.uiHints || {};     // This is an object
            const order = toolCall.order;

            state.pendingToolCalls[toolCallId] = { // Store with camelCase toolCallId as key
                name: toolName,
                args_summary: summarizeArguments(toolArguments), // summarizeArguments can handle any object
                ui_hints: uiHints,
                order: order
            };
            const displayName = uiHints.displayNameForTool || toolName;
            appendLogItem(
                `Plan item #${order}: ${displayName} (ID: ${toolCallId}) - Status: Pending`,
                'fas fa-list-check log-info',
                `type-plan_details tool-${toolName} status-pending`,
                { arguments: toolArguments, tool_call_id: toolCallId } // For log details, use camelCase if it mirrors LLM
            );
        });
        if (state.isProcessLogVisible) showProcessLog(true);
    }

    function handleToolStatusUpdate(msg) {
        // Assuming top-level keys here (tool_call_id, tool_name, status, message, details) are snake_case
        // If backend changes these to camelCase, update here.
        const { tool_call_id, tool_name, status, message: msgText, details } = msg;
        let logIconClass = 'fas fa-cog log-info';
        let itemStatusClass = `status-${status}`;

        if (status === 'running') {
            logIconClass = 'fas fa-cog fa-spin log-info';
        } else if (status === 'retrying') {
            logIconClass = 'fas fa-history log-info';
        } else if (status === 'succeeded') {
            logIconClass = 'fas fa-check-circle log-success';
        } else if (status === 'failed') {
            logIconClass = 'fas fa-times-circle log-error';
        } else if (status === 'aborted_due_to_previous_failure') {
            logIconClass = 'fas fa-ban log-warning';
            itemStatusClass = 'status-aborted';
        }

        // IMPORTANT: `state.pendingToolCalls` is keyed by `toolCallId` (camelCase) from `handlePlanDetails`.
        // So, if `tool_call_id` from this message is snake_case, we need to be careful.
        // Assuming backend sends `tool_call_id` matching the `toolCallId` in the plan.
        const pendingToolInfo = state.pendingToolCalls[tool_call_id]; // Use as is, assuming consistency
        const displayName = pendingToolInfo?.ui_hints?.displayNameForTool || tool_name;
        let fullLogMessage = `Tool: ${displayName} (ID: ${tool_call_id}) - ${status.replace(/_/g, ' ').toUpperCase()}: ${msgText}`;

        let existingLogItem = dom.processLogContent.querySelector(`.log-item[data-tool-call-id="${tool_call_id}"]`);

        if (existingLogItem) {
            existingLogItem.className = `log-item animate__animated type-tool_status_update tool-${tool_name} ${itemStatusClass}`;
            const iconEl = existingLogItem.querySelector('i:first-child');
            if (iconEl) iconEl.className = logIconClass;
            const messageEl = existingLogItem.querySelector('.log-item-message');
            if (messageEl) messageEl.textContent = fullLogMessage;

            let detailsEl = existingLogItem.querySelector('.log-item-details');
            // The 'details' object from this message might also need camelCase parsing if it mirrors LLM JSON structure.
            if (details && Object.keys(details).length > 0) {
                if (!detailsEl) {
                    detailsEl = document.createElement('div');
                    detailsEl.className = 'log-item-details';
                    existingLogItem.querySelector('.log-item-text-wrapper').appendChild(detailsEl);
                }
                const formattedDetailsHtml = formatLogDetails(details, 'tool_status_update', null, status); // formatLogDetails needs to handle camelCase if 'details' uses it
                detailsEl.innerHTML = formattedDetailsHtml || '';
            } else if (detailsEl) {
                detailsEl.innerHTML = '';
            }
            existingLogItem.classList.remove('animate__flash', 'animate__headShake');
            if (status === 'failed') existingLogItem.classList.add('animate__headShake');
            else existingLogItem.classList.add('animate__flash');
            existingLogItem.style.setProperty('--animate-duration', '0.5s');

        } else {
            const logItemDiv = appendLogItem(fullLogMessage, logIconClass, `type-tool_status_update tool-${tool_name} ${itemStatusClass}`, details); // details to formatLogDetails
            if (logItemDiv) logItemDiv.dataset.toolCallId = tool_call_id;
        }

        if (state.isProcessLogVisible) showProcessLog(false);

        if (status === 'succeeded' || status === 'failed' || status === 'aborted_due_to_previous_failure') {
            if (state.pendingToolCalls[tool_call_id]) { // Assuming tool_call_id matches key
                delete state.pendingToolCalls[tool_call_id];
            }
        }
    }

    function handleInterimResponse(msg) {
        // Assuming msg.content, msg.llm_interaction_id are snake_case
        const { content, llm_interaction_id } = msg;
        appendLogItem(
            `Agent Intention: "${content.substring(0, 150)}${content.length > 150 ? '...' : ''}"`,
            'fas fa-bullhorn log-info',
            'type-agent_intention',
            // Details here are simple, can remain snake_case for internal logging
            { llm_interaction_id: llm_interaction_id, full_content: content }
        );
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handleFinalResponse(msg) {
        hideTypingIndicator();
        setLoadingState(false);
        state.currentClientRequestId = null;
        state.pendingToolCalls = {}; // Clear pending calls on final response

        // Top-level keys from WebSocket message (assumed snake_case from Python backend)
        const { content, llm_interaction_id } = msg; // content is the fallback/raw text. llm_interaction_id from the WS message.
        
        // CORE CHANGE: The actual structured JSON is now in a specific (camelCased) field.
        // Let's assume backend sends it as `final_v8_3_2_camelcase_json_if_success`.
        // If this key is different, it needs to be adjusted here.
        const finalCamelCaseJson = msg.final_v8_3_2_camelcase_json_if_success; // Access the camelCased JSON object

        let thinkingForBubble = null;
        let actualContentForBubble = content; // Fallback to raw content if JSON parsing fails

        if (finalCamelCaseJson && finalCamelCaseJson.status === 'success') {
            // All keys inside finalCamelCaseJson are camelCase as per V8.3.2 spec.
            if (finalCamelCaseJson.thoughtProcess) { // This is from <think> block, placed by OutputParser
                thinkingForBubble = finalCamelCaseJson.thoughtProcess;
            }
            if (finalCamelCaseJson.decision &&
                finalCamelCaseJson.decision.responseToUser &&
                finalCamelCaseJson.decision.responseToUser.content) { // Accessing camelCase keys
                actualContentForBubble = finalCamelCaseJson.decision.responseToUser.content;

                const suggestions = finalCamelCaseJson.decision.responseToUser.suggestionsForNextSteps; // camelCase key
                if (suggestions && Array.isArray(suggestions) && suggestions.length > 0) {
                    let suggestionsText = "\n\n<div class=\"final-response-suggestions\"><strong>Next steps you might consider:</strong><ul>";
                    suggestions.forEach(sugg => { // sugg object also uses camelCase keys
                        if (sugg.textForUser) { // camelCase key
                            // data-message should be safe for HTML attribute if it's plain text
                            suggestionsText += `<li><a href="#" class="quick-action-btn" data-message="${sugg.textForUser.replace(/"/g, '&quot;')}">${sugg.textForUser}</a></li>`;
                        }
                    });
                    suggestionsText += "</ul></div>";
                    actualContentForBubble += suggestionsText;
                    appendMessage(actualContentForBubble, 'agent', true, thinkingForBubble, false, [], null);
                } else {
                    appendMessage(actualContentForBubble, 'agent', false, thinkingForBubble, false, [], null);
                }
            } else { // Content missing in the camelCase JSON structure
                appendMessage(actualContentForBubble, 'agent', false, thinkingForBubble, false, [], "ContentMissingInV8_3_2_JSON");
            }
        } else {
            // Fallback if finalCamelCaseJson is not available, indicates failure, or parsing failed.
            thinkingForBubble = state.lastResponseThinking; // Use cached thinking if any
            appendMessage(actualContentForBubble, 'agent', false, thinkingForBubble, false, [], "ErrorResponseOrNo_V8_3_2_JSON");
        }

        addMessageToCurrentSession({
            content: actualContentForBubble,
            sender: 'agent',
            timestamp: Date.now(),
            isHTML: (finalCamelCaseJson?.decision?.responseToUser?.suggestionsForNextSteps?.length > 0), // check camelCase path
            // Store the new camelCase JSON structure
            rawResponseV8_3_2_CamelCase: finalCamelCaseJson,
            thinking: thinkingForBubble,
        });
        state.lastResponseThinking = null; // Clear after use

        if (state.sessions[state.currentSessionId]) {
            state.sessions[state.currentSessionId].lastActivity = Date.now();
        }
        saveSessions();
        renderSessionList();

        // Log details can be the summary or the raw camelCased JSON (or parts of it)
        const llmIdForLog = finalCamelCaseJson?.llmInteractionId || llm_interaction_id || 'N/A'; // Prefer ID from JSON
        appendLogItem(`Agent final response delivered (LLM_ID: ${llmIdForLog})`, 'fas fa-flag-checkered log-success', 'type-final_response', finalCamelCaseJson ? { summary: actualContentForBubble.substring(0,100)+"...", raw_response: finalCamelCaseJson } : { error_details: "Response generation indicated failure or missing V8.3.2 JSON." });
        if (state.isProcessLogVisible) showProcessLog(true);
    }


    function setLoadingState(isLoading) {
        state.isLoading = isLoading;
        dom.sendButton.disabled = isLoading;
        dom.userInput.disabled = isLoading;
        dom.sendIcon.style.display = isLoading ? 'none' : 'inline-block';
        dom.sendLoadingIcon.style.display = isLoading ? 'inline-block' : 'none';
        if (isLoading) {
            dom.sendButton.title = "Processing...";
        } else {
            dom.sendButton.title = "Send message";
        }
    }

    function summarizeArguments(argsObj) { // This function is generic, handles any object
        if (!argsObj || typeof argsObj !== 'object' || Object.keys(argsObj).length === 0) {
            return "(No args)";
        }
        try {
            return JSON.stringify(argsObj, (key, value) => {
                if (typeof value === 'string' && value.length > 30) {
                    return value.substring(0, 27) + "...";
                }
                return value;
            }).substring(0, 150);
        } catch (e) {
            return "(Error summarizing args)";
        }
    }

    function parseItemClasses(itemClassesStr) { // Generic helper
        const classes = itemClassesStr ? itemClassesStr.split(' ') : [];
        const parsed = { type: null, stage: null, status: null };
        classes.forEach(cls => {
            if (cls.startsWith('type-')) parsed.type = cls.substring(5);
            else if (cls.startsWith('stage-')) parsed.stage = cls.substring(6);
            else if (cls.startsWith('status-')) parsed.status = cls.substring(7);
            else if (cls.startsWith('phase-')) parsed.stage = cls.substring(6); // Alias for stage
        });
        return parsed;
    }

    function formatLogDetails(details, type, stage, status) {
        // This function now needs to be robust to keys being either snake_case (from older parts or direct Python)
        // OR camelCase (from new LLM JSON structures or plan_details/tool_status_update if backend standardizes).
        // For simplicity, we'll assume `details` passed here from `handlePlanDetails` or `handleToolStatusUpdate`
        // might contain camelCased keys if they originate from the LLM's JSON.
        // The formatting logic itself tries to make keys more readable.
        let html = '';
        const addDetailKeyValue = (key, value, indentLevel = 0) => {
            const sanitizedValue = String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
            const paddingLeftStyle = `padding-left: ${indentLevel * 10}px;`;
            // Convert both snake_case and camelCase to "Title Case With Spaces"
            const formattedKey = key
                .replace(/([A-Z])/g, " $1") // Add space before uppercase letters (for camelCase)
                .replace(/_/g, ' ')        // Replace underscores (for snake_case)
                .trim()
                .replace(/\b\w/g, char => char.toUpperCase());
            return `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>${formattedKey}:</strong> <span>${sanitizedValue}</span></div>`;
        };

        const formatRecursive = (obj, currentType, currentStage, currentStatus, indentLevel = 0) => {
            let partHtml = '';
            for (const key in obj) {
                if (Object.prototype.hasOwnProperty.call(obj, key)) {
                    const value = obj[key];
                    const displayKey = key // Use original key for specific checks, then format for display
                        .replace(/([A-Z])/g, " $1")
                        .replace(/_/g, ' ')
                        .trim()
                        .replace(/\b\w/g, char => char.toUpperCase());
                    const paddingLeftStyle = `padding-left: ${indentLevel * 10}px;`;

                    // Special handling based on original key (camelCase or snake_case)
                    if ((type === 'plan_details' && key === 'toolCallId') || (type === 'tool_status_update' && key === 'tool_call_id')) continue; // Already in main log message

                    if (key === 'uiHints' && typeof value === 'object' && value !== null) { // uiHints is camelCase
                        const dn = String(value.displayNameForTool || 'N/A').replace(/</g, "&lt;").replace(/>/g, "&gt;"); // displayNameForTool is camelCase
                        const ed = String(value.estimatedDurationCategory || 'N/A').replace(/</g, "&lt;").replace(/>/g, "&gt;"); // estimatedDurationCategory is camelCase
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>UI Hints:</strong> <span>Display: ${dn}, Duration: ${ed}</span></div>`;
                    } else if (key === 'result_data_preview' && typeof value === 'string') { // Assuming snake_case from _send_tool_status_update
                        let previewContent = String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>Result Preview:</strong> <pre class="log-detail-preview-code"><code>${previewContent}</code></pre></div>`;
                    } else if ((type === 'plan_details' || type === 'tool_status_update') && key === 'arguments' && typeof value === 'object' && value !== null) { // 'arguments' in log, 'toolArguments' in LLM JSON
                        let argItems = [];
                        for (const argKey in value) { // argKey is from tool schema (e.g., component_type)
                            const formattedArgKey = argKey.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                            argItems.push(`<em>${formattedArgKey}</em>: ${String(value[argKey]).replace(/</g, "&lt;").replace(/>/g, "&gt;")}`);
                        }
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>Arguments:</strong> <span>${argItems.join('; ')}</span></div>`;
                    } else if (key === 'toolArguments' && typeof value === 'object' && value !== null) { // Explicitly for toolArguments from LLM JSON
                        let argItems = [];
                        for (const argKey in value) {
                            const formattedArgKey = argKey.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                            argItems.push(`<em>${formattedArgKey}</em>: ${String(value[argKey]).replace(/</g, "&lt;").replace(/>/g, "&gt;")}`);
                        }
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>Tool Arguments:</strong> <span>${argItems.join('; ')}</span></div>`;
                    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>${displayKey}:</strong></div>`;
                        partHtml += formatRecursive(value, currentType, currentStage, currentStatus, indentLevel + 1);
                    } else if (Array.isArray(value)) {
                        const arrayItems = value.map(item => {
                            if (typeof item === 'object' && item !== null) return JSON.stringify(item).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                            return String(item).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        });
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong>${displayKey}:</strong> <span>[${arrayItems.join(', ')}]</span></div>`;
                    } else {
                        partHtml += addDetailKeyValue(key, value, indentLevel); // addDetailKeyValue handles formatting key
                    }
                }
            }
            return partHtml;
        };
        html = formatRecursive(details, type, stage, status, 0);
        return html || null;
    }


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
            // formatLogDetails will handle potential camelCase keys in `details`
            const formattedDetailsHtml = formatLogDetails(details, type, stage, status);

            if (formattedDetailsHtml) {
                detailsEl.innerHTML = formattedDetailsHtml;
            } else { // Fallback to raw JSON string if formatting returns nothing
                try {
                    let detailsText = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details);
                    detailsEl.innerHTML = `<pre><code>${detailsText.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>`;
                } catch (e) {
                    detailsEl.textContent = String(details); // Fallback for unstringifiable objects
                }
            }
            textWrapperEl.appendChild(detailsEl);
        }

        logItemDiv.appendChild(iconEl);
        logItemDiv.appendChild(textWrapperEl);
        dom.processLogContent.appendChild(logItemDiv);
        scrollToProcessLogBottom();
        return logItemDiv;
    }


    function appendLogItemWithThink(headerText, headerIconClass, itemClasses, thinkContent, thinkBubbleLabel = "Thought Process") {
        const logItemDiv = document.createElement('div');
        logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
        logItemDiv.style.setProperty('--animate-duration', '0.3s');
        if (itemClasses) logItemDiv.classList.add(...itemClasses.split(' '));

        const headerDiv = document.createElement('div');
        headerDiv.style.display = 'flex';
        headerDiv.style.alignItems = 'center';
        headerDiv.style.gap = 'var(--spacing-unit)';

        const iconEl = document.createElement('i');
        iconEl.className = headerIconClass;
        headerDiv.appendChild(iconEl);

        const textEl = document.createElement('span');
        textEl.className = 'log-item-message';
        textEl.textContent = headerText;
        headerDiv.appendChild(textEl);
        logItemDiv.appendChild(headerDiv);

        if (thinkContent) {
            const thinkDiv = document.createElement('div');
            thinkDiv.classList.add('log-think-content');
            let formattedThink = thinkContent.replace(/\n/g, '<br>');
            const jsonBlockRegex = /```json([\s\S]*?)```/gi;
            formattedThink = formattedThink.replace(jsonBlockRegex, (match, jsonContentStr) => {
                const trimmedJson = jsonContentStr.trim();
                try {
                    const parsedJson = JSON.parse(trimmedJson);
                    const escapedJsonString = JSON.stringify(parsedJson, null, 2)
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    return `<pre><code class="language-json">${escapedJsonString}</code></pre>`;
                } catch (jsonErr) {
                    const escapedOriginalJson = trimmedJson
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    return `<pre><code class="language-json error">${escapedOriginalJson}<br>(JSON Parse Error)</code></pre>`;
                }
            });
            thinkDiv.innerHTML = `<strong>${thinkBubbleLabel}:</strong><div class="think-bubble">${formattedThink}</div>`;
            logItemDiv.appendChild(thinkDiv);
        }
        dom.processLogContent.appendChild(logItemDiv);
        scrollToProcessLogBottom();
    }

    function scrollToProcessLogBottom(instant = false) {
        if (!dom.processLogContent) return;
        const container = dom.processLogContainer; // processLogContainer is the scrollable element
        const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth';
        container.scrollTo({ top: container.scrollHeight, behavior: behavior });
    }

    function showProcessLog(ensureExpanded = false) {
        if (!dom.processLogContainer) return;
        state.isProcessLogVisible = true;
        dom.processLogContainer.style.display = 'flex'; // It's a flex container

        if (state.animationLevel !== 'none' && !dom.processLogContainer.classList.contains('animate__fadeInDown')) {
            dom.processLogContainer.classList.remove('animate__fadeOutUp');
            dom.processLogContainer.classList.add('animate__animated', 'animate__fadeInDown');
            dom.processLogContainer.style.setProperty('--animate-duration', '0.4s');
        }
        if (ensureExpanded && state.isProcessLogCollapsed) {
            toggleProcessLogCollapse(false); // false means don't use instant animation for uncollapsing
        }
         localStorage.setItem(APP_PREFIX + 'isProcessLogVisible', state.isProcessLogVisible.toString());
    }

    function hideProcessLog() {
        if (!dom.processLogContainer) return;
        state.isProcessLogVisible = false;
        if (state.animationLevel !== 'none') {
            dom.processLogContainer.classList.remove('animate__fadeInDown');
            dom.processLogContainer.classList.add('animate__animated', 'animate__fadeOutUp');
            dom.processLogContainer.addEventListener('animationend', () => {
                if (!state.isProcessLogVisible) { // Check again in case state changed during animation
                    dom.processLogContainer.style.display = 'none';
                }
                // Always remove animation classes after it ends
                dom.processLogContainer.classList.remove('animate__animated', 'animate__fadeOutUp');
            }, { once: true });
        } else {
            dom.processLogContainer.style.display = 'none';
        }
        localStorage.setItem(APP_PREFIX + 'isProcessLogVisible', state.isProcessLogVisible.toString());
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
            // CSS handles transition for max-height and padding
            dom.processLogContainer.style.transition = 'max-height var(--transition-duration-long) var(--transition-timing-function-smooth), padding var(--transition-duration-long) var(--transition-timing-function-smooth)';
        } else {
            dom.processLogContainer.style.transition = 'none'; // Apply instantly
        }
    }

    function updateProcessLogCollapseState(collapse, instant = false) {
        state.isProcessLogCollapsed = collapse;
        dom.processLogContainer.classList.toggle('collapsed', state.isProcessLogCollapsed);
        const iconElement = dom.toggleProcessLogCollapseButton.querySelector('i');
        if (iconElement) {
            iconElement.className = state.isProcessLogCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
        }
        if (instant || state.animationLevel === 'none') {
             // Temporarily disable transition for instant update
            if (dom.processLogContainer.style.transition !== 'none') dom.processLogContainer.style.transition = 'none';
        }
        // If not instant, rely on existing CSS transitions (or default if none was set explicitly)
    }


    function initializeApp() {
        // VERSION UPDATE: Log message reflects V8.3.2
        console.log("IDT Agent Pro V8.3.2 CamelCase Reasoning Initializing...");
        updateLoaderProgress(10);
        loadSettings();
        updateLoaderProgress(25);
        applyCurrentTheme();
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
        applyAnimationLevel(state.animationLevel);
        updateLoaderProgress(40);
        loadSessions();
        updateLoaderProgress(55);
        setupEventListeners();
        updateLoaderProgress(70);
        adjustTextareaHeight();
        updateCharCounter();
        updateLoaderProgress(85);
        updateSidebarState(state.isSidebarExpanded, true); // true for instant
        updateSessionManagerState(state.isSessionManagerCollapsed, true); // true for instant
        updateProcessLogCollapseState(state.isProcessLogCollapsed, true); // true for instant


        if (localStorage.getItem(APP_PREFIX + 'isProcessLogVisible') === 'true') {
            showProcessLog(true); // true to ensure expanded if visible
        } else {
            hideProcessLog();
        }
        connectWebSocket(); // Starts WebSocket connection
        updateLoaderProgress(95); // Almost done before WS fully connects
        setTimeout(() => {
            if (dom.loaderProgress) dom.loaderProgress.style.width = '100%';
        }, 200); // Simulate final bit of loading
        // VERSION UPDATE
        console.log("IDT Agent Pro V8.3.2 CamelCase Reasoning initialization sequence complete, awaiting WebSocket confirmation.");
    }

    function updateLoaderProgress(percentage) {
        if (dom.loaderProgress) {
            dom.loaderProgress.style.width = `${percentage}%`;
        }
        const loadingTextEl = dom.loader.querySelector('.loading-text');
        // VERSION UPDATE: Loader text reflects V8.3.2 and CamelCase Reasoning where appropriate
        if (loadingTextEl) {
            if (percentage < 30) loadingTextEl.textContent = "Calibrating camelCase reasoning circuits...";
            else if (percentage < 60) loadingTextEl.textContent = "Loading cognitive models (V8.3.2)...";
            else if (percentage < 90) loadingTextEl.textContent = "Polishing interface clarity...";
            else loadingTextEl.textContent = "Establishing ethereal link (V8.3.2)...";
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
            applyTheme(nextTheme);
            showToast(`Theme set to: ${getThemeDisplayName(state.currentTheme)}`, 'info');
        });

        dom.clearChatButton.addEventListener('click', handleClearCurrentChat);
        dom.manageSessionsToggle.addEventListener('click', () => updateSidebarState(!state.isSidebarExpanded));
        dom.toggleProcessLogVisibilityButton.addEventListener('click', () => {
            if (state.isProcessLogVisible) {
                hideProcessLog();
            } else {
                showProcessLog(true); // true to ensure expanded if toggled on
            }
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

        if (dom.openSettingsButton) dom.openSettingsButton.addEventListener('click', openSettingsModal);
        if (dom.closeSettingsButton) dom.closeSettingsButton.addEventListener('click', () => closeSettingsModal(true)); // true to revert changes
        if (dom.saveSettingsButton) dom.saveSettingsButton.addEventListener('click', () => {
            collectAndSaveSettings();
            closeSettingsModal(false); // false to not revert (changes were saved)
            showToast('Personalization parameters calibrated and saved!', 'success');
        });
        if (dom.resetSettingsButton) dom.resetSettingsButton.addEventListener('click', resetToDefaultSettings);

        if (dom.fontSizeInput) dom.fontSizeInput.addEventListener('input', () => {
            const newSize = dom.fontSizeInput.value;
            if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${newSize}px`;
            document.body.style.fontSize = `${newSize}px`; // Apply live preview
        });
        if (dom.animationLevelSelect) dom.animationLevelSelect.addEventListener('change', (e) => {
            applyAnimationLevel(e.target.value); // Apply live preview
        });
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.addEventListener('change', (e) => {
            state.showChatBubblesThink = e.target.checked; // Live update state
        });
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.addEventListener('change', (e) => {
            state.showLogBubblesThink = e.target.checked; // Live update state
        });
         if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.addEventListener('change', (e) => {
            state.autoSubmitQuickActions = e.target.checked; // Live update state
        });


        if (dom.settingsModal) dom.settingsModal.addEventListener('click', (e) => {
            if (e.target === dom.settingsModal) closeSettingsModal(true); // Close and revert if clicking outside content
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
        return `session_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 11)}`;
    }

    function generateClientRequestId() {
        return `creq_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 9)}`;
    }

    function initializeCurrentSessionUI(isInitialLoadOrConnect = false) {
        const lastSessionId = localStorage.getItem(APP_PREFIX + 'lastSessionId');
        let targetSessionId = state.currentSessionId;

        if (!targetSessionId) {
            if (lastSessionId && state.sessions[lastSessionId]) {
                targetSessionId = lastSessionId;
            } else if (Object.keys(state.sessions).length > 0) {
                const sortedSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
                targetSessionId = sortedSessions[0].id;
            }
        }
        
        if (!targetSessionId || !state.sessions[targetSessionId]) {
            targetSessionId = createNewSession(true);
        }
        
        switchSession(targetSessionId, isInitialLoadOrConnect);
    }


    function createNewSession(isInitialCreation = false) {
        const newId = generateSessionId();
        const now = Date.now();
        const sessionCount = Object.keys(state.sessions).length + 1;
        state.sessions[newId] = {
            id: newId,
            name: `Nebula Session ${sessionCount}`, // Default name
            messages: [],
            createdAt: now,
            lastActivity: now,
        };
        saveSessions();

        if (!isInitialCreation) {
            switchSession(newId, false);
            showToast('New ethereal link established for session!', 'success');
            if (!state.isSidebarExpanded) updateSidebarState(true);
            if (state.isSessionManagerCollapsed) updateSessionManagerState(false);
        }
        return newId;
    }

    function switchSession(sessionId, isInitialLoadOrConnect = false) {
        if (!state.sessions[sessionId]) {
            console.error(`Attempt to switch to non-existent session: ${sessionId}. Creating a new one.`);
            const fallbackId = createNewSession(true);
            state.currentSessionId = fallbackId;
            if (!isInitialLoadOrConnect) {
                 // Assuming backend expects snake_case 'session_id'
                sendWebSocketMessage({ type: 'init', session_id: fallbackId });
            }
            dom.chatBox.innerHTML = '';
            appendWelcomeMessage();
            dom.currentSessionNameDisplay.textContent = state.sessions[fallbackId]?.name || "New Session";
            renderSessionList();
            return;
        }

        if (!isInitialLoadOrConnect && state.currentSessionId !== sessionId) {
            state.currentSessionId = sessionId;
             // Assuming backend expects snake_case 'session_id'
            sendWebSocketMessage({ type: 'init', session_id: sessionId });
            dom.chatBox.innerHTML = '';
            appendMessage("Loading conversation echoes...", 'system-info', false, null, true, [], "System Loading");
            dom.currentSessionNameDisplay.textContent = state.sessions[sessionId]?.name || "Loading...";
            renderSessionList();
            return; 
        }
        
        state.currentSessionId = sessionId;
        if (state.sessions[sessionId]) {
            state.sessions[sessionId].lastActivity = Date.now();
        }
        localStorage.setItem(APP_PREFIX + 'lastSessionId', sessionId);
        saveSessions();

        dom.currentSessionNameDisplay.textContent = state.sessions[sessionId]?.name || "Session";
        dom.chatBox.innerHTML = '';

        if (state.sessions[sessionId]?.messages.length === 0) {
            appendWelcomeMessage();
        } else {
            state.sessions[sessionId]?.messages.forEach(msg => {
                // When loading messages, use the stored 'thinking' and 'rawResponse' (which might be V8.3.2 camelCase)
                appendMessage(msg.content, msg.sender, msg.isHTML, msg.thinking, true, msg.attachments, msg.errorType);
            });
        }
        scrollToBottom(true);
        renderSessionList();
        dom.userInput.focus();

        dom.processLogContent.innerHTML = '';
        if (!state.isProcessLogVisible) hideProcessLog();

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
                switchSession(remainingSessions[0].id, false);
            } else {
                createNewSession(false);
            }
        } else {
            saveSessions();
            renderSessionList();
        }
        showToast(`Session "${sessionName}" has been archived.`, 'info');
        if (Object.keys(state.sessions).length === 0 && dom.sessionList) renderSessionList();
    }

    function handleEditSessionName() {
        const currentSession = state.sessions[state.currentSessionId];
        if (!currentSession) return;

        const newName = prompt("Enter new name for this session:", currentSession.name);
        if (newName && newName.trim() !== "" && newName.trim() !== currentSession.name) {
            currentSession.name = newName.trim().substring(0, 50);
            currentSession.lastActivity = Date.now();
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            saveSessions();
            renderSessionList();
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
            emptyItem.innerHTML = '<i class="fas fa-ghost"></i> No past echoes found';
            dom.sessionList.appendChild(emptyItem);
            return;
        }

        sortedSessions.forEach(session => {
            const listItem = document.createElement('li');
            listItem.classList.add('session-list-item');
            if (state.animationLevel === 'full' && !listItem.classList.contains('active-session')) {
                listItem.classList.add('animate__animated', 'animate__fadeInRight');
                listItem.style.setProperty('--animate-duration', '0.35s');
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
                if (state.currentSessionId !== session.id) switchSession(session.id, false);
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
                                // When loading, check for both old and new raw response keys
                                rawResponseV8_1: m.rawResponseV8_1, // Old key for compatibility if loading old data
                                rawResponseV8_3_2_CamelCase: m.rawResponseV8_3_2_CamelCase, // New key
                                errorType: m.errorType,
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
                localStorage.removeItem(APP_PREFIX + 'sessions');
            }
        } else {
            state.sessions = {};
        }
    }

    function updateSidebarState(expand, instant = false) {
        state.isSidebarExpanded = expand;
        dom.sidebar.classList.toggle('expanded', state.isSidebarExpanded);
        dom.manageSessionsToggle.setAttribute('aria-expanded', state.isSidebarExpanded.toString());
        dom.manageSessionsToggle.querySelector('i').className = state.isSidebarExpanded ? 'fas fa-chevron-left' : 'fas fa-bars';

        const duration = state.animationLevel === 'none' || instant ? 'none' : 'var(--transition-duration-long) var(--transition-timing-function-smooth)';
        dom.sidebar.style.transition = `width ${duration}, background-color ${duration}`;
        
        localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());

        if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
            updateSessionManagerState(true, instant);
        }
    }

    function updateSessionManagerState(collapse, instant = false) {
        state.isSessionManagerCollapsed = collapse;
        dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
        dom.sessionManagerToggle.setAttribute('aria-expanded', (!state.isSessionManagerCollapsed).toString());
        
        const duration = state.animationLevel === 'none' || instant ? 'none' : 'var(--transition-duration-long) var(--transition-timing-function-smooth)';
        dom.sessionListContainer.style.transition = `max-height ${duration}, padding ${duration}`;
        
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
            connectWebSocket();
            return;
        }

        setLoadingState(true);
        state.currentClientRequestId = generateClientRequestId();
        state.lastResponseThinking = null;

        const currentUserMessage = {
            content: messageText,
            sender: 'user',
            timestamp: Date.now(),
            isHTML: false,
            attachments: filesToSend.map(f => ({ name: f.name, size: f.size, type: f.type }))
        };
        addMessageToCurrentSession(currentUserMessage);
        appendMessage(messageText, 'user', false, null, false, currentUserMessage.attachments);

        const currentSession = state.sessions[state.currentSessionId];
        if (currentSession && currentSession.name.startsWith("Nebula Session ") && currentSession.messages.filter(m => m.sender === 'user').length === 1) {
            const autoName = messageText.substring(0, 30).trim() || "New Chat";
            currentSession.name = autoName + (messageText.length > 30 ? "..." : "");
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            renderSessionList();
        }

        dom.userInput.value = '';
        adjustTextareaHeight();
        updateCharCounter();
        closeFilePreview();

        dom.processLogContent.innerHTML = '';
        showProcessLog(true);

        let backendMessageContent = messageText;
        if (filesToSend.length > 0) {
            backendMessageContent += `\n[User conceptually attached files: ${filesToSend.map(f => f.name).join(', ')}. Please process the text query based on these filenames.]`;
        }

        // Assuming backend expects snake_case keys for 'message' type
        sendWebSocketMessage({
            type: 'message',
            session_id: state.currentSessionId,
            request_id: state.currentClientRequestId,
            content: backendMessageContent,
            mode: state.currentMode
        });
    }

    function addMessageToCurrentSession(messageObject) {
        if (state.sessions[state.currentSessionId]) {
            if (messageObject.sender !== 'agent') {
                // For user messages, remove agent-specific raw response keys
                delete messageObject.rawResponseV8_1;
                delete messageObject.rawResponseV8_3_2_CamelCase; // New key
                delete messageObject.thinking;
            }
            if (!messageObject.errorType) {
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
    
    function appendMessage(content, sender, isHTML = false, thinkContent = null, isSwitchingSession = false, attachments = [], errorType = null) {
        const messageDiv = document.createElement('div');
        const messageSenderClass = `message-${sender}`;
        messageDiv.classList.add('message', messageSenderClass);

        if (errorType) {
            const errorClassSuffix = errorType.toLowerCase().replace(/\s+/g, '-');
            messageDiv.classList.add(`message-error-type-${errorClassSuffix}`);
        }
        if (sender === 'system-info' || sender === 'error-system') {
            messageDiv.classList.add('system-message');
            if (sender === 'error-system') messageDiv.classList.add('error-message');
        }

        if (!isSwitchingSession && state.animationLevel !== 'none') {
            const animationClass = state.animationLevel === 'full' ? 'animate__fadeInUp' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
            if (animationClass) {
                messageDiv.classList.add('animate__animated', animationClass);
                messageDiv.style.setProperty('--animate-duration', state.animationLevel === 'full' ? '0.45s' : '0.3s');
            }
        }

        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('message-avatar');
        let avatarIcon = 'fas fa-info-circle';
        if (sender === 'user') avatarIcon = 'fas fa-user-astronaut';
        else if (sender === 'agent') avatarIcon = 'fas fa-robot';
        else if (sender === 'error-system') avatarIcon = 'fas fa-shield-virus';

        avatarDiv.innerHTML = `<i class="${avatarIcon}"></i>`;

        if (sender !== 'user' && sender !== 'system-message') {
            messageDiv.appendChild(avatarDiv);
        }

        const messageBubbleDiv = document.createElement('div');
        messageBubbleDiv.classList.add('message-bubble');

        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.classList.add('message-content-wrapper');
        
        if (sender === 'agent' && thinkContent && state.showChatBubblesThink) {
            const thinkPrefixDiv = document.createElement('div');
            thinkPrefixDiv.classList.add('message-thought-prefix');
            let formattedThink = String(thinkContent).replace(/\n/g, '<br>');
            const jsonBlockRegex = /```json([\s\S]*?)```/gi;
            formattedThink = formattedThink.replace(jsonBlockRegex, (match, jsonContentStr) => {
                const trimmedJson = jsonContentStr.trim();
                try {
                    const parsedJson = JSON.parse(trimmedJson);
                    const escapedJsonString = JSON.stringify(parsedJson, null, 2)
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    return `<pre class="embedded-json"><code>${escapedJsonString}</code></pre>`;
                } catch (e) {
                    console.warn("Chat bubble: JSON parsing for pretty print failed within thought:", e);
                    const escapedOriginalJson = trimmedJson
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    return `<pre class="embedded-json error"><code>${escapedOriginalJson}<br>(Invalid JSON structure)</code></pre>`;
                }
            });
            thinkPrefixDiv.innerHTML = `<strong>Agent's Reasoning:</strong><div class="think-bubble-content">${formattedThink}</div>`;
            messageContentWrapper.appendChild(thinkPrefixDiv);
        }

        const textContentDiv = document.createElement('div');
        textContentDiv.classList.add('message-text-content');

        if (isHTML) {
            textContentDiv.innerHTML = content;
        } else {
            const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
            const linkedContent = String(content)
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
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

        if (sender === 'user') {
            messageDiv.appendChild(avatarDiv);
        }

        dom.chatBox.appendChild(messageDiv);
        attachQuickActionButtonListeners(messageDiv);

        if (!isSwitchingSession) {
            scrollToBottom();
        }
    }

    function appendWelcomeMessage() {
        const lastMessage = dom.chatBox.lastElementChild;
        if (lastMessage && lastMessage.classList.contains('message-system-initial')) {
            return;
        }
        if (lastMessage && lastMessage.classList.contains('message-system-info') && lastMessage.textContent.includes("Loading conversation echoes...")) {
            lastMessage.remove();
        }

        // VERSION UPDATE: Welcome message reflects V8.3.2
        const welcomeHTML = `
            <div class="message-content">
                <div class="welcome-header">
                    <i class="fas fa-atom robot-icon animate__animated animate__pulse animate__infinite" style="--animate-duration: 2.5s;"></i>
                    <h2>IDT 智能助手 <span class="version-pro">Pro <span class="version-number">v8.3.2</span></span></h2>
                </div>
                <p class="welcome-subtitle">Your advanced assistant for circuit design and programming, now with enhanced CamelCase Reasoning. Ready to materialize your ideas.</p>
                <div class="capabilities">
                    <div class="capability"><i class="fas fa-bolt-lightning"></i><span>Rapid Analysis</span></div>
                    <div class="capability"><i class="fas fa-lightbulb"></i><span>Insightful Solutions</span></div>
                    <div class="capability"><i class="fas fa-tools"></i><span>Tool Integration</span></div>
                    <div class="capability"><i class="fas fa-infinity"></i><span>Iterative Refinement</span></div>
                </div>
                 <div class="quick-actions">
                    <p>Whisper your commands, or try these:</p>
                    <ul>
                        <li><a href="#" class="quick-action-btn" data-message="Add a 1k ohm resistor named R1">Add Resistor R1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Integrate a blue LED, call it LED_BLUE">Add Blue LED</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Connect R1 to LED_BLUE's anode, then LED_BLUE's cathode to ground (GND1)">Link R1-LED-GND</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Describe the current circuit schematic.">Describe Circuit</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Clear all components and connections.">Clear Circuit</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Explain series vs parallel circuits.">Series & Parallel?</a></li>
                    </ul>
                 </div>
            </div>
        `;
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'message system-message system-message-initial animate__animated animate__fadeInUp';
        welcomeDiv.style.setProperty('--animate-duration', '0.6s');
        welcomeDiv.innerHTML = welcomeHTML;
        dom.chatBox.appendChild(welcomeDiv);
        attachQuickActionButtonListeners(welcomeDiv);
    }


    function scrollToBottom(instant = false) {
        if (state.autoScroll) {
            const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth';
            dom.chatBox.scrollTo({ top: dom.chatBox.scrollHeight, behavior: behavior });
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
            typingDiv.style.setProperty('--animate-duration', '0.35s');
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
        textContent.innerHTML = `IDT Agent Pro is processing<span class="typing-dots">${dotsHTML}</span>`;
        
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
                typingElement.style.setProperty('--animate-duration', '0.3s');
                typingElement.addEventListener('animationend', () => typingElement.remove(), { once: true });
            } else {
                typingElement.remove();
            }
        }
    }

    function adjustTextareaHeight() {
        dom.userInput.style.height = 'auto';
        let scrollHeight = dom.userInput.scrollHeight;
        const maxHeight = parseInt(getComputedStyle(dom.userInput).maxHeight, 10) || 200;
        const minHeight = parseInt(getComputedStyle(dom.userInput).minHeight, 10) || 48;

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

        dom.processLogContent.innerHTML = '';
        if (!state.isProcessLogVisible) hideProcessLog();


        showToast('Current conversation cleared!', 'info');
        renderSessionList();
    }

    function handleModeChange(newMode) {
        if (state.currentMode === newMode) return;
        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === newMode));
        state.currentMode = newMode;
        localStorage.setItem(APP_PREFIX + 'currentMode', state.currentMode);
        console.log(`Mode switched to: ${newMode}`);
        showToast(`Switched to ${getModeDisplayName(newMode)} mode`, 'info');
        const sessionName = state.sessions[state.currentSessionId]?.name || 'current session';
        dom.userInput.placeholder = `Message in ${getModeDisplayName(newMode)} mode (${sessionName})...`;
    }

    function getModeDisplayName(mode) {
        const names = { chat: 'Conversation', code: 'Programming', circuit: 'Circuit Design', settings: 'Settings' };
        return names[mode] || 'Unknown';
    }

    function handleFileSelection(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        const MAX_FILES = 5, MAX_SIZE_MB = 2;

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
        const codeExtensions = ['.js', '.ts', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bat', '.v', '.sv', '.vhd', '.md', '.txt'];
        if (codeExtensions.some(ext => fileName.toLowerCase().endsWith(ext)) || fileType.includes('text')) return 'fa-file-code';
        if (fileName.endsWith('.doc') || fileName.endsWith('.docx')) return 'fa-file-word';
        if (fileName.endsWith('.xls') || fileName.endsWith('.xlsx')) return 'fa-file-excel';
        if (fileName.endsWith('.ppt') || fileName.endsWith('.pptx')) return 'fa-file-powerpoint';
        return 'fa-file-alt';
    }

    function removeFileFromPreview(fileName, fileSize) {
        state.uploadedFiles = state.uploadedFiles.filter(f => !(f.name === fileName && f.size === fileSize));
        const fileItemElement = dom.filePreviewContent.querySelector(`.file-item[data-file-name="${CSS.escape(fileName)}"][data-file-size="${fileSize}"]`);
        if (fileItemElement) {
            if (state.animationLevel !== 'none') {
                fileItemElement.classList.remove('animate__bounceIn');
                fileItemElement.classList.add('animate__animated', 'animate__bounceOut');
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
        state.uploadedFiles = [];
        dom.filePreviewContent.innerHTML = '';
    }

    function applyCurrentTheme() {
        applyTheme(state.currentTheme, true);
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
            if (themeIcon && themeName !== 'auto') themeIcon.className = 'fas fa-sun';
        } else {
            document.body.classList.add('light-theme');
            if (themeIcon && themeName !== 'auto') themeIcon.className = 'fas fa-moon';
        }
        state.currentTheme = themeName;
        if (dom.themeSelect) dom.themeSelect.value = themeName;
        if (!initialLoad) saveSettings();
        console.log(`Theme applied: ${themeName} (Effective: ${effectiveTheme})`);
    }

    function getThemeDisplayName(theme) { return { 'light': 'Light Mode', 'dark': 'Dark Mode', 'auto': 'System Default' }[theme] || 'Unknown'; }

    function applyFontSize(size) {
        const newSize = parseInt(size, 10);
        if (isNaN(newSize) || newSize < 12 || newSize > 20) {
            document.body.style.fontSize = '16px';
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
        modalContent.classList.remove('animate__fadeOutDown', 'animate__zoomOut', 'animate__fadeOut');
        const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInUp' : 'animate__fadeIn') : '';
        if (animIn) {
            modalContent.classList.add('animate__animated', animIn);
            modalContent.style.setProperty('--animate-duration', '0.4s');
        }
    }

    function closeSettingsModal(revertChanges = true) {
        if (revertChanges) {
            applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
            applyAnimationLevel(localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full');
            state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || 'true') === 'true';
            state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || 'false') === 'true';
            state.showChatBubblesThink = (localStorage.getItem(APP_PREFIX + 'showChatBubblesThink') || 'true') === 'true';
            state.showLogBubblesThink = (localStorage.getItem(APP_PREFIX + 'showLogBubblesThink') || 'true') === 'true';
            state.autoSubmitQuickActions = (localStorage.getItem(APP_PREFIX + 'autoSubmitQuickActions') || 'true') === 'true';

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
            if (animOut) modalContent.classList.remove('animate__animated', animOut);
        };

        if (state.animationLevel !== 'none' && animOut) {
            modalContent.classList.add('animate__animated', animOut);
            modalContent.style.setProperty('--animate-duration', '0.3s');
            modalContent.addEventListener('animationend', animationEndHandler, { once: true });
        } else {
            animationEndHandler();
        }
    }


    function collectAndSaveSettings() {
        applyTheme(dom.themeSelect.value);
        applyFontSize(dom.fontSizeInput.value);
        applyAnimationLevel(dom.animationLevelSelect.value);
        
        state.autoScroll = dom.autoScrollToggle.checked;
        state.soundEnabled = dom.soundEnabledToggle.checked;
        state.showChatBubblesThink = dom.showChatBubblesThinkToggle.checked;
        state.showLogBubblesThink = dom.showLogBubblesThinkToggle.checked;
        state.autoSubmitQuickActions = dom.autoSubmitQuickActionsToggle.checked;

        saveSettings();
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
        localStorage.setItem(APP_PREFIX + 'processLogVisible', state.isProcessLogVisible.toString());
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

        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;

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
        applyTheme(defaults.theme);
        applyFontSize(defaults.fontSize);
        applyAnimationLevel(defaults.animationLevel);
        state.autoScroll = defaults.autoScroll;
        state.soundEnabled = defaults.soundEnabled;
        state.showChatBubblesThink = defaults.showChatBubblesThink;
        state.showLogBubblesThink = defaults.showLogBubblesThink;
        state.autoSubmitQuickActions = defaults.autoSubmitQuickActions;
        state.currentMode = defaults.currentMode;

        updateSidebarState(defaults.sidebarExpanded, true);
        updateSessionManagerState(defaults.sessionManagerCollapsed, true);
        state.isProcessLogVisible = defaults.isProcessLogVisible;
        if (state.isProcessLogVisible) showProcessLog(true); else hideProcessLog();
        updateProcessLogCollapseState(defaults.processLogCollapsed, true);

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

        saveSettings();
        showToast('All parameters reset to factory settings!', 'success');
    }

    function showToast(message, type = 'info', duration = 3500) {
        const toast = document.createElement('div');
        toast.classList.add('toast', type, 'glass-effect');
        const animIn = state.animationLevel !== 'none' ? 'animate__fadeInRight' : '';
        const animOut = state.animationLevel !== 'none' ? 'animate__fadeOutRight' : '';

        if (state.animationLevel !== 'none' && animIn) {
            toast.classList.add('animate__animated', animIn);
            toast.style.setProperty('--animate-duration', '0.45s');
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
        if (toast.parentElement) {
            if (state.animationLevel !== 'none' && animOut && toast.classList.contains('animate__animated')) {
                toast.classList.remove(toast.classList.contains('animate__fadeInRight') ? 'animate__fadeInRight' : 'animate__fadeIn');
                toast.classList.add(animOut);
                toast.addEventListener('animationend', () => toast.remove(), { once: true });
            } else {
                toast.remove();
            }
        }
    }

    function attachQuickActionButtonListeners(container) {
        container.querySelectorAll('.quick-action-btn').forEach(button => {
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
            if (state.autoSubmitQuickActions) {
                handleSendMessage();
            }
        }
    }

    initializeApp();
    attachQuickActionButtonListeners(dom.chatBox); 

    [dom.appHeader, dom.sidebar, dom.inputArea, dom.processLogContainer, dom.settingsModal.querySelector('.modal-content'), dom.filePreviewArea]
    .forEach(el => {
        if (el) el.classList.add('glass-effect');
    });
});