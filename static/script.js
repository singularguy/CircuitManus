// 当整个 HTML 文档加载完成并解析完毕后执行回调函数
document.addEventListener('DOMContentLoaded', () => {
    // ======== DOM 元素获取 (集中管理，方便维护) ========
    const dom = {
        // 动态背景相关 (如果需要JS交互的话，目前纯CSS)
        dynamicBackground: document.querySelector('.dynamic-background'),

        // 加载动画相关
        loader: document.getElementById('loader'),
        loaderCore: document.querySelector('.loader-core'), // For enhanced loader animation
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
        themeToggleIcon: document.querySelector('#theme-toggle i'), // Kept for direct icon manipulation if needed
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
        openSettingsButton: document.querySelector('.sidebar-button[data-mode="settings"]'), // Still relevant
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
        componentVisibilityToggle: document.getElementById('component-visibility-toggle'), // Settings for 3D component
        resetSettingsButton: document.getElementById('reset-settings'),
        saveSettingsButton: document.getElementById('save-settings'),

        // 3D组件显示开关与包装器
        idtComponentToggleBtn: document.getElementById('toggleIdtComponentBtn'),
        idtComponentWrapper: document.getElementById('idtTechComponentWrapper')
    };

    // ======== 应用状态与配置 ========
    const APP_PREFIX = 'CircuitManusPro_SciFiEnhanced_'; // Updated prefix
    let state = {
        sessions: {},
        currentSessionId: null,
        currentTheme: 'auto', // Default to auto, will be loaded
        autoScroll: true,
        soundEnabled: false,
        showChatBubblesThink: true,
        showLogBubblesThink: true,
        animationLevel: 'full',
        currentMode: 'chat',
        uploadedFiles: [],
        isAgentTyping: false,
        isLoading: false,
        isSidebarExpanded: window.innerWidth > 768, // Initial state based on window width
        isSessionManagerCollapsed: false,
        isProcessLogVisible: false,
        isProcessLogCollapsed: true,
        maxInputChars: 8000, // Default from HTML
        currentClientRequestId: null,
        lastResponseThinking: null,
        autoSubmitQuickActions: true,
        isIdtComponentVisible: true, // Default from HTML class 'is-visible'

        // 3D Component Dragging State
        isDraggingComponent: false,
        componentDragStartX: 0,
        componentDragStartY: 0,
        componentInitialTopPx: 0, // Store initial pixel values for smoother drag
        componentInitialLeftPx: 0,
    };

    // ======== WebSocket 相关 ========
    let websocket = null;
    const websocketUrl = `ws://${window.location.host}/ws/chat`;
    let wsReconnectAttempts = 0;
    const MAX_WS_RECONNECT_ATTEMPTS = 5;
    const WS_RECONNECT_INTERVAL = 3000; // milliseconds

    function connectWebSocket() {
        if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
            console.log("WebSocket is already connected or connecting.");
            return;
        }
        console.log(`Attempting to connect WebSocket (Attempt ${wsReconnectAttempts + 1}): ${websocketUrl}`);
        if (dom.loader && wsReconnectAttempts === 0) {
            const loadingText = dom.loader.querySelector('.loading-text');
            if (loadingText) loadingText.textContent = "INITIATING HYPERLOOP CONNECTION (V1.0.0 Sci-Fi)...";
        }

        websocket = new WebSocket(websocketUrl);

        websocket.onopen = (event) => {
            console.log("WebSocket connection established", event);
            wsReconnectAttempts = 0;
            showToast("Quantum Entanglement Link ACTIVE (V1.0.0 Sci-Fi).", "success", 4000);
            sendWebSocketMessage({
                type: 'init',
                session_id: state.currentSessionId
            });
            // Hide loader after successful connection and init message sent
            if (dom.loader) dom.loader.classList.add('hidden');
            if (dom.mainContainer) dom.mainContainer.classList.add('loaded');
        };

        websocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                console.log("WS RX:", message);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error("Failed to parse WebSocket message:", e, "Raw data:", event.data);
                showToast("Received corrupted data stream from server.", "error");
            }
        };

        websocket.onerror = (event) => {
            console.error("WebSocket error:", event);
            // Potentially show a more persistent error if it's a connection-refused type error
            // showToast("Critical error in communication link.", "error", 7000);
        };

        websocket.onclose = (event) => {
            console.log("WebSocket connection closed:", event);
            hideTypingIndicator();
            setLoadingState(false);
            websocket = null; // Important to allow reconnection

            const reason = event.reason ? `Reason: ${event.reason}` : (event.wasClean ? 'Connection closed cleanly.' : 'Connection anomaly detected.');
            const codeMsg = `(Code: ${event.code})`;

            if (!event.wasClean && wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                wsReconnectAttempts++;
                showToast(`Subspace link unstable. Re-calibrating (${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})... ${codeMsg}`, "warning", WS_RECONNECT_INTERVAL + 500);
                setTimeout(connectWebSocket, WS_RECONNECT_INTERVAL);
            } else if (!event.wasClean) {
                showToast(`Communication link SEVERED after ${MAX_WS_RECONNECT_ATTEMPTS} attempts. Manual system refresh required. ${codeMsg} ${reason}`, "error", 0); // 0 for persistent
                if (dom.loader) {
                    const loadingText = dom.loader.querySelector('.loading-text');
                    if (loadingText) loadingText.textContent = "CONNECTION CORE FAILURE. REFRESH REQUIRED.";
                    // Optional: Animate loader to an error state
                    if (dom.loaderCore) dom.loaderCore.classList.add('error-state');
                    dom.loader.classList.remove('hidden'); // Show loader again
                }
            } else {
                showToast(`Communication link terminated. ${codeMsg} ${reason}`, "info", 6000);
            }
        };
    }

    function sendWebSocketMessage(message) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            const messageStr = JSON.stringify(message);
            console.log("WS TX:", message);
            websocket.send(messageStr);
        } else {
            console.error("WebSocket connection not open. Cannot send message:", message);
            showToast("Communication link inactive. Attempting to re-establish link...", "warning");
            if (!websocket || websocket.readyState === WebSocket.CLOSED || websocket.readyState === WebSocket.CLOSING) {
                if (wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                    connectWebSocket(); // Try to reconnect if fully closed and retries available
                } else {
                    showToast("Cannot send: Max reconnection attempts reached. Please refresh.", "error");
                }
            }
        }
    }

    function handleWebSocketMessage(message) {
        // Assuming backend sends snake_case, client-side uses camelCase for state and DOM logic.
        // Conversion logic for specific complex nested objects (like final_response content) happens in dedicated handlers.
        switch (message.type) {
            case 'init_success':
                state.currentSessionId = message.session_id; // Backend confirms/sends session_id
                localStorage.setItem(APP_PREFIX + 'lastSessionId', state.currentSessionId);

                const agentStatusMessage = message.agent_available === false
                    ? 'AI Core Module OFFLINE. Functionality severely limited. (V1.0.0 Sci-Fi)'
                    : 'Hyperion Core (V1.0.0 Sci-Fi) online and synchronized!';
                const agentStatusType = message.agent_available === false ? 'warning' : 'success';
                showToast(agentStatusMessage, agentStatusType, message.agent_available ? 4500 : 8000);

                if (!state.sessions[state.currentSessionId]) {
                    const now = Date.now();
                    state.sessions[state.currentSessionId] = {
                        id: state.currentSessionId,
                        name: `Quantum Entanglement ${Object.keys(state.sessions).length + 1}`, // Sci-fi session name
                        messages: [],
                        createdAt: now,
                        lastActivity: now,
                    };
                    saveSessions();
                }
                initializeCurrentSessionUI(true); // true for initial load/connect
                // Loader hidden in onopen now for faster perceived load
                break;

            case 'init_error':
                showToast(`AI Core synchronization failed: ${message.message}`, 'error', 10000);
                if (dom.loader) dom.loader.classList.add('hidden'); // Still hide loader on error
                if (dom.mainContainer) dom.mainContainer.classList.add('loaded');
                if (message.agent_available === false) {
                    appendMessage("CRITICAL SYSTEM ALERT: Hyperion AI core failed to initialize. Subsystems non-responsive. (V1.0.0 Sci-Fi)", 'error-system', false, null, false, [], "System Error");
                }
                setLoadingState(false);
                break;

            case 'error': // General server-side errors
                console.error("Server-reported error:", message);
                showToast(`Server Uplink Anomaly: ${message.message}`, 'error', 7000);
                if (message.details) {
                    appendMessage(`SERVER ERROR (${message.message}): ${message.details}`, 'error-system', false, null, false, [], "Server Error");
                }
                setLoadingState(false);
                break;

            // Assuming backend sends snake_case keys for these status messages
            case 'general_status': handleGeneralStatus(message); break;
            case 'llm_communication_status': handleLlmCommStatus(message); break;
            case 'thinking_log': handleThinkingLog(message); break;
            case 'plan_details': handlePlanDetails(message); break;
            case 'tool_status_update': handleToolStatusUpdate(message); break;
            case 'interim_response': handleInterimResponse(message); break;
            case 'final_response': handleFinalResponse(message); break;

            default:
                console.warn("Received unknown data packet from server:", message.type, message);
                showToast(`Unknown data packet type: ${message.type}`, 'warning');
        }
    }

    function handleGeneralStatus(msg) {
        const { stage, status, message: msgText, details } = msg;
        let logIconClass = 'fas fa-info-circle log-info';
        let logItemClasses = `type-general_status stage-${stage} status-${status}`;

        if (status === 'started' || status === 'llm_retry_needed' || status === 'llm_error_retrying') logIconClass = 'fas fa-sync-alt fa-spin log-info';
        else if (status === 'completed' || status === 'received' || status === 'completed_and_validated') logIconClass = 'fas fa-check-circle log-success';
        else if (status === 'error' || status === 'failed' || status === 'failed_after_llm_retries' || status === 'tool_failure_detected') {
            logIconClass = 'fas fa-exclamation-triangle log-error'; // Changed icon
        }
        else if (status === 'ignored') logIconClass = 'fas fa-eye-slash log-muted';

        appendLogItem(msgText, logIconClass, logItemClasses, details);
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handleLlmCommStatus(msg) {
        const { llm_phase, status, message: msgText, details } = msg;
        let logIconClass = 'fas fa-brain log-info'; // Retained brain icon
        let logItemClasses = `type-llm_communication_status phase-${llm_phase} status-${status}`;

        if (status === 'started') logIconClass = 'fas fa-brain fa-beat-fade log-info'; // Using fa-beat-fade for active thinking
        else if (status === 'completed') logIconClass = 'fas fa-check log-success';
        else if (status === 'error') logIconClass = 'fas fa-bolt log-error'; // Changed to bolt for error

        appendLogItem(msgText, logIconClass, logItemClasses, details);
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handleThinkingLog(msg) {
        const { stage, content, llm_interaction_id } = msg;
        if (content) {
            state.lastResponseThinking = content; // Cache for potential use in final message bubble
        }

        if (state.showLogBubblesThink) {
            const thinkLabel = `AI COGNITIVE TRACE (${stage.replace(/_/g, ' ').toUpperCase()})`;
            appendLogItemWithThink(thinkLabel, 'fas fa-comment-dots log-think', `type-thinking_log stage-${stage} llm-id-${llm_interaction_id}`, content, "Detailed Thought Process:");
        } else {
            appendLogItem(`Cognitive log received (${stage}, LLM_ID: ${llm_interaction_id}) - ${content.substring(0, 80)}...`, 'fas fa-comment-dots log-muted', `type-thinking_log stage-${stage} muted`);
        }
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handlePlanDetails(msg) {
        const { plan } = msg; // plan is an array of objects with camelCase keys
        state.pendingToolCalls = {};
        plan.forEach(toolCall => {
            const { toolCallId, toolName, toolArguments, uiHints = {}, order } = toolCall;
            state.pendingToolCalls[toolCallId] = {
                name: toolName,
                args_summary: summarizeArguments(toolArguments),
                ui_hints: uiHints,
                order: order
            };
            const displayName = uiHints.displayNameForTool || toolName.replace(/_tool$/, "").replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
            appendLogItem(
                `STRATEGIC NODE #${order}: ${displayName} (ID: ${toolCallId}) - Status: QUEUED`,
                'fas fa-list-check log-info', // Using fa-list-check for plan items
                `type-plan_details tool-${toolName} status-pending`,
                { arguments: toolArguments, tool_call_id: toolCallId } // Log details might use camelCase if from LLM
            );
        });
        if (state.isProcessLogVisible) showProcessLog(true);
    }

    function handleToolStatusUpdate(msg) {
        // Backend sends snake_case top-level keys.
        const { tool_call_id, tool_name, status, message: msgText, details } = msg;
        let logIconClass = 'fas fa-cog log-info';
        let itemStatusClass = `status-${status}`;

        if (status === 'running') logIconClass = 'fas fa-cogs fa-spin log-info'; // Changed to cogs for multiple
        else if (status === 'retrying') logIconClass = 'fas fa-history fa-spin log-info'; // Added spin
        else if (status === 'succeeded') logIconClass = 'fas fa-check-double log-success'; // Changed to double-check
        else if (status === 'failed') logIconClass = 'fas fa-bomb log-error'; // Changed to bomb for failure
        else if (status === 'aborted_due_to_previous_failure') {
            logIconClass = 'fas fa-ban log-warning';
            itemStatusClass = 'status-aborted';
        }

        const pendingToolInfo = state.pendingToolCalls[tool_call_id];
        const displayName = pendingToolInfo?.ui_hints?.displayNameForTool || tool_name.replace(/_tool$/, "").replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
        let fullLogMessage = `TOOL: ${displayName} (ID: ${tool_call_id}) - ${status.replace(/_/g, ' ').toUpperCase()}: ${msgText}`;

        let existingLogItem = dom.processLogContent.querySelector(`.log-item[data-tool-call-id="${tool_call_id}"]`);

        if (existingLogItem) {
            existingLogItem.className = `log-item animate__animated type-tool_status_update tool-${tool_name} ${itemStatusClass}`;
            const iconEl = existingLogItem.querySelector('i:first-child');
            if (iconEl) iconEl.className = logIconClass;
            const messageEl = existingLogItem.querySelector('.log-item-message');
            if (messageEl) messageEl.textContent = fullLogMessage;

            let detailsEl = existingLogItem.querySelector('.log-item-details');
            if (details && Object.keys(details).length > 0) {
                if (!detailsEl) {
                    detailsEl = document.createElement('div');
                    detailsEl.className = 'log-item-details';
                    existingLogItem.querySelector('.log-item-text-wrapper').appendChild(detailsEl);
                }
                const formattedDetailsHtml = formatLogDetails(details, 'tool_status_update', null, status);
                detailsEl.innerHTML = formattedDetailsHtml || '';
            } else if (detailsEl) {
                detailsEl.innerHTML = '';
            }
            existingLogItem.classList.remove('animate__flash', 'animate__headShake', 'animate__pulse');
            if (status === 'failed') existingLogItem.classList.add('animate__headShake');
            else if (status === 'succeeded') existingLogItem.classList.add('animate__pulse'); // Pulse on success
            else existingLogItem.classList.add('animate__flash');
            existingLogItem.style.setProperty('--animate-duration', '0.6s');

        } else {
            const logItemDiv = appendLogItem(fullLogMessage, logIconClass, `type-tool_status_update tool-${tool_name} ${itemStatusClass}`, details);
            if (logItemDiv) logItemDiv.dataset.toolCallId = tool_call_id;
        }

        if (state.isProcessLogVisible) showProcessLog(false);

        if (status === 'succeeded' || status === 'failed' || status === 'aborted_due_to_previous_failure') {
            if (state.pendingToolCalls[tool_call_id]) {
                delete state.pendingToolCalls[tool_call_id];
            }
        }
    }

    function handleInterimResponse(msg) {
        const { content, llm_interaction_id } = msg; // snake_case from backend
        appendLogItem(
            `AI INTENT: "${content.substring(0, 180)}${content.length > 180 ? '...' : ''}"`,
            'fas fa-bullhorn log-info', // Bullhorn for intent
            'type-agent_intention',
            { llm_interaction_id: llm_interaction_id, full_content: content }
        );
        if (state.isProcessLogVisible) showProcessLog(false);
    }

    function handleFinalResponse(msg) {
        hideTypingIndicator();
        setLoadingState(false);
        state.currentClientRequestId = null;
        state.pendingToolCalls = {};

        const { content, llm_interaction_id } = msg; // snake_case from backend ws handler
        const finalCamelCaseJson = msg.final_v8_3_2_camelcase_json_if_success; // camelCase JSON object

        let thinkingForBubble = null;
        let actualContentForBubble = content; // Fallback

        if (finalCamelCaseJson && finalCamelCaseJson.status === 'success') {
            if (finalCamelCaseJson.thoughtProcess) { // camelCase key from parsed LLM output
                thinkingForBubble = finalCamelCaseJson.thoughtProcess;
            }
            if (finalCamelCaseJson.decision &&
                finalCamelCaseJson.decision.responseToUser &&
                finalCamelCaseJson.decision.responseToUser.content) { // camelCase keys
                actualContentForBubble = finalCamelCaseJson.decision.responseToUser.content;

                const suggestions = finalCamelCaseJson.decision.responseToUser.suggestionsForNextSteps; // camelCase
                if (suggestions && Array.isArray(suggestions) && suggestions.length > 0) {
                    let suggestionsText = "\n\n<div class=\"final-response-suggestions\"><strong>NEXT TRANSMISSION OPTIONS:</strong><ul>"; // Sci-fi label
                    suggestions.forEach(sugg => { // sugg object keys are camelCase
                        if (sugg.textForUser) {
                            suggestionsText += `<li><a href="#" class="quick-action-btn" data-message="${sugg.textForUser.replace(/"/g, '&quot;')}"><i class="fas fa-angle-right"></i> ${sugg.textForUser}</a></li>`; // Added icon
                        }
                    });
                    suggestionsText += "</ul></div>";
                    actualContentForBubble += suggestionsText;
                    appendMessage(actualContentForBubble, 'agent', true, thinkingForBubble, false, [], null);
                } else {
                    appendMessage(actualContentForBubble, 'agent', false, thinkingForBubble, false, [], null);
                }
            } else {
                appendMessage(actualContentForBubble, 'agent', false, thinkingForBubble, false, [], "ContentMissingIn_V8_3_2_JSON");
            }
        } else {
            thinkingForBubble = state.lastResponseThinking; // Use cached thinking if any
            appendMessage(actualContentForBubble, 'agent', false, thinkingForBubble, false, [], "ErrorResponseOrNo_V8_3_2_JSON");
        }

        addMessageToCurrentSession({
            content: actualContentForBubble,
            sender: 'agent',
            timestamp: Date.now(),
            isHTML: (finalCamelCaseJson?.decision?.responseToUser?.suggestionsForNextSteps?.length > 0),
            rawResponseV8_3_2_CamelCase: finalCamelCaseJson, // Store the camelCase JSON
            thinking: thinkingForBubble,
        });
        state.lastResponseThinking = null;

        if (state.sessions[state.currentSessionId]) {
            state.sessions[state.currentSessionId].lastActivity = Date.now();
        }
        saveSessions();
        renderSessionList();

        const llmIdForLog = finalCamelCaseJson?.llmInteractionId || llm_interaction_id || 'N/A';
        appendLogItem(`AI FINAL TRANSMISSION DELIVERED (LLM_ID: ${llmIdForLog})`, 'fas fa-flag-checkered log-success', 'type-final_response', finalCamelCaseJson ? { summary: actualContentForBubble.substring(0, 120) + "...", raw_response: finalCamelCaseJson } : { error_details: "Response generation indicated failure or missing V1.0.0 JSON." });
        if (state.isProcessLogVisible) showProcessLog(true);
    }

    function setLoadingState(isLoading) {
        state.isLoading = isLoading;
        dom.sendButton.disabled = isLoading;
        dom.userInput.disabled = isLoading;
        dom.sendIcon.style.display = isLoading ? 'none' : 'inline-block';
        dom.sendLoadingIcon.style.display = isLoading ? 'inline-block' : 'none';
        dom.sendButton.title = isLoading ? "TRANSMITTING..." : "TRANSMIT COMMAND";
        // Enhanced visual feedback for loading
        if (isLoading) {
            dom.inputArea.classList.add('processing');
            dom.sendButton.classList.add('processing-active');
        } else {
            dom.inputArea.classList.remove('processing');
            dom.sendButton.classList.remove('processing-active');
        }
    }

    function summarizeArguments(argsObj) {
        if (!argsObj || typeof argsObj !== 'object' || Object.keys(argsObj).length === 0) {
            return "(No args)";
        }
        try {
            return JSON.stringify(argsObj, (key, value) => {
                if (typeof value === 'string' && value.length > 35) { // Slightly longer preview
                    return value.substring(0, 32) + "...";
                }
                return value;
            }).substring(0, 180); // Slightly longer overall summary
        } catch (e) {
            return "(Error summarizing args)";
        }
    }

    function parseItemClasses(itemClassesStr) {
        const classes = itemClassesStr ? itemClassesStr.split(' ') : [];
        const parsed = { type: null, stage: null, status: null };
        classes.forEach(cls => {
            if (cls.startsWith('type-')) parsed.type = cls.substring(5);
            else if (cls.startsWith('stage-')) parsed.stage = cls.substring(6);
            else if (cls.startsWith('status-')) parsed.status = cls.substring(7);
            else if (cls.startsWith('phase-')) parsed.stage = cls.substring(6);
        });
        return parsed;
    }

    function formatLogDetails(details, type, stage, status) {
        // Handles both snake_case and camelCase keys in the details object.
        let html = '';
        const addDetailKeyValue = (key, value, indentLevel = 0) => {
            const sanitizedValue = String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
            const paddingLeftStyle = `padding-left: ${indentLevel * 12}px;`; // Increased indent
            const formattedKey = key
                .replace(/([A-Z])/g, " $1").replace(/_/g, ' ').trim()
                .replace(/\b\w/g, char => char.toUpperCase());
            return `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${formattedKey}:</strong> <span class="log-detail-value">${sanitizedValue}</span></div>`;
        };

        const formatRecursive = (obj, currentType, currentStage, currentStatus, indentLevel = 0) => {
            let partHtml = '';
            for (const key in obj) {
                if (Object.prototype.hasOwnProperty.call(obj, key)) {
                    const value = obj[key];
                    const displayKey = key.replace(/([A-Z])/g, " $1").replace(/_/g, ' ').trim().replace(/\b\w/g, char => char.toUpperCase());
                    const paddingLeftStyle = `padding-left: ${indentLevel * 12}px;`;

                    if ((type === 'plan_details' && key === 'toolCallId') || (type === 'tool_status_update' && key === 'tool_call_id')) continue;

                    if (key === 'uiHints' && typeof value === 'object' && value !== null) {
                        const dn = String(value.displayNameForTool || 'N/A').replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        const ed = String(value.estimatedDurationCategory || 'N/A').replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">UI Hints:</strong> <span class="log-detail-value">Display: ${dn}, Duration: ${ed}</span></div>`;
                    } else if (key === 'result_data_preview' && typeof value === 'string') {
                        let previewContent = String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">Result Preview:</strong> <pre class="log-detail-preview-code"><code>${previewContent}</code></pre></div>`;
                    } else if ((type === 'plan_details' || type === 'tool_status_update') && (key === 'arguments' || key === 'toolArguments') && typeof value === 'object' && value !== null) {
                        let argItems = [];
                        for (const argKey in value) {
                            const formattedArgKey = argKey.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                            argItems.push(`<em class="log-arg-key">${formattedArgKey}</em>: ${String(value[argKey]).replace(/</g, "&lt;").replace(/>/g, "&gt;")}`);
                        }
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong> <span class="log-detail-value">${argItems.join('; ')}</span></div>`;
                    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                        partHtml += `<div class="log-detail-item log-detail-object-header" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong></div>`;
                        partHtml += formatRecursive(value, currentType, currentStage, currentStatus, indentLevel + 1);
                    } else if (Array.isArray(value)) {
                        const arrayItems = value.map(item => {
                            if (typeof item === 'object' && item !== null) return JSON.stringify(item).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                            return String(item).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        });
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong> <span class="log-detail-value log-detail-array">[${arrayItems.join(', ')}]</span></div>`;
                    } else {
                        partHtml += addDetailKeyValue(key, value, indentLevel);
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
        logItemDiv.style.setProperty('--animate-duration', '0.35s');
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
            } else {
                try {
                    let detailsText = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details);
                    detailsEl.innerHTML = `<pre class="log-detail-raw-json"><code>${detailsText.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>`;
                } catch (e) {
                    detailsEl.textContent = String(details);
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

    function appendLogItemWithThink(headerText, headerIconClass, itemClasses, thinkContent, thinkBubbleLabel = "Cognitive Matrix Output") { // Sci-fi label
        const logItemDiv = document.createElement('div');
        logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
        logItemDiv.style.setProperty('--animate-duration', '0.35s');
        if (itemClasses) logItemDiv.classList.add(...itemClasses.split(' '));

        const headerDiv = document.createElement('div');
        headerDiv.className = 'log-item-header-flex'; // For flex alignment

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
                    return `<pre><code class="language-json error">${escapedOriginalJson}<br>(JSON Data Stream Corruption Detected)</code></pre>`;
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
        const container = dom.processLogContainer;
        const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth';
        container.scrollTo({ top: container.scrollHeight, behavior: behavior });
    }

    function showProcessLog(ensureExpanded = false) {
        if (!dom.processLogContainer) return;
        state.isProcessLogVisible = true;
        dom.processLogContainer.style.display = 'flex';

        if (state.animationLevel !== 'none' && !dom.processLogContainer.classList.contains('animate__fadeInDown')) {
            dom.processLogContainer.classList.remove('animate__fadeOutUp');
            dom.processLogContainer.classList.add('animate__animated', 'animate__fadeInDown');
            dom.processLogContainer.style.setProperty('--animate-duration', '0.45s'); // Slightly longer for visibility
        }
        if (ensureExpanded && state.isProcessLogCollapsed) {
            toggleProcessLogCollapse(false);
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
                if (!state.isProcessLogVisible) {
                    dom.processLogContainer.style.display = 'none';
                }
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
            dom.processLogContainer.style.transition = 'max-height var(--transition-duration-long) var(--transition-timing-function-smooth), padding var(--transition-duration-long) var(--transition-timing-function-smooth)';
        } else {
            dom.processLogContainer.style.transition = 'none';
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
            if (dom.processLogContainer.style.transition !== 'none') dom.processLogContainer.style.transition = 'none';
        }
    }

    function initializeApp() {
        console.log("CircuitManus Pro - HYPERION CORE (V1.0.0 Sci-Fi Enhanced) Initializing...");
        // updateLoaderProgress(10); // Removed as loader is now more visual
        loadSettings();
        // updateLoaderProgress(25);
        applyCurrentTheme();
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
        applyAnimationLevel(state.animationLevel);
        // updateLoaderProgress(40);
        loadSessions();
        // updateLoaderProgress(55);
        setupEventListeners(); // This now includes 3D component listeners
        // updateLoaderProgress(70);
        adjustTextareaHeight();
        updateCharCounter();
        // updateLoaderProgress(85);
        updateSidebarState(state.isSidebarExpanded, true);
        updateSessionManagerState(state.isSessionManagerCollapsed, true);
        updateProcessLogCollapseState(state.isProcessLogCollapsed, true);

        if (state.isProcessLogVisible) {
            showProcessLog(true);
        } else {
            hideProcessLog();
        }

        // Initialize 3D component visibility based on settings
        dom.idtComponentWrapper.classList.toggle('is-visible', state.isIdtComponentVisible);
        dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? 'Deactivate AI Core Visualizer' : 'Activate AI Core Visualizer');
        // Optional: update icon based on state.isIdtComponentVisible
        // const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
        // if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-cubes';


        connectWebSocket(); // WebSocket connection will handle final loader hide
        // updateLoaderProgress(95); // No longer numeric progress

        initializeCurrentSessionUI(true);
        attachQuickActionButtonListeners(dom.chatBox);

        // Ensure glass effect is applied to specified elements if not already by CSS alone
        [dom.appHeader, dom.sidebar, dom.inputArea, dom.processLogContainer, dom.settingsModal.querySelector('.modal-content'), dom.filePreviewArea]
            .forEach(el => { if (el && !el.classList.contains('glass-effect')) el.classList.add('glass-effect'); });

        console.log("Hyperion Core Systems Nominal. Awaiting Quantum Entanglement Link.");
    }

    // function updateLoaderProgress(percentage) { // No longer used with new loader
    //     // ... (kept for reference, but not called)
    // }

    function setupEventListeners() {
        dom.sendButton.addEventListener('click', handleSendMessage);
        dom.userInput.addEventListener('keypress', handleUserInputKeypress);
        dom.userInput.addEventListener('input', () => {
            adjustTextareaHeight();
            updateCharCounter();
        });

        dom.themeToggleButton.addEventListener('click', () => {
            const themes = ['auto', 'light', 'dark']; // Ensure 'auto' is a valid option
            const currentIndex = themes.indexOf(state.currentTheme);
            const nextTheme = themes[(currentIndex + 1) % themes.length];
            applyTheme(nextTheme); // This will also save the setting
            showToast(`Visual Spectrum Shifted to: ${getThemeDisplayName(state.currentTheme)}`, 'info');
        });

        dom.clearChatButton.addEventListener('click', handleClearCurrentChat);
        dom.manageSessionsToggle.addEventListener('click', () => updateSidebarState(!state.isSidebarExpanded));
        dom.toggleProcessLogVisibilityButton.addEventListener('click', () => {
            if (state.isProcessLogVisible) hideProcessLog();
            else showProcessLog(true);
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
        dom.micButton.addEventListener('click', () => showToast('Voice Command Matrix: Calibration in Progress...', 'info'));

        // Settings Modal Listeners
        if (dom.closeSettingsButton) dom.closeSettingsButton.addEventListener('click', () => closeSettingsModal(true));
        if (dom.saveSettingsButton) dom.saveSettingsButton.addEventListener('click', () => {
            collectAndSaveSettings();
            closeSettingsModal(false);
            showToast('Personalization Matrix Synchronized and Stored!', 'success');
        });
        if (dom.resetSettingsButton) dom.resetSettingsButton.addEventListener('click', resetToDefaultSettings);
        if (dom.fontSizeInput) dom.fontSizeInput.addEventListener('input', () => {
            const newSize = dom.fontSizeInput.value;
            if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${newSize}px`;
            document.body.style.fontSize = `${newSize}px`;
        });
        if (dom.animationLevelSelect) dom.animationLevelSelect.addEventListener('change', (e) => applyAnimationLevel(e.target.value));
        if (dom.autoScrollToggle) dom.autoScrollToggle.addEventListener('change', (e) => { state.autoScroll = e.target.checked; });
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.addEventListener('change', (e) => { state.soundEnabled = e.target.checked; });
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.addEventListener('change', (e) => { state.showChatBubblesThink = e.target.checked; });
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.addEventListener('change', (e) => { state.showLogBubblesThink = e.target.checked; });
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.addEventListener('change', (e) => { state.autoSubmitQuickActions = e.target.checked; });
        if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.addEventListener('change', (e) => {
            state.isIdtComponentVisible = e.target.checked;
            dom.idtComponentWrapper.classList.toggle('is-visible', state.isIdtComponentVisible);
            dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? 'Deactivate AI Core Visualizer' : 'Activate AI Core Visualizer');
        });


        if (dom.settingsModal) dom.settingsModal.addEventListener('click', (e) => {
            if (e.target === dom.settingsModal) closeSettingsModal(true);
        });
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (state.currentTheme === 'auto') applyCurrentTheme();
        });
        if (dom.toggleProcessLogCollapseButton) dom.toggleProcessLogCollapseButton.addEventListener('click', () => toggleProcessLogCollapse());

        // 3D Component Toggle Button
        if (dom.idtComponentToggleBtn && dom.idtComponentWrapper) {
            dom.idtComponentToggleBtn.addEventListener('click', () => {
                state.isIdtComponentVisible = !dom.idtComponentWrapper.classList.contains('is-visible'); // State before toggle
                dom.idtComponentWrapper.classList.toggle('is-visible');
                state.isIdtComponentVisible = dom.idtComponentWrapper.classList.contains('is-visible'); // Update state after toggle

                dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? 'Deactivate AI Core Visualizer' : 'Activate AI Core Visualizer');
                // Update settings toggle if modal is open
                if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;
                localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', state.isIdtComponentVisible.toString());
            });
        } else {
            if (!dom.idtComponentToggleBtn) console.warn("IDT Component Control Button (toggleIdtComponentBtn) not found.");
            if (!dom.idtComponentWrapper) console.warn("IDT Component Wrapper (idtTechComponentWrapper) not found.");
        }

        // 3D Component Drag Listeners
        if (dom.idtComponentWrapper) {
            dom.idtComponentWrapper.addEventListener('mousedown', handleComponentMouseDown);
        } else {
            console.warn("IDT Component Wrapper (idtTechComponentWrapper) not found for drag setup.");
        }
    }

    // ======== 3D 组件拖动处理函数 ========
    function handleComponentMouseDown(e) {
        if (!dom.idtComponentWrapper.classList.contains('is-visible') || e.button !== 0) {
            return;
        }
        state.isDraggingComponent = true;
        dom.idtComponentWrapper.style.cursor = 'grabbing';
        document.body.style.userSelect = 'none';

        const styles = getComputedStyle(document.documentElement);
        const currentTopPercent = parseFloat(styles.getPropertyValue('--idt-offset-top-percentage')) || 0;
        const currentLeftPercent = parseFloat(styles.getPropertyValue('--idt-offset-left-percentage')) || 0;

        state.componentInitialTopPx = (currentTopPercent / 100) * window.innerHeight;
        state.componentInitialLeftPx = (currentLeftPercent / 100) * window.innerWidth;

        // If inline styles are set (from previous drag within session before saving to CSS var), use them.
        // This logic prioritizes current visual position if it differs from CSS var (e.g. mid-drag)
        if (dom.idtComponentWrapper.style.top && dom.idtComponentWrapper.style.left) {
            state.componentInitialTopPx = parseFloat(dom.idtComponentWrapper.style.top);
            state.componentInitialLeftPx = parseFloat(dom.idtComponentWrapper.style.left);
        }


        state.componentDragStartX = e.clientX;
        state.componentDragStartY = e.clientY;

        document.addEventListener('mousemove', handleComponentMouseMove);
        document.addEventListener('mouseup', handleComponentMouseUp);
        document.addEventListener('mouseleave', handleComponentMouseUp); // Handle mouse leaving window
        e.preventDefault();
    }

    function handleComponentMouseMove(e) {
        if (!state.isDraggingComponent) return;

        const deltaX = e.clientX - state.componentDragStartX;
        const deltaY = e.clientY - state.componentDragStartY;

        let newTopPx = state.componentInitialTopPx + deltaY;
        let newLeftPx = state.componentInitialLeftPx + deltaX;

        const componentRect = dom.idtComponentWrapper.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        newTopPx = Math.max(0, Math.min(newTopPx, viewportHeight - componentRect.height));
        newLeftPx = Math.max(0, Math.min(newLeftPx, viewportWidth - componentRect.width));

        dom.idtComponentWrapper.style.top = `${newTopPx}px`;
        dom.idtComponentWrapper.style.left = `${newLeftPx}px`;
    }

    function handleComponentMouseUp() {
        if (!state.isDraggingComponent) return;
        state.isDraggingComponent = false;
        dom.idtComponentWrapper.style.cursor = 'grab';
        document.body.style.userSelect = '';

        document.removeEventListener('mousemove', handleComponentMouseMove);
        document.removeEventListener('mouseup', handleComponentMouseUp);
        document.removeEventListener('mouseleave', handleComponentMouseUp);

        const finalTopPx = parseFloat(dom.idtComponentWrapper.style.top) || 0;
        const finalLeftPx = parseFloat(dom.idtComponentWrapper.style.left) || 0;
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        let newTopPercent = (finalTopPx / viewportHeight) * 100;
        let newLeftPercent = (finalLeftPx / viewportWidth) * 100;

        // Ensure component top-left corner percentage is within bounds that keep the component fully visible
        const componentWidthPercent = (dom.idtComponentWrapper.offsetWidth / viewportWidth) * 100;
        const componentHeightPercent = (dom.idtComponentWrapper.offsetHeight / viewportHeight) * 100;

        newTopPercent = Math.max(0, Math.min(newTopPercent, 100 - componentHeightPercent));
        newLeftPercent = Math.max(0, Math.min(newLeftPercent, 100 - componentWidthPercent));


        document.documentElement.style.setProperty('--idt-offset-top-percentage', `${newTopPercent.toFixed(2)}%`);
        document.documentElement.style.setProperty('--idt-offset-left-percentage', `${newLeftPercent.toFixed(2)}%`);

        // Clear inline styles to let CSS variables take over for consistency and responsiveness
        dom.idtComponentWrapper.style.top = '';
        dom.idtComponentWrapper.style.left = '';

        localStorage.setItem(APP_PREFIX + 'idtComponentTopPercent', `${newTopPercent.toFixed(2)}%`);
        localStorage.setItem(APP_PREFIX + 'idtComponentLeftPercent', `${newLeftPercent.toFixed(2)}%`);
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
        return `session_quantum_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 12)}`; // Sci-fi ID
    }

    function generateClientRequestId() {
        return `creq_hyperion_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 10)}`; // Sci-fi ID
    }

    function initializeCurrentSessionUI(isInitialLoadOrConnect = false) {
        const lastSessionId = localStorage.getItem(APP_PREFIX + 'lastSessionId');
        let targetSessionId = state.currentSessionId; // Might be set by init_success if WS connects very fast

        if (!targetSessionId) { // If WS hasn't set it yet, try to load from localStorage or find most recent
            if (lastSessionId && state.sessions[lastSessionId]) {
                targetSessionId = lastSessionId;
            } else if (Object.keys(state.sessions).length > 0) {
                const sortedSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
                targetSessionId = sortedSessions[0].id;
            }
        }

        if (!targetSessionId || !state.sessions[targetSessionId]) {
            targetSessionId = createNewSession(true); // true for initial creation, won't switch yet
        }

        // switchSession will handle the actual UI update and WS init if needed.
        // If isInitialLoadOrConnect is true, switchSession might delay WS init if session_id is already current.
        switchSession(targetSessionId, isInitialLoadOrConnect);
    }

    function createNewSession(isInitialCreation = false) {
        const newId = generateSessionId();
        const now = Date.now();
        const sessionCount = Object.keys(state.sessions).length + 1;
        state.sessions[newId] = {
            id: newId,
            name: `Nebula Stream ${sessionCount}`, // Sci-fi default name
            messages: [],
            createdAt: now,
            lastActivity: now,
        };
        saveSessions();

        if (!isInitialCreation) {
            switchSession(newId, false); // false means it's not the initial page load/connect
            showToast('New Quantum Entanglement Stream Established!', 'success');
            if (!state.isSidebarExpanded) updateSidebarState(true); // Expand sidebar to show new session
            if (state.isSessionManagerCollapsed) updateSessionManagerState(false); // Expand session list
        }
        return newId; // Return the new ID, useful for initial creation
    }

    function switchSession(sessionId, isInitialLoadOrConnect = false) {
        if (!state.sessions[sessionId]) {
            console.error(`Attempt to switch to non-existent session: ${sessionId}. Creating a fallback.`);
            // This should ideally not happen if createNewSession was called correctly for new sessions.
            const fallbackId = createNewSession(true); // Create a new session without immediately switching UI
            state.currentSessionId = fallbackId; // Set current ID
            // No WS init here, as it might be part of initial load or handled by connectWebSocket
        } else {
            state.currentSessionId = sessionId;
        }

        // Only send 'init' to WebSocket if it's a deliberate switch, not part of initial page load where `connectWebSocket` handles the first init.
        // Also, only if the new sessionId is different from what might have been set by an early `init_success`.
        if (!isInitialLoadOrConnect && websocket && websocket.readyState === WebSocket.OPEN) {
            sendWebSocketMessage({ type: 'init', session_id: state.currentSessionId });
        }

        localStorage.setItem(APP_PREFIX + 'lastSessionId', state.currentSessionId);
        if (state.sessions[state.currentSessionId]) { // Ensure session exists after potential fallback
            state.sessions[state.currentSessionId].lastActivity = Date.now();
        }
        saveSessions();

        dom.currentSessionNameDisplay.textContent = state.sessions[state.currentSessionId]?.name || "Initializing Stream...";
        dom.chatBox.innerHTML = ''; // Clear chatbox

        if (state.sessions[state.currentSessionId]?.messages.length === 0) {
            appendWelcomeMessage();
        } else {
            state.sessions[state.currentSessionId]?.messages.forEach(msg => {
                appendMessage(msg.content, msg.sender, msg.isHTML, msg.thinking, true, msg.attachments, msg.errorType);
            });
        }
        scrollToBottom(true); // Instant scroll
        renderSessionList();
        dom.userInput.focus();

        // Clear process log for the new session view
        dom.processLogContent.innerHTML = '';
        // If process log was visible, keep it visible but clear, otherwise keep it hidden
        if (!state.isProcessLogVisible) hideProcessLog(); else showProcessLog(false); // false to not force expand

        console.log(`Switched to session: ${state.sessions[state.currentSessionId]?.name} (ID: ${state.currentSessionId})`);
    }

    function deleteSession(sessionId, event) {
        if (event) event.stopPropagation();
        if (!state.sessions[sessionId]) return;

        const sessionName = state.sessions[sessionId].name;
        // Sci-fi confirm message
        if (!confirm(`ARCHIVE CHRONO-SIGNATURE "${sessionName}" (ID: ${sessionId})? This action is irreversible across timelines.`)) {
            return;
        }

        const listItem = dom.sessionList.querySelector(`li[data-session-id="${sessionId}"]`);
        if (listItem) {
            if (state.animationLevel !== 'none') {
                listItem.classList.add('animate__animated', 'animate__fadeOutLeftBig'); // Enhanced animation
                listItem.style.setProperty('--animate-duration', '0.5s');
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
                // Create a new session if all are deleted, and switch to it.
                const newFallbackId = createNewSession(true);
                switchSession(newFallbackId, false);
            }
        } else {
            saveSessions(); // Save after deleting, before re-rendering
            renderSessionList(); // Re-render if current session wasn't the one deleted
        }
        showToast(`Chrono-signature "${sessionName}" archived.`, 'info');
        if (Object.keys(state.sessions).length === 0 && dom.sessionList) renderSessionList(); // Ensure empty state is shown
    }

    function handleEditSessionName() {
        const currentSession = state.sessions[state.currentSessionId];
        if (!currentSession) return;

        const newName = prompt(`Re-calibrate Chrono-Anchor name for "${currentSession.name}":`, currentSession.name);
        if (newName && newName.trim() !== "" && newName.trim() !== currentSession.name) {
            currentSession.name = newName.trim().substring(0, 60); // Slightly longer name allowed
            currentSession.lastActivity = Date.now();
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            saveSessions();
            renderSessionList();
            showToast("Chrono-Anchor name recalibrated.", "success");
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
            emptyItem.innerHTML = '<i class="fas fa-ghost"></i> NO PAST ECHOES DETECTED'; // Sci-fi text
            dom.sessionList.appendChild(emptyItem);
            return;
        }

        sortedSessions.forEach(session => {
            const listItem = document.createElement('li');
            listItem.classList.add('session-list-item');
            // Animation applied on add, not re-render, to avoid constant flashing
            if (session.id === state.currentSessionId) {
                listItem.classList.add('active-session');
            }
            listItem.dataset.sessionId = session.id;

            const lastActivityDate = new Date(session.lastActivity);
            const createdDate = new Date(session.createdAt);
            const timeSinceLastActivity = formatTimeSince(session.lastActivity);

            listItem.title = `Last Signal: ${timeSinceLastActivity} (${lastActivityDate.toLocaleString()})\nEstablished: ${createdDate.toLocaleDateString()}`;

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
            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>'; // Standard trash icon is fine
            deleteBtn.title = "Archive this Chrono-Signature";
            deleteBtn.addEventListener('click', (e) => deleteSession(session.id, e));

            listItem.appendChild(contentWrapper);
            listItem.appendChild(deleteBtn);
            listItem.addEventListener('click', () => {
                if (state.currentSessionId !== session.id) switchSession(session.id, false);
            });

            dom.sessionList.appendChild(listItem);
            // Trigger animation if it's a newly added item (more complex logic needed for this, usually handled by how items are added)
            // For simplicity, this re-render won't re-animate existing items unless classes are re-added.
            if (state.animationLevel === 'full' && !listItem.classList.contains('animate__animated')) {
                // This might need adjustment if items are frequently re-rendered.
                // Typically, you'd animate on initial append or specific add operation.
                // listItem.classList.add('animate__animated', 'animate__fadeInRight');
                // listItem.style.setProperty('--animate-duration', '0.4s');
            }
        });
    }

    function formatTimeSince(dateTimestamp) {
        const now = new Date();
        const secondsPast = (now.getTime() - dateTimestamp) / 1000;

        if (secondsPast < 60) return 'Just Now';
        if (secondsPast < 3600) return `${Math.round(secondsPast / 60)}m ago`;
        if (secondsPast <= 86400) return `${Math.round(secondsPast / 3600)}h ago`;
        // For older items, show date, or relative days if preferred
        const daysPast = Math.round(secondsPast / 86400);
        if (daysPast < 7) return `${daysPast}d ago`;

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
            console.error("Error saving session data to localStorage (Quantum Datastore might be unstable):", e);
            showToast("Could not persist session data. Datastore anomaly detected.", "error");
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
                            name: s.name || "Lost Signal Stream", // Sci-fi fallback
                            messages: s.messages.map(m => ({
                                content: m.content || "",
                                sender: m.sender || "system",
                                timestamp: m.timestamp || Date.now(),
                                isHTML: m.isHTML || false,
                                attachments: m.attachments || [],
                                thinking: m.thinking || null,
                                rawResponseV8_3_2_CamelCase: m.rawResponseV8_3_2_CamelCase, // Ensure new key is loaded
                                errorType: m.errorType,
                            })),
                            createdAt: s.createdAt || Date.now(),
                            lastActivity: s.lastActivity || Date.now(),
                        };
                    } else {
                        console.warn("Found corrupted chrono-signature data, bypassing:", id, s);
                    }
                });
            } catch (e) {
                console.error("Failed to load or parse session data (Datastore corruption suspected):", e);
                state.sessions = {}; // Reset if corrupted
                localStorage.removeItem(APP_PREFIX + 'sessions'); // Clear corrupted data
            }
        } else {
            state.sessions = {}; // No sessions found
        }
    }

    function updateSidebarState(expand, instant = false) {
        state.isSidebarExpanded = expand;
        dom.sidebar.classList.toggle('expanded', state.isSidebarExpanded);
        dom.manageSessionsToggle.setAttribute('aria-expanded', state.isSidebarExpanded.toString());
        dom.manageSessionsToggle.querySelector('i').className = state.isSidebarExpanded ? 'fas fa-chevron-left' : 'fas fa-bars'; // Icons for expand/collapse

        const duration = state.animationLevel === 'none' || instant ? 'none' : 'width var(--transition-duration-long) var(--transition-timing-function-smooth), background-color var(--transition-duration-medium) var(--transition-timing-function-smooth)';
        dom.sidebar.style.transition = duration;

        localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());

        // If sidebar collapses, and session manager was expanded, collapse session manager too.
        if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
            updateSessionManagerState(true, instant);
        }
    }

    function updateSessionManagerState(collapse, instant = false) {
        state.isSessionManagerCollapsed = collapse;
        dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
        dom.sessionManagerToggle.setAttribute('aria-expanded', (!state.isSessionManagerCollapsed).toString());
        // Toggle icon for session manager expand/collapse (optional, if you want visual feedback here too)
        const sessionToggleIcon = dom.sessionManagerToggle.querySelector('.toggle-icon');
        if (sessionToggleIcon) sessionToggleIcon.className = state.isSessionManagerCollapsed ? 'fas fa-angle-double-down' : 'fas fa-angle-double-up';


        const duration = state.animationLevel === 'none' || instant ? 'none' : 'max-height var(--transition-duration-long) var(--transition-timing-function-smooth), padding var(--transition-duration-long) var(--transition-timing-function-smooth)';
        dom.sessionListContainer.style.transition = duration;

        localStorage.setItem(APP_PREFIX + 'sessionManagerCollapsed', state.isSessionManagerCollapsed.toString());
    }

    async function handleSendMessage() {
        if (state.isLoading) {
            showToast("AI Core is processing previous command sequence. Stand by...", "warning");
            return;
        }
        const messageText = dom.userInput.value.trim();
        const filesToSend = [...state.uploadedFiles];

        if (messageText === '' && filesToSend.length === 0) {
            showToast("Directive required. Input command or attach data crystal.", "warning");
            return;
        }
        if (dom.userInput.value.length > state.maxInputChars) {
            showToast(`COMMAND BUFFER OVERFLOW. Max ${state.maxInputChars} characters.`, "error");
            return;
        }

        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
            showToast("Quantum Link OFFLINE. Attempting re-synchronization...", "warning");
            connectWebSocket(); // Attempt to reconnect
            return;
        }

        setLoadingState(true);
        state.currentClientRequestId = generateClientRequestId();
        state.lastResponseThinking = null; // Clear previous thinking

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
        if (currentSession && currentSession.name.startsWith("Nebula Stream ") && currentSession.messages.filter(m => m.sender === 'user').length === 1) {
            // Auto-name session based on first user message
            const autoName = messageText.substring(0, 35).trim() || "New Transmission"; // Slightly longer auto-name
            currentSession.name = autoName + (messageText.length > 35 ? "..." : "");
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            renderSessionList(); // Update list with new name
        }

        dom.userInput.value = '';
        adjustTextareaHeight();
        updateCharCounter();
        closeFilePreview(); // Clear file previews after sending

        dom.processLogContent.innerHTML = ''; // Clear log for new request
        showProcessLog(true); // Show and expand log for new request

        let backendMessageContent = messageText;
        if (filesToSend.length > 0) {
            backendMessageContent += `\n[User attached data crystals: ${filesToSend.map(f => f.name).join(', ')}. Process text query based on these filenames.]`;
        }

        sendWebSocketMessage({
            type: 'message',
            session_id: state.currentSessionId,
            request_id: state.currentClientRequestId,
            content: backendMessageContent,
            mode: state.currentMode // Send current interaction mode
        });
    }

    function addMessageToCurrentSession(messageObject) {
        if (state.sessions[state.currentSessionId]) {
            if (messageObject.sender !== 'agent') {
                delete messageObject.rawResponseV8_3_2_CamelCase;
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
                messageDiv.style.setProperty('--animate-duration', state.animationLevel === 'full' ? '0.5s' : '0.35s'); // Slightly adjusted duration
            }
        }

        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('message-avatar');
        let avatarIcon = 'fas fa-question-circle'; // Default icon
        if (sender === 'user') avatarIcon = 'fas fa-user-astronaut';
        else if (sender === 'agent') avatarIcon = 'fas fa-robot'; // Or fa-brain, fa-microchip
        else if (sender === 'system-info') avatarIcon = 'fas fa-info-circle';
        else if (sender === 'error-system') avatarIcon = 'fas fa-shield-virus'; // Or fa-biohazard

        avatarDiv.innerHTML = `<i class="${avatarIcon}"></i>`;

        if (sender !== 'user') { // Avatar on left for agent/system
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
                    return `<pre class="embedded-json error"><code>${escapedOriginalJson}<br>(Invalid JSON Sub-Routine)</code></pre>`;
                }
            });
            // Sci-fi label for thought bubble
            thinkPrefixDiv.innerHTML = `<strong><i class="fas fa-brain"></i> AI COGNITIVE MATRIX:</strong><div class="think-bubble-content">${formattedThink}</div>`;
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
                .replace(urlRegex, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer" class="external-link"><i class="fas fa-external-link-alt"></i> ${url}</a>`); // Added icon to links
            textContentDiv.innerHTML = linkedContent;
        }
        messageContentWrapper.appendChild(textContentDiv);

        if (attachments && attachments.length > 0) {
            const attachmentsDiv = document.createElement('div');
            attachmentsDiv.classList.add('message-attachments-summary');
            attachmentsDiv.innerHTML = `<i class="fas fa-paperclip"></i> Data Crystals Attached (${attachments.length}): `;
            attachments.forEach(file => {
                const fileChip = document.createElement('span');
                fileChip.classList.add('filename-chip');
                fileChip.textContent = file.name;
                fileChip.title = `${file.name} (${(file.size / 1024).toFixed(1)} KB, Type: ${file.type || 'Unknown'})`;
                attachmentsDiv.appendChild(fileChip);
            });
            messageContentWrapper.appendChild(attachmentsDiv);
        }

        messageBubbleDiv.appendChild(messageContentWrapper);
        messageDiv.appendChild(messageBubbleDiv);

        if (sender === 'user') { // Avatar on right for user
            messageDiv.appendChild(avatarDiv);
        }

        dom.chatBox.appendChild(messageDiv);
        attachQuickActionButtonListeners(messageDiv); // Attach listeners for quick actions in this message

        if (!isSwitchingSession) {
            scrollToBottom();
        }
    }

    function appendWelcomeMessage() {
        const lastMessage = dom.chatBox.lastElementChild;
        if (lastMessage && lastMessage.classList.contains('message-system-initial')) {
            return; // Welcome message already exists
        }
        // Clear "Loading echoes..." if present
        if (lastMessage && lastMessage.classList.contains('message-system-info') && lastMessage.textContent.includes("Loading conversation echoes...")) {
            lastMessage.remove();
        }

        const welcomeHTML = `
            <div class="message-content">
                <div class="welcome-header">
                    <i class="fas fa-atom robot-icon animate__animated animate__pulse animate__infinite" style="--animate-duration: 2.8s;"></i>
                    <h2>CircuitManus <span class="version-pro">Hyperion <span class="version-number">v1.0.0</span></span></h2>
                </div>
                <p class="welcome-subtitle">Your Advanced Tactical AI for Circuit Schematics & Quantum Programming. Hyperion Core online. Transmit your directives.</p>
                <div class="capabilities">
                    <div class="capability"><i class="fas fa-bolt-lightning"></i><span>RAPID ANALYSIS</span></div>
                    <div class="capability"><i class="fas fa-tools"></i><span>TOOL INTEGRATION</span></div>
                    <div class="capability"><i class="fas fa-infinity"></i><span>ITERATIVE REFINEMENT</span></div>
                    <div class="capability"><i class="fas fa-brain"></i><span>INTELLIGENT THINKING</span></div>
                    <div class="capability"><i class="fas fa-microchip"></i><span>QUANTUM COMPUTING</span></div>
                    <div class="capability"><i class="fas fa-code"></i><span>CODE SYNTHESIS</span></div>
                    <div class="capability"><i class="fas fa-project-diagram"></i><span>CIRCUIT DESIGN</span></div>
                    <div class="capability"><i class="fas fa-cogs"></i><span>SYSTEM DESIGN</span></div>
                    <div class="capability"><i class="fas fa-user-astronaut"></i><span>USER FRIENDLY</span></div>
                    <div class="capability"><i class="fas fa-chart-line"></i><span>ANALYSIS</span></div>
                    <div class="capability"><i class="fas fa-code-branch"></i><span>VERSION CONTROL</span></div>
                </div>
                 <div class="quick-actions">
                    <p>Initiate Command Sequence or Select Pre-emptive Protocol:</p>
                    <ul>
                        <li><a href="#" class="quick-action-btn" data-message="Add a 1k ohm resistor named R1"><i class="fas fa-plus-circle"></i> Add Resistor R1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Integrate a blue LED, call it LED_BLUE"><i class="fas fa-plus-circle"></i> Add Blue LED</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Connect R1 to LED_BLUE's anode, then LED_BLUE's cathode to ground (GND1)"><i class="fas fa-link"></i> Link R1-LED-GND</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Describe the current circuit schematic."><i class="fas fa-eye"></i> Describe Circuit</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Clear all components and connections."><i class="fas fa-skull-crossbones"></i> Purge Circuit Matrix</a></li> 
                        <li><a href="#" class="quick-action-btn" data-message="Explain series vs parallel circuits."><i class="fas fa-question-circle"></i> Series & Parallel?</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Generate a schematic for a simple LED circuit with a 1k ohm resistor."><i class="fas fa-cogs"></i> Generate LED Circuit</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Create a new session."><i class="fas fa-plus"></i> New Quantum Stream</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Delete current session."><i class="fas fa-trash-alt"></i> Archive Chrono-Signature</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Switch to Code Synthesis Core mode."><i class="fas fa-code"></i> Code Synthesis</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="Switch to Circuit Design Nexus mode."><i class="fas fa-project-diagram"></i> Circuit Design</a></li>
                    </ul>
                 </div>
            </div>
        `;
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'message system-message system-message-initial animate__animated animate__fadeInUp';
        welcomeDiv.style.setProperty('--animate-duration', '0.65s');
        welcomeDiv.innerHTML = welcomeHTML;
        dom.chatBox.appendChild(welcomeDiv);
        attachQuickActionButtonListeners(welcomeDiv); // Attach listeners for quick actions in welcome message
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
        typingDiv.id = 'typing-indicator'; // Ensure ID is set for removal
        const animationClass = state.animationLevel !== 'none' ? 'animate__fadeInUp' : '';
        typingDiv.classList.add('message', 'message-agent', 'typing-indicator');
        if (animationClass) {
            typingDiv.classList.add('animate__animated', animationClass);
            typingDiv.style.setProperty('--animate-duration', '0.4s');
        }

        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('message-avatar');
        avatarDiv.innerHTML = '<i class="fas fa-robot fa-beat"></i>'; // fa-beat for active typing

        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('message-bubble');

        const contentWrapper = document.createElement('div');
        contentWrapper.classList.add('message-content-wrapper');

        const textContent = document.createElement('div');
        textContent.classList.add('message-text-content');

        let dotsHTML = Array(3).fill('<span class="typing-dot"></span>').join('');
        textContent.innerHTML = `Hyperion Core Processing<span class="typing-dots">${dotsHTML}</span>`; // Sci-fi text

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
                typingElement.classList.remove('animate__fadeInUp', 'animate__fadeIn'); // Remove specific in-animation
                typingElement.classList.add('animate__animated', animationOutClass);
                typingElement.style.setProperty('--animate-duration', '0.35s');
                typingElement.addEventListener('animationend', () => typingElement.remove(), { once: true });
            } else {
                typingElement.remove();
            }
        }
    }

    function adjustTextareaHeight() {
        dom.userInput.style.height = 'auto'; // Reset height to shrink if needed
        let scrollHeight = dom.userInput.scrollHeight;
        const maxHeight = parseInt(getComputedStyle(dom.userInput).maxHeight, 10) || 250; // From CSS
        const minHeight = parseInt(getComputedStyle(dom.userInput).minHeight, 10) || 56; // From CSS

        // Add a little padding for single line for better aesthetics, but only if it's truly single line content
        const singleLinePadding = 6; // Small padding
        if (dom.userInput.value.split('\n').length <= 1 && scrollHeight < minHeight + singleLinePadding * 2) { // Check against minHeight + padding
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

        // Sci-fi confirm message
        if (!confirm(`PURGE CURRENT DATA STREAM in session "${state.sessions[state.currentSessionId].name}"? This will erase all message logs and associated AI process data for this view.`)) {
            return;
        }

        state.sessions[state.currentSessionId].messages = [];
        state.sessions[state.currentSessionId].lastActivity = Date.now(); // Update activity
        saveSessions(); // Persist change

        dom.chatBox.innerHTML = ''; // Clear chat display
        appendWelcomeMessage(); // Show welcome message again

        dom.processLogContent.innerHTML = ''; // Clear process log display
        if (!state.isProcessLogVisible) hideProcessLog(); // Keep hidden if it was

        showToast('Current Data Stream Purged!', 'info');
        renderSessionList(); // Update session list (activity time changes)
    }

    function handleModeChange(newMode) {
        if (state.currentMode === newMode) return;
        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === newMode));
        state.currentMode = newMode;
        localStorage.setItem(APP_PREFIX + 'currentMode', state.currentMode);
        console.log(`Mode matrix reconfigured to: ${newMode}`);
        showToast(`Engaged ${getModeDisplayName(newMode)} Protocol`, 'info'); // Sci-fi toast
        const sessionName = state.sessions[state.currentSessionId]?.name || 'current stream';
        dom.userInput.placeholder = `Transmit to Hyperion via ${getModeDisplayName(newMode)} Protocol (${sessionName})...`; // Sci-fi placeholder
    }

    function getModeDisplayName(mode) {
        const names = { chat: 'Conversation Matrix', code: 'Code Synthesis Core', circuit: 'Circuit Design Nexus', settings: 'System Calibration' };
        return names[mode] || 'Unknown Protocol';
    }

    function handleFileSelection(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        const MAX_FILES = 5, MAX_SIZE_MB = 2; // These can be configurable

        files.forEach(file => {
            if (state.uploadedFiles.length >= MAX_FILES) {
                showToast(`Max ${MAX_FILES} data crystals allowed per transmission.`, 'warning'); return;
            }
            if (file.size > MAX_SIZE_MB * 1024 * 1024) {
                showToast(`Data crystal "${file.name}" exceeds ${MAX_SIZE_MB}MB integrity limit.`, 'warning'); return;
            }
            if (!state.uploadedFiles.find(f => f.name === file.name && f.size === file.size)) {
                state.uploadedFiles.push(file);
                addFileToPreview(file);
            } else {
                showToast(`Data crystal "${file.name}" already queued for upload.`, 'info');
            }
        });
        if (state.uploadedFiles.length > 0) dom.filePreviewArea.classList.add('active');
        dom.fileInput.value = ''; // Reset file input to allow re-selecting same file if removed
    }

    function addFileToPreview(file) {
        const fileItem = document.createElement('div');
        fileItem.classList.add('file-item');
        if (state.animationLevel !== 'none') fileItem.classList.add('animate__animated', 'animate__bounceIn'); // Or 'animate__fadeInRightBig'
        fileItem.style.setProperty('--animate-duration', '0.45s');
        fileItem.dataset.fileName = file.name; // Use dataset for easier removal
        fileItem.dataset.fileSize = file.size;

        const iconClass = getFileIconClass(file.type, file.name); // Helper to get appropriate icon
        fileItem.innerHTML = `
            <i class="fas ${iconClass} file-icon"></i>
            <span class="file-name" title="${file.name} (${(file.size / 1024).toFixed(1)}KB, Type: ${file.type || 'Unknown'})">${file.name}</span>
            <button class="file-remove icon-btn" title="Eject data crystal"><i class="fas fa-times-circle"></i></button>`;

        fileItem.querySelector('.file-remove').addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent triggering other listeners if any
            removeFileFromPreview(file.name, file.size);
        });
        dom.filePreviewContent.appendChild(fileItem);
    }

    function getFileIconClass(fileType, fileName) { // Returns Font Awesome class
        if (fileType.startsWith('image/')) return 'fa-file-image';
        if (fileType.startsWith('audio/')) return 'fa-file-audio';
        if (fileType.startsWith('video/')) return 'fa-file-video';
        if (fileType === 'application/pdf') return 'fa-file-pdf';
        if (fileType === 'application/zip' || fileName.endsWith('.zip') || fileName.endsWith('.rar') || fileName.endsWith('.7z')) return 'fa-file-archive';
        // More specific code/text types
        const ext = fileName.slice(fileName.lastIndexOf(".")).toLowerCase();
        const codeExtensions = ['.js', '.ts', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bat', '.v', '.sv', '.vhd', '.md', '.txt', '.log'];
        if (codeExtensions.includes(ext) || fileType.includes('text')) return 'fa-file-code'; // Generic code/text
        if (['.doc', '.docx'].includes(ext)) return 'fa-file-word';
        if (['.xls', '.xlsx', '.csv'].includes(ext)) return 'fa-file-excel';
        if (['.ppt', '.pptx'].includes(ext)) return 'fa-file-powerpoint';
        return 'fa-file-alt'; // Default file icon
    }

    function removeFileFromPreview(fileName, fileSize) {
        state.uploadedFiles = state.uploadedFiles.filter(f => !(f.name === fileName && f.size === fileSize));
        const fileItemElement = dom.filePreviewContent.querySelector(`.file-item[data-file-name="${CSS.escape(fileName)}"][data-file-size="${fileSize}"]`);
        if (fileItemElement) {
            if (state.animationLevel !== 'none') {
                fileItemElement.classList.remove('animate__bounceIn', 'animate__fadeInRightBig');
                fileItemElement.classList.add('animate__animated', 'animate__bounceOut'); // Or 'animate__fadeOutLeftBig'
                fileItemElement.addEventListener('animationend', () => {
                    fileItemElement.remove();
                    if (state.uploadedFiles.length === 0) closeFilePreview(); // Hide preview area if empty
                }, { once: true });
            } else {
                fileItemElement.remove();
                if (state.uploadedFiles.length === 0) closeFilePreview();
            }
        }
    }
    function closeFilePreview() {
        dom.filePreviewArea.classList.remove('active'); // Hide preview area
        // Optionally clear files array and preview content if not already done by removeFileFromPreview
        // state.uploadedFiles = [];
        // dom.filePreviewContent.innerHTML = '';
    }

    function applyCurrentTheme() {
        applyTheme(state.currentTheme, true); // true for initial load
    }

    function applyTheme(themeName, initialLoad = false) {
        let effectiveTheme = themeName;
        document.body.classList.remove('light-theme', 'dark-theme');
        const themeIcon = dom.themeToggleButton.querySelector('i'); // Icon inside button

        if (themeName === 'auto') {
            effectiveTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            if (themeIcon) themeIcon.className = 'fas fa-desktop'; // Or a more sci-fi "auto" icon like fa-cogs
        }

        if (effectiveTheme === 'dark') {
            document.body.classList.add('dark-theme');
            if (themeIcon && themeName !== 'auto') themeIcon.className = 'fas fa-sun'; // Sun for "switch to light"
        } else { // Light theme
            document.body.classList.add('light-theme');
            if (themeIcon && themeName !== 'auto') themeIcon.className = 'fas fa-moon'; // Moon for "switch to dark"
        }
        state.currentTheme = themeName; // Store the selected preference ('auto', 'light', or 'dark')
        if (dom.themeSelect) dom.themeSelect.value = themeName; // Update settings dropdown
        if (!initialLoad) saveSettings(); // Save settings if not initial load
        console.log(`Visual Spectrum set to: ${themeName} (Effective: ${effectiveTheme})`);
    }

    function getThemeDisplayName(theme) {
        return { 'light': 'Daybreak Matrix', 'dark': 'Void Nebula', 'auto': 'Adaptive Chronosphere' }[theme] || 'Unknown Spectrum';
    }

    function applyFontSize(size) {
        const newSize = parseInt(size, 10);
        if (isNaN(newSize) || newSize < 12 || newSize > 20) {
            // Fallback to default if invalid
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
        document.body.dataset.animationLevel = level; // Use data attribute for CSS targeting
        state.animationLevel = level;
        if (dom.animationLevelSelect && dom.animationLevelSelect.value !== level) {
            dom.animationLevelSelect.value = level;
        }
        console.log(`Dynamic Visuals Protocol set to: ${level}`);
    }

    function openSettingsModal() {
        // Populate modal with current settings
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
        if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;


        dom.settingsModal.style.display = 'flex'; // Show modal
        const modalContent = dom.settingsModal.querySelector('.modal-content');
        // Clear previous out-animations, then apply in-animation
        modalContent.classList.remove('animate__fadeOutDown', 'animate__zoomOut', 'animate__fadeOut');
        const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInUpBig' : 'animate__fadeIn') : ''; // Enhanced in-animation
        if (animIn) {
            modalContent.classList.add('animate__animated', animIn);
            modalContent.style.setProperty('--animate-duration', '0.5s'); // Slightly longer for effect
        }
    }

    function closeSettingsModal(revertChanges = true) {
        if (revertChanges) { // Revert to previously saved settings if "Save" wasn't clicked
            applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
            applyAnimationLevel(localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full');
            state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || 'true') === 'true';
            state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || 'false') === 'true';
            state.showChatBubblesThink = (localStorage.getItem(APP_PREFIX + 'showChatBubblesThink') || 'true') === 'true';
            state.showLogBubblesThink = (localStorage.getItem(APP_PREFIX + 'showLogBubblesThink') || 'true') === 'true';
            state.autoSubmitQuickActions = (localStorage.getItem(APP_PREFIX + 'autoSubmitQuickActions') || 'true') === 'true';
            state.isIdtComponentVisible = (localStorage.getItem(APP_PREFIX + 'isIdtComponentVisible') || 'true') === 'true';

            // Update UI elements to reflect reverted state
            if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
            if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
            if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
            if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
            if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;
            if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;
            dom.idtComponentWrapper.classList.toggle('is-visible', state.isIdtComponentVisible); // Reflect visibility
        }

        const modalContent = dom.settingsModal.querySelector('.modal-content');
        modalContent.classList.remove('animate__fadeInUpBig', 'animate__zoomIn', 'animate__fadeIn');
        const animOut = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeOutDownBig' : 'animate__fadeOut') : ''; // Enhanced out-animation

        const animationEndHandler = () => {
            dom.settingsModal.style.display = 'none';
            if (animOut) modalContent.classList.remove('animate__animated', animOut);
        };

        if (state.animationLevel !== 'none' && animOut) {
            modalContent.classList.add('animate__animated', animOut);
            modalContent.style.setProperty('--animate-duration', '0.4s');
            modalContent.addEventListener('animationend', animationEndHandler, { once: true });
        } else {
            animationEndHandler(); // No animation, hide immediately
        }
    }

    function collectAndSaveSettings() {
        // Theme is applied directly via applyTheme, which also saves.
        applyFontSize(dom.fontSizeInput.value); // This applies and sets up for saving
        applyAnimationLevel(dom.animationLevelSelect.value); // This applies and sets up for saving

        state.autoScroll = dom.autoScrollToggle.checked;
        state.soundEnabled = dom.soundEnabledToggle.checked;
        state.showChatBubblesThink = dom.showChatBubblesThinkToggle.checked;
        state.showLogBubblesThink = dom.showLogBubblesThinkToggle.checked;
        state.autoSubmitQuickActions = dom.autoSubmitQuickActionsToggle.checked;
        state.isIdtComponentVisible = dom.componentVisibilityToggle.checked; // Already applied live

        saveSettings(); // Central function to save all state to localStorage
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
        localStorage.setItem(APP_PREFIX + 'isProcessLogVisible', state.isProcessLogVisible.toString());
        localStorage.setItem(APP_PREFIX + 'processLogCollapsed', state.isProcessLogCollapsed.toString());
        localStorage.setItem(APP_PREFIX + 'autoSubmitQuickActions', state.autoSubmitQuickActions.toString());
        localStorage.setItem(APP_PREFIX + 'currentMode', state.currentMode);
        localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', state.isIdtComponentVisible.toString());
        // Save 3D component position
        localStorage.setItem(APP_PREFIX + 'idtComponentTopPercent', document.documentElement.style.getPropertyValue('--idt-offset-top-percentage'));
        localStorage.setItem(APP_PREFIX + 'idtComponentLeftPercent', document.documentElement.style.getPropertyValue('--idt-offset-left-percentage'));

        console.log("Personalization Matrix data saved to Quantum Datastore.");
    }

    function loadSettings() {
        // Load 3D component position first, as it sets CSS vars used by component HTML/CSS
        const savedTopPercent = localStorage.getItem(APP_PREFIX + 'idtComponentTopPercent');
        const savedLeftPercent = localStorage.getItem(APP_PREFIX + 'idtComponentLeftPercent');
        if (savedTopPercent !== null) document.documentElement.style.setProperty('--idt-offset-top-percentage', savedTopPercent);
        if (savedLeftPercent !== null) document.documentElement.style.setProperty('--idt-offset-left-percentage', savedLeftPercent);

        state.currentTheme = localStorage.getItem(APP_PREFIX + 'theme') || 'auto';
        // Font size loaded and applied in initializeApp via applyFontSize
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
        state.isIdtComponentVisible = (localStorage.getItem(APP_PREFIX + 'isIdtComponentVisible') || 'true') === 'true';

        // Update UI elements in settings modal if they exist
        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;
        if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;


        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === state.currentMode));
        const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || 'current stream';
        dom.userInput.placeholder = `Transmit to Hyperion via ${getModeDisplayName(state.currentMode)} Protocol (${sessionNameForPlaceholder})...`;
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
            isIdtComponentVisible: true,
            idtComponentTopPercent: '2.5%', // Default from CSS
            idtComponentLeftPercent: '1.8%', // Default from CSS
        };

        // Apply visual settings
        applyTheme(defaults.theme);
        applyFontSize(defaults.fontSize);
        applyAnimationLevel(defaults.animationLevel);

        // Apply state settings
        state.autoScroll = defaults.autoScroll;
        state.soundEnabled = defaults.soundEnabled;
        state.showChatBubblesThink = defaults.showChatBubblesThink;
        state.showLogBubblesThink = defaults.showLogBubblesThink;
        state.autoSubmitQuickActions = defaults.autoSubmitQuickActions;
        state.currentMode = defaults.currentMode;
        state.isIdtComponentVisible = defaults.isIdtComponentVisible;

        // Apply UI component states
        updateSidebarState(defaults.sidebarExpanded, true);
        updateSessionManagerState(defaults.sessionManagerCollapsed, true);
        state.isProcessLogVisible = defaults.isProcessLogVisible; // Set state first
        if (state.isProcessLogVisible) showProcessLog(true); else hideProcessLog();
        updateProcessLogCollapseState(defaults.processLogCollapsed, true);

        dom.idtComponentWrapper.classList.toggle('is-visible', state.isIdtComponentVisible);
        dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? 'Deactivate AI Core Visualizer' : 'Activate AI Core Visualizer');
        document.documentElement.style.setProperty('--idt-offset-top-percentage', defaults.idtComponentTopPercent);
        document.documentElement.style.setProperty('--idt-offset-left-percentage', defaults.idtComponentLeftPercent);


        // Update settings modal UI elements
        if (dom.themeSelect) dom.themeSelect.value = defaults.theme;
        if (dom.fontSizeInput) dom.fontSizeInput.value = defaults.fontSize;
        if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${defaults.fontSize}px`;
        if (dom.animationLevelSelect) dom.animationLevelSelect.value = defaults.animationLevel;
        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = defaults.autoScroll;
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = defaults.soundEnabled;
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = defaults.showChatBubblesThink;
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = defaults.showLogBubblesThink;
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = defaults.autoSubmitQuickActions;
        if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = defaults.isIdtComponentVisible;


        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === defaults.currentMode));
        const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || 'current stream';
        dom.userInput.placeholder = `Transmit to Hyperion via ${getModeDisplayName(defaults.currentMode)} Protocol (${sessionNameForPlaceholder})...`;

        saveSettings(); // Persist default settings
        showToast('System Parameters Reset to Factory Defaults!', 'success');
    }

    function showToast(message, type = 'info', duration = 4000) { // Slightly longer default duration
        const toast = document.createElement('div');
        toast.classList.add('toast', `toast-${type}`, 'glass-effect'); // Added toast- prefix for type class for specificity
        const animIn = state.animationLevel !== 'none' ? 'animate__fadeInRightBig' : ''; // Enhanced animation
        const animOut = state.animationLevel !== 'none' ? 'animate__fadeOutRightBig' : '';

        if (state.animationLevel !== 'none' && animIn) {
            toast.classList.add('animate__animated', animIn);
            toast.style.setProperty('--animate-duration', '0.5s');
        }

        const icons = { 'info': 'fa-info-circle', 'success': 'fa-check-circle', 'warning': 'fa-exclamation-triangle', 'error': 'fa-skull-crossbones' }; // Sci-fi error icon
        const iconClass = icons[type] || 'fa-info-circle';

        toast.innerHTML = `
            <i class="fas ${iconClass} toast-icon"></i>
            <span class="toast-message">${message.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</span>
            <button class="toast-close icon-btn"><i class="fas fa-times"></i></button>`;

        toast.querySelector('.toast-close').addEventListener('click', () => removeToast(toast, animOut));
        dom.toastContainer.appendChild(toast);

        if (duration > 0) { // Allow duration 0 for persistent toasts
            setTimeout(() => removeToast(toast, animOut), duration);
        }
    }

    function removeToast(toast, animOut) {
        if (toast.parentElement) { // Check if still in DOM
            if (state.animationLevel !== 'none' && animOut && toast.classList.contains('animate__animated')) {
                toast.classList.remove(toast.classList.contains('animate__fadeInRightBig') ? 'animate__fadeInRightBig' : 'animate__fadeIn');
                toast.classList.add(animOut);
                toast.addEventListener('animationend', () => toast.remove(), { once: true });
            } else {
                toast.remove();
            }
        }
    }

    function attachQuickActionButtonListeners(container) {
        container.querySelectorAll('.quick-action-btn').forEach(button => {
            // Remove old listener before adding, to prevent duplicates if called multiple times on same container
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

    // Call initialization
    initializeApp();

}); // End of DOMContentLoaded
