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
        themeToggleIcon: document.querySelector('#theme-toggle i'), // Specific icon for theme
        clearChatButton: document.getElementById('clear-chat'),
        manageSessionsToggle: document.getElementById('manage-sessions-toggle'),

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
        toggleProcessLogButton: document.getElementById('toggle-process-log'),

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
        showThinkBubblesToggle: document.getElementById('show-think-bubbles'),
        resetSettingsButton: document.getElementById('reset-settings'),
        saveSettingsButton: document.getElementById('save-settings'),
    };

    // ======== 应用状态与配置 ========
    const APP_PREFIX = 'IDTAgentPro_v8.2_'; // Updated prefix for new version
    let state = {
        sessions: {},
        currentSessionId: null,
        currentTheme: 'auto',
        autoScroll: true,
        soundEnabled: false,
        showThinkBubbles: true, // Now controls if thinking appears in chat bubble
        animationLevel: 'full',
        currentMode: 'chat',
        uploadedFiles: [],
        isAgentTyping: false,
        isLoading: false,
        isSidebarExpanded: window.innerWidth > 768,
        isSessionManagerCollapsed: false,
        isProcessLogCollapsed: true,
        maxInputChars: 2000,
        lastResponseThinking: null, // Store the thinking process for the latest response
    };

    // ======== WebSocket 相关 ========
    let websocket = null;
    const websocketUrl = `ws://${window.location.host}/ws/chat`;

    function connectWebSocket() {
        if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
            console.log("WebSocket is already connected or connecting.");
            return;
        }
        console.log(`Attempting to connect WebSocket: ${websocketUrl}`);
        websocket = new WebSocket(websocketUrl);

        websocket.onopen = (event) => {
            console.log("WebSocket connection established", event);
            sendWebSocketMessage({
                type: 'init',
                session_id: state.currentSessionId
            });
        };

        websocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error("Failed to parse WebSocket message:", e, "Raw data:", event.data);
                showToast("Received invalid data format from server.", "error");
            }
        };

        websocket.onerror = (event) => {
            console.error("WebSocket error:", event);
            hideTypingIndicator();
            setLoadingState(false);
            showToast("Communication link error!", "error", 7000);
        };

        websocket.onclose = (event) => {
            console.log("WebSocket connection closed:", event);
            hideTypingIndicator();
            setLoadingState(false);
            const reason = event.reason ? `Reason: ${event.reason}` : 'No specific reason';
            if (event.wasClean) {
                showToast(`Communication link closed (Code: ${event.code}). ${reason}`, "info", 5000);
            } else {
                showToast(`Communication link abruptly disconnected! (Code: ${event.code}). ${reason}`, "error", 7000);
            }
            websocket = null;
        };
    }

    function sendWebSocketMessage(message) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify(message));
        } else {
            console.error("WebSocket connection not open. Cannot send message:", message);
            showToast("Communication link not active. Please wait or refresh.", "warning");
            if (!websocket || websocket.readyState === WebSocket.CLOSED) {
                connectWebSocket();
            }
        }
    }

    function handleWebSocketMessage(message) {
        switch (message.type) {
            case 'init_success':
                state.currentSessionId = message.session_id;
                const agentStatusMessage = message.agent_available === false
                    ? 'Agent core module not loaded. Functionality limited.'
                    : 'Communication link established. Agent ready!';
                const agentStatusType = message.agent_available === false ? 'warning' : 'success';
                showToast(agentStatusMessage, agentStatusType, message.agent_available ? 4000 : 7000);
                
                initializeCurrentSession(true);

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
                     appendMessage("Apologies, the Agent's core module failed to load. I am unable to process your requests at this time.", 'error', false, null, false, [], "System Error");
                }
                setLoadingState(false);
                break;
            case 'error':
                console.error("Server-reported error:", message);
                showToast(`Server error: ${message.message}`, 'error', 6000);
                if (message.details) {
                    appendMessage(`Server error (${message.message}): ${message.details}`, 'error', false, null, false, [], "Server Error");
                }
                setLoadingState(false);
                break;
            case 'status':
                // Store thinking if it's related to the response stage
                if (message.stage === 'response' && message.status === 'thinking_log' && message.details?.thinking) {
                    state.lastResponseThinking = message.details.thinking;
                }
                handleProcessStatus(message); // Still log it to process log as well
                if (!(message.status === 'thinking_log' && !localStorage.getItem(APP_PREFIX + 'showProcessLogThinkBubbles') === 'true')) { // Check dedicated setting for process log
                    showProcessLog(true);
                }
                break;
            case 'final_response':
                hideTypingIndicator();
                setLoadingState(false);
                const finalMessageContent = message.content;
                // Pass the stored thinking process to appendMessage
                appendMessage(finalMessageContent, 'agent', false, state.lastResponseThinking, false, []);
                addMessageToCurrentSession({
                    content: finalMessageContent,
                    sender: 'agent',
                    timestamp: Date.now(),
                    isHTML: false,
                    rawResponse: finalMessageContent,
                    thinking: state.lastResponseThinking, // Store with message for persistence
                });
                state.lastResponseThinking = null; // Clear after use

                if(state.sessions[state.currentSessionId]) {
                    state.sessions[state.currentSessionId].lastActivity = Date.now();
                }
                saveSessions();
                renderSessionList();
                break;
            default:
                console.warn("Received unknown WebSocket message type:", message.type, message);
        }
    }

    function setLoadingState(isLoading) {
        state.isLoading = isLoading;
        dom.sendButton.disabled = isLoading;
        dom.sendIcon.style.display = isLoading ? 'none' : 'inline-block';
        dom.sendLoadingIcon.style.display = isLoading ? 'inline-block' : 'none';
    }

    function handleProcessStatus(statusMessage) {
        const { stage, status, details = {}, message: messageText = '' } = statusMessage;
        let logItemClass = `log-item stage-${stage} status-${status}`;
        let logIconClass = 'fas fa-info-circle';

        if (status === 'started' || status === 'retrying_exec') logIconClass = 'fas fa-spinner fa-spin';
        else if (status === 'completed' && (!details.error_type && (!details.result || details.result.status === 'success'))) logIconClass = 'fas fa-check-circle log-success';
        else if (status === 'error' || status === 'failure' || (status === 'completed' && (details.error_type || (details.result && details.result.status !== 'success')))) {
            logIconClass = 'fas fa-times-circle log-error';
            logItemClass += ' status-error-type';
        }
        else if (status === 'warning') logIconClass = 'fas fa-exclamation-triangle log-warning';
        else if (status === 'ignored') logIconClass = 'fas fa-eye-slash log-muted';
        else if (status === 'retrying') logIconClass = 'fas fa-history log-info';
        else if (status === 'aborted') logIconClass = 'fas fa-ban log-warning';

        let logDescription = messageText || `Status: ${stage} - ${status}`;

        if (stage === 'action' && statusMessage.tool_status) {
            logItemClass = `log-item stage-action tool-status-${statusMessage.tool_status}`;
            if (details.result && details.result.status) {
                logItemClass += ` status-${details.result.status}`;
            }
            if (statusMessage.tool_status === 'started') logIconClass = 'fas fa-cog fa-spin log-info';
            else if (statusMessage.tool_status === 'completed' && details.result?.status === 'success') logIconClass = 'fas fa-check log-success';
            else if (statusMessage.tool_status === 'failure' || (statusMessage.tool_status === 'completed' && details.result?.status !== 'success')) logIconClass = 'fas fa-times log-error';
            else if (statusMessage.tool_status === 'retrying') logIconClass = 'fas fa-history log-info';
            else if (statusMessage.tool_status === 'retrying_exec') logIconClass = 'fas fa-spinner fa-spin log-info';
        }
        
        // Check a different setting for process log thinking bubbles
        const showProcessLogThink = (localStorage.getItem(APP_PREFIX + 'showProcessLogThinkBubbles') || 'true') === 'true';

        if (status === 'thinking_log' && details.thinking) {
            if (showProcessLogThink) { // Use the dedicated setting here
                const thinkLabel = messageText || `Thinking (${stage.charAt(0).toUpperCase() + stage.slice(1)})`;
                appendLogItemWithThink(thinkLabel, 'fas fa-brain log-think', logItemClass, details.thinking, "Agent's Thought Process (Log)");
            }
            // Do not return if stage is not 'response', so other thinking logs are still shown as normal items if bubbles are off.
            // If it *is* a response thinking log, it's handled for chat bubble, so can be skipped here if bubbles are off for log.
            if (stage === 'response' && !showProcessLogThink) return;
            if (stage !== 'response' && !showProcessLogThink) {
                appendLogItem(messageText || `Thinking log received (${stage})`, 'fas fa-brain log-think', logItemClass);
            }
            return;
        }
        
        if (stage === 'planning' && status === 'started') showTypingIndicator();
        // The "Generating final response..." is now its own status "completed" message for the response stage
        // else if (stage === 'response' && status === 'started') showTypingIndicator(); // Keep this for "Generating final response..."
        
        appendLogItem(logDescription, logIconClass, logItemClass);
    }

    function appendLogItem(text, iconClass, classes = '') {
        const logItemDiv = document.createElement('div');
        logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
        logItemDiv.style.setProperty('--animate-duration', '0.3s');
        if (classes) logItemDiv.classList.add(...classes.split(' '));
        
        const iconEl = document.createElement('i');
        iconEl.className = iconClass;
        
        const textEl = document.createElement('span');
        textEl.className = 'log-item-text';
        textEl.textContent = text;

        logItemDiv.appendChild(iconEl);
        logItemDiv.appendChild(textEl);
        dom.processLogContent.appendChild(logItemDiv);
        scrollToProcessLogBottom();
    }

    function appendLogItemWithThink(text, iconClass, classes, thinkContent, thinkLabel) {
        const logItemDiv = document.createElement('div');
        logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
        logItemDiv.style.setProperty('--animate-duration', '0.3s');
        if (classes) logItemDiv.classList.add(...classes.split(' '));

        const headerDiv = document.createElement('div');
        headerDiv.className = 'log-item-header';

        const iconEl = document.createElement('i');
        iconEl.className = iconClass;
        
        const textEl = document.createElement('span');
        textEl.className = 'log-item-text';
        textEl.textContent = text;

        headerDiv.appendChild(iconEl);
        headerDiv.appendChild(textEl);
        logItemDiv.appendChild(headerDiv);

        if (thinkContent) {
           const thinkDiv = document.createElement('div');
           thinkDiv.classList.add('log-think-content');
           let formattedThink = thinkContent.replace(/\n/g, '<br>');
            try {
               const jsonMatch = formattedThink.match(/```json([\s\S]*?)```/i);
               if (jsonMatch && jsonMatch[1]) {
                    const jsonContent = jsonMatch[1].trim();
                    try {
                        const parsedJson = JSON.parse(jsonContent);
                        formattedThink = formattedThink.replace(jsonMatch[0], `<pre><code class="language-json">${JSON.stringify(parsedJson, null, 2)}</code></pre>`);
                    } catch (jsonErr) {
                        console.warn("Log area JSON parsing failed:", jsonErr);
                        formattedThink = formattedThink.replace(jsonMatch[0], `<pre><code class="language-json error">${jsonContent} (JSON Parse Error)</code></pre>`);
                    }
               }
            } catch (e) { console.error("Error processing JSON in log:", e); }

           thinkDiv.innerHTML = `<strong>${thinkLabel}:</strong><div class="think-bubble">${formattedThink}</div>`;
           logItemDiv.appendChild(thinkDiv);
        }
        dom.processLogContent.appendChild(logItemDiv);
        scrollToProcessLogBottom();
    }
    
    function scrollToProcessLogBottom(instant = false) {
        if (!dom.processLogContainer) return;
        const behavior = instant || state.animationLevel === 'none' ? 'instant' : 'smooth';
        dom.processLogContainer.scrollTo({ top: dom.processLogContainer.scrollHeight, behavior });
    }

    function showProcessLog(ensureExpanded = false) {
        if (!dom.processLogContainer) return;
        dom.processLogContainer.style.display = 'block';
        if (state.animationLevel !== 'none' && !dom.processLogContainer.classList.contains('animate__fadeInDown')) {
            dom.processLogContainer.classList.remove('animate__fadeOutUp');
            dom.processLogContainer.classList.add('animate__animated', 'animate__fadeInDown');
            dom.processLogContainer.style.setProperty('--animate-duration', '0.3s');
        }
        if (ensureExpanded && state.isProcessLogCollapsed) {
            toggleProcessLogCollapse();
        }
    }

    function hideProcessLog() {
        if (!dom.processLogContainer) return;
        if (state.animationLevel !== 'none') {
            dom.processLogContainer.classList.replace('animate__fadeInDown', 'animate__fadeOutUp') || dom.processLogContainer.classList.add('animate__animated','animate__fadeOutUp');
            dom.processLogContainer.addEventListener('animationend', () => {
                dom.processLogContainer.style.display = 'none';
                dom.processLogContainer.classList.remove('animate__animated','animate__fadeOutUp');
            }, {once: true});
        } else {
            dom.processLogContainer.style.display = 'none';
        }
    }

    function toggleProcessLogCollapse() {
        state.isProcessLogCollapsed = !state.isProcessLogCollapsed;
        dom.processLogContainer.classList.toggle('collapsed', state.isProcessLogCollapsed);
        const iconElement = dom.toggleProcessLogButton.querySelector('i');
        if (iconElement) {
            iconElement.className = state.isProcessLogCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
        }
        // Save this specific setting, different from the main 'showThinkBubbles' for chat
        localStorage.setItem(APP_PREFIX + 'processLogCollapsed', state.isProcessLogCollapsed.toString());
    }
    
    async function initializeApp() {
        console.log("IDT Agent Pro Initializing...");
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
        
        updateProcessLogCollapseState(state.isProcessLogCollapsed, true); // Apply loaded collapse state for process log
        // Apply loaded state for process log's own thinking bubbles
        if (dom.showThinkBubblesToggle) { // Ensure element exists before setting
             // Note: This showThinkBubblesToggle is for chat display.
             // We need a separate one if we want to control process log bubbles independently.
             // For now, let's assume the current toggle controls chat bubbles.
             // A new setting `showProcessLogThinkBubbles` would be needed for independent control.
        }


        connectWebSocket();
        updateLoaderProgress(95);
        
        setTimeout(() => {
             if (dom.loaderProgress) dom.loaderProgress.style.width = '100%';
        }, 200);
        console.log("IDT Agent Pro initialization sequence complete, awaiting WebSocket confirmation.");
    }

    function updateLoaderProgress(percentage) {
        if (dom.loaderProgress) {
            dom.loaderProgress.style.width = `${percentage}%`;
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

        dom.openSettingsButton.addEventListener('click', openSettingsModal);
        dom.closeSettingsButton.addEventListener('click', () => closeSettingsModal(true)); // Pass true to revert changes on simple close
        dom.saveSettingsButton.addEventListener('click', () => {
            collectAndSaveSettings();
            closeSettingsModal(false); // Pass false as settings are saved
            showToast('Personalization parameters calibrated and saved!', 'success');
        });
        dom.resetSettingsButton.addEventListener('click', resetToDefaultSettings);
        
        dom.fontSizeInput.addEventListener('input', () => {
            const newSize = dom.fontSizeInput.value;
            dom.fontSizeValue.textContent = `${newSize}px`;
            document.body.style.fontSize = `${newSize}px`;
        });
        dom.animationLevelSelect.addEventListener('change', (e) => {
            applyAnimationLevel(e.target.value);
        });
        
        dom.settingsModal.addEventListener('click', (e) => {
            if (e.target === dom.settingsModal) closeSettingsModal(true);
        });
        
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (state.currentTheme === 'auto') applyCurrentTheme();
        });

        dom.toggleProcessLogButton.addEventListener('click', toggleProcessLogCollapse);
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
        return `session_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
    }

    function initializeCurrentSession(isInitialLoad = false) {
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
        
        state.currentSessionId = targetSessionId;

        if (isInitialLoad || !dom.chatBox.hasChildNodes() || dom.chatBox.querySelector('.message-system-initial')) { 
            switchSession(state.currentSessionId, true);
        } else {
            dom.currentSessionNameDisplay.textContent = state.sessions[state.currentSessionId]?.name || "Session";
        }
        renderSessionList();
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
        saveSessions();

        if (!isInitialCreation) {
            switchSession(newId); // This will now handle WS re-init if needed
            showToast('New communication link established!', 'success');
            if (!state.isSidebarExpanded) updateSidebarState(true);
            if (state.isSessionManagerCollapsed) updateSessionManagerState(false);
        }
        return newId;
    }

    function switchSession(sessionId, isInitialSwitch = false) {
        if (!state.sessions[sessionId]) {
            console.error(`Attempt to switch to non-existent session: ${sessionId}`);
            const fallbackId = createNewSession(true); // Create a new one if target is invalid
            state.currentSessionId = fallbackId; // Update state.currentSessionId
            // Now, re-initialize with this new valid ID via WebSocket
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                sendWebSocketMessage({ type: 'init', session_id: fallbackId });
            } else {
                connectWebSocket(); // connect will send init
            }
            // Visual placeholders until WS confirms
            dom.chatBox.innerHTML = '';
            appendMessage("Initializing new session...", "system", false, null, true);
            dom.currentSessionNameDisplay.textContent = state.sessions[fallbackId]?.name || "New Session";
            renderSessionList();
            return;
        }

        // If it's a user-initiated switch to a *different* session
        if (!isInitialSwitch && state.currentSessionId !== sessionId) {
             if (websocket && websocket.readyState === WebSocket.OPEN) {
                 state.currentSessionId = sessionId; // Update state.currentSessionId first
                 sendWebSocketMessage({ type: 'init', session_id: sessionId });
                 // Clear chat and show loading indicator, actual content loads on init_success
                 dom.chatBox.innerHTML = '';
                 appendMessage("Loading session...", "system", false, null, true, [], "System Loading");
                 dom.currentSessionNameDisplay.textContent = state.sessions[sessionId]?.name || "Loading...";
                 return; 
             } else {
                 console.warn("WebSocket not connected during session switch. Attempting to connect.");
                 state.currentSessionId = sessionId; // Update state.currentSessionId
                 connectWebSocket(); // connectWebSocket will handle sending the init message
                 // UI updates for local switch until WS connects
                 dom.chatBox.innerHTML = '';
                 appendMessage("Reconnecting and loading session...", "system", false, null, true, [], "System Reconnecting");
                 dom.currentSessionNameDisplay.textContent = state.sessions[sessionId]?.name || "Reconnecting...";
                 renderSessionList();
                 return;
             }
        }
        
        // This part now primarily runs on initial load or after init_success confirms the session
        state.currentSessionId = sessionId;
        if(state.sessions[sessionId]) { // Ensure session exists after potential async operations
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
                appendMessage(msg.content, msg.sender, msg.isHTML, msg.thinking, true, msg.attachments);
            });
        }
        scrollToBottom(true);
        renderSessionList();
        dom.userInput.focus();
        
        dom.processLogContent.innerHTML = '';
        if (!state.isProcessLogCollapsed && dom.processLogContainer.style.display !== 'none') {
             updateProcessLogCollapseState(true, true); // Collapse log, instant
        }
        console.log(`Active session: ${state.sessions[sessionId]?.name} (ID: ${sessionId})`);
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
                listItem.addEventListener('animationend', () => listItem.remove(), {once: true});
             } else {
                listItem.remove();
             }
        }

        delete state.sessions[sessionId];

        if (state.currentSessionId === sessionId) {
            const remainingSessions = Object.values(state.sessions).sort((a,b)=> b.lastActivity - a.lastActivity);
            if (remainingSessions.length > 0) {
                // Switch to the most recent remaining session. switchSession will handle WS re-init.
                switchSession(remainingSessions[0].id); 
            } else {
                // No sessions left, create a new one. createNewSession then calls switchSession.
                createNewSession(); 
            }
        } else {
            // If deleted session was not active, just save and re-render list
            saveSessions();
            renderSessionList();
        }
        showToast(`Session "${sessionName}" has been archived.`, 'info');
        if(Object.keys(state.sessions).length === 0 && dom.sessionList) renderSessionList(); 
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
        if (!dom.sessionList) return; // Guard if element not found
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
             if (state.animationLevel === 'full' && !listItem.classList.contains('active-session')) { // Avoid re-animating active
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
                if (state.currentSessionId !== session.id) switchSession(session.id);
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
        localStorage.setItem(APP_PREFIX + 'sessions', JSON.stringify(state.sessions));
    }

    function loadSessions() {
        const storedSessions = localStorage.getItem(APP_PREFIX + 'sessions');
        if (storedSessions) {
            try {
                 const parsedSessions = JSON.parse(storedSessions);
                 // Validate and structure each session
                 Object.keys(parsedSessions).forEach(id => {
                     const s = parsedSessions[id];
                     if (s && typeof s.id === 'string' && typeof s.name === 'string' && Array.isArray(s.messages)) {
                         state.sessions[id] = {
                             id: s.id,
                             name: s.name || "Untitled Session",
                             messages: s.messages.map(m => ({ // Ensure messages have all needed fields
                                 content: m.content || "",
                                 sender: m.sender || "system",
                                 timestamp: m.timestamp || Date.now(),
                                 isHTML: m.isHTML || false,
                                 attachments: m.attachments || [],
                                 thinking: m.thinking || null, // Load stored thinking
                                 rawResponse: m.rawResponse, // May be undefined
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
        localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());
        if (!instant && state.animationLevel !== 'none') {
            dom.sidebar.style.transition = state.isSidebarExpanded ? 'width 0.3s ease-out' : 'width 0.2s ease-in';
        } else if (dom.sidebar.style.transition !== 'none') { // Only clear if not already none
            dom.sidebar.style.transition = 'none';
        }
        if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
            updateSessionManagerState(true, instant);
        }
    }
    
    function updateSessionManagerState(collapse, instant = false) {
        state.isSessionManagerCollapsed = collapse;
        dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
        dom.sessionManagerToggle.setAttribute('aria-expanded', (!state.isSessionManagerCollapsed).toString());
        localStorage.setItem(APP_PREFIX + 'sessionManagerCollapsed', state.isSessionManagerCollapsed.toString());

        if (!instant && state.animationLevel !== 'none') {
            dom.sessionListContainer.style.transition = 'max-height 0.3s ease-in-out, padding 0.3s ease-in-out';
        } else if (dom.sessionListContainer.style.transition !== 'none') {
            dom.sessionListContainer.style.transition = 'none';
        }
    }

    function updateProcessLogCollapseState(collapse, instant = false) {
        state.isProcessLogCollapsed = collapse;
        dom.processLogContainer.classList.toggle('collapsed', state.isProcessLogCollapsed);
        const iconElement = dom.toggleProcessLogButton.querySelector('i');
        if (iconElement) {
            iconElement.className = state.isProcessLogCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
        }
        if (!instant && state.animationLevel !== 'none') {
            dom.processLogContainer.style.transition = 'max-height 0.3s ease-in-out, padding 0.3s ease-in-out';
        } else if (dom.processLogContainer.style.transition !== 'none') {
            dom.processLogContainer.style.transition = 'none';
        }
    }


    async function handleSendMessage() {
        if (state.isLoading) {
            showToast("Processing previous message, please wait...", "warning");
            return;
        }
        const messageText = dom.userInput.value.trim();
        const filesToSend = [...state.uploadedFiles]; // Clone for current message

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
        state.lastResponseThinking = null; // Clear previous thinking for new request cycle
        
        const currentUserMessage = {
            content: messageText,
            sender: 'user',
            timestamp: Date.now(),
            isHTML: false, 
            attachments: filesToSend.map(f => ({ name: f.name, size: f.size, type: f.type }))
        };
        addMessageToCurrentSession(currentUserMessage);
        // Pass raw text and attachments to appendMessage for user
        appendMessage(messageText, 'user', false, null, false, currentUserMessage.attachments);


        const currentSession = state.sessions[state.currentSessionId];
        if (currentSession && currentSession.name.startsWith("Conversation ") && currentSession.messages.filter(m => m.sender === 'user').length === 1) {
            const autoName = messageText.substring(0, 30).trim() || "New Chat";
            currentSession.name = autoName + (messageText.length > 30 ? "..." : "");
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            renderSessionList();
        }

        dom.userInput.value = '';
        adjustTextareaHeight();
        updateCharCounter();
        closeFilePreview(); // Clears state.uploadedFiles and UI

        dom.processLogContent.innerHTML = ''; 
        showProcessLog(true); 

        let backendMessage = messageText;
        if (filesToSend.length > 0) {
             backendMessage += `\n[User conceptually uploaded files: ${filesToSend.map(f => f.name).join(', ')}]`;
        }

        sendWebSocketMessage({
             type: 'message',
             session_id: state.currentSessionId,
             content: backendMessage,
        });
    }

    function addMessageToCurrentSession(messageObject) {
        if (state.sessions[state.currentSessionId]) {
            if (messageObject.sender !== 'agent') {
                 delete messageObject.rawResponse; // Only agents have raw LLM response
            }
             // Ensure thinking is only added if it's an agent message and has thinking
            if (messageObject.sender !== 'agent' || !messageObject.thinking) {
                delete messageObject.thinking;
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
        if(errorType) messageDiv.classList.add(`message-error-type-${errorType.toLowerCase().replace(/\s+/g, '-')}`);


        if (!isSwitchingSession && state.animationLevel !== 'none') {
            const animationClass = state.animationLevel === 'full' ? 'animate__fadeInUp' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
            if (animationClass) {
                messageDiv.classList.add('animate__animated', animationClass);
                messageDiv.style.setProperty('--animate-duration', state.animationLevel === 'full' ? '0.4s' : '0.25s');
            }
        }

        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('message-avatar');
        avatarDiv.innerHTML = sender === 'user' ? '<i class="fas fa-user-astronaut"></i>' : (sender === 'agent' ? '<i class="fas fa-robot"></i>' : '<i class="fas fa-info-circle"></i>');
        messageDiv.appendChild(avatarDiv);

        const messageBubbleDiv = document.createElement('div');
        messageBubbleDiv.classList.add('message-bubble');

        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.classList.add('message-content-wrapper');

        // Prepend thinking process if it's an agent message and thinking content exists and user wants to see it
        if (sender === 'agent' && thinkContent && state.showThinkBubbles) {
            const thinkPrefixDiv = document.createElement('div');
            thinkPrefixDiv.classList.add('message-thought-prefix');
            let formattedThink = thinkContent.replace(/\n/g, '<br>');
            // Basic JSON formatting within thoughts (optional, can be expanded)
            formattedThink = formattedThink.replace(/```json([\s\S]*?)```/gi, (match, jsonContent) => {
                try {
                    const parsed = JSON.parse(jsonContent);
                    return `<pre class="embedded-json"><code>${JSON.stringify(parsed, null, 2)}</code></pre>`;
                } catch (e) {
                    return `<pre class="embedded-json error"><code>${jsonContent} (Invalid JSON)</code></pre>`;
                }
            });
            thinkPrefixDiv.innerHTML = `<strong>Agent's Reasoning:</strong> ${formattedThink}`;
            messageContentWrapper.appendChild(thinkPrefixDiv);
        }


        const textContentDiv = document.createElement('div');
        textContentDiv.classList.add('message-text-content');

        if (isHTML) {
            textContentDiv.innerHTML = content;
        } else {
            const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
            const linkedContent = content
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;").replace(/'/g, "&#039;")
                .replace(/\n/g, '<br>')
                .replace(urlRegex, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
            textContentDiv.innerHTML = linkedContent;
        }
        messageContentWrapper.appendChild(textContentDiv);

        if (attachments && attachments.length > 0) {
            const attachmentsDiv = document.createElement('div');
            attachmentsDiv.classList.add('message-attachments-summary'); // Changed class name
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
        dom.chatBox.appendChild(messageDiv);

        if (!isSwitchingSession) {
           scrollToBottom();
        }
    }
    
    function appendWelcomeMessage() {
        // Clear previous message if it's system loading message
        const lastMessage = dom.chatBox.lastElementChild;
        if (lastMessage && lastMessage.classList.contains('message-system') && lastMessage.textContent.includes("Loading session...")) {
            lastMessage.remove();
        }

        const welcomeHTML = `
            <div class="message-content">
                <div class="welcome-header">
                    <i class="fas fa-robot robot-icon animate__animated animate__pulse animate__infinite" style="--animate-duration: 2s;"></i>
                    <h2>IDT 智能助手 <span class="version-pro">Pro</span></h2>
                </div>
                <p>我是您的电路设计与编程高级助理。已准备就绪，随时为您服务！</p>
                <div class="capabilities">
                    <div class="capability"><i class="fas fa-bolt"></i><span>快速响应</span></div>
                    <div class="capability"><i class="fas fa-brain"></i><span>深度分析</span></div>
                    <div class="capability"><i class="fas fa-code-branch"></i><span>多任务处理</span></div>
                    <div class="capability"><i class="fas fa-cogs"></i><span>工具调用</span></div>
                </div>
                 <div class="quick-actions">
                    <p>您可以尝试以下指令开始：</p>
                    <ul>
                        <li><a href="#" class="quick-action-btn" data-message="添加一个1kΩ的电阻R1">添加电阻R1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="添加一个LED，命名为LED1">添加LED1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="将R1与LED1的正极连接">连接R1与LED1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="当前电路状态如何？">描述电路</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="清空电路">清空电路</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="什么是欧姆定律？">欧姆定律</a></li>
                    </ul>
                 </div>
            </div>
        `;
        const welcomeDiv = document.createElement('div');
        // Add a unique class to identify this specific welcome message if needed
        welcomeDiv.className = 'message system-message system-message-initial animate__animated animate__fadeInUp'; 
        welcomeDiv.innerHTML = welcomeHTML;
        dom.chatBox.appendChild(welcomeDiv);
        attachQuickActionButtonListeners(welcomeDiv);
    }


    function scrollToBottom(instant = false) {
        if (state.autoScroll) {
            const behavior = instant || state.animationLevel === 'none' ? 'instant' : 'smooth';
            dom.chatBox.scrollTo({ top: dom.chatBox.scrollHeight, behavior });
        }
    }

    function showTypingIndicator() {
        if (state.isAgentTyping) return;
        state.isAgentTyping = true;

        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        const animationClass = state.animationLevel !== 'none' ? 'animate__fadeInUp' : '';
        // Apply general message structure for consistency
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
        textContent.innerHTML = `IDT Agent Pro is thinking<span class="typing-dots">${dotsHTML}</span>`;
        
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
        const maxHeight = parseInt(getComputedStyle(dom.userInput).maxHeight, 10) || 200;
        const minHeight = parseInt(getComputedStyle(dom.userInput).minHeight, 10) || 64;

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

        if (!confirm(`Are you sure you want to clear all messages in session "${state.sessions[state.currentSessionId].name}"?`)) {
            return;
        }

        state.sessions[state.currentSessionId].messages = [];
        state.sessions[state.currentSessionId].lastActivity = Date.now();
        saveSessions();

        dom.chatBox.innerHTML = ''; 
        appendWelcomeMessage(); 

        dom.processLogContent.innerHTML = '';
        if (!state.isProcessLogCollapsed) updateProcessLogCollapseState(true, true);

        showToast('Current conversation cleared!', 'info');
        renderSessionList(); 
    }

    function handleModeChange(newMode) {
        if (state.currentMode === newMode) return;
        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === newMode));
        state.currentMode = newMode;
        console.log(`Mode switched to: ${newMode}`);
        showToast(`Switched to ${getModeDisplayName(newMode)} mode`, 'info');
        const sessionName = state.sessions[state.currentSessionId]?.name || 'current session';
        dom.userInput.placeholder = `Message in ${getModeDisplayName(newMode)} mode (${sessionName})...`;
    }

    function getModeDisplayName(mode) {
        const names = { chat: 'Conversation', code: 'Programming', circuit: 'Circuit Design', settings: 'Settings'};
        return names[mode] || 'Unknown';
    }

    function handleFileSelection(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        const MAX_FILES = 5, MAX_SIZE_MB = 10;

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
        if(state.animationLevel !== 'none') fileItem.classList.add('animate__animated', 'animate__bounceIn');
        fileItem.style.setProperty('--animate-duration', '0.4s');
        fileItem.dataset.fileName = file.name; 
        fileItem.dataset.fileSize = file.size;

        const iconClass = getFileIconClass(file.type, file.name);
        fileItem.innerHTML = `
            <i class="fas ${iconClass} file-icon"></i>
            <span class="file-name" title="${file.name} (${(file.size/1024).toFixed(1)}KB)">${file.name}</span>
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
        const codeExtensions = ['.js','.ts', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bat', '.v', '.sv', '.vhd', '.md'];
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
            if(state.animationLevel !== 'none') {
                fileItemElement.classList.replace('animate__bounceIn', 'animate__bounceOut') || fileItemElement.classList.add('animate__bounceOut');
                fileItemElement.addEventListener('animationend', () => {
                    fileItemElement.remove();
                    if (state.uploadedFiles.length === 0) closeFilePreview();
                }, {once: true});
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
            if(themeIcon) themeIcon.className = 'fas fa-desktop';
        }

        if (effectiveTheme === 'dark') {
            document.body.classList.add('dark-theme');
            if(themeIcon && themeName !== 'auto') themeIcon.className = 'fas fa-sun';
        } else { 
            document.body.classList.add('light-theme');
            if(themeIcon && themeName !== 'auto') themeIcon.className = 'fas fa-moon';
        }
        state.currentTheme = themeName;
        
        if(dom.themeSelect) dom.themeSelect.value = themeName;
        
        if(!initialLoad) saveSettings();
        console.log(`Theme applied: ${themeName} (Effective: ${effectiveTheme})`);
    }

    function getThemeDisplayName(theme) { return {'light':'Light Mode','dark':'Dark Mode','auto':'System Default'}[theme] || 'Unknown'; }

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
        if(dom.themeSelect) dom.themeSelect.value = state.currentTheme;
        const currentFontSize = parseFloat(getComputedStyle(document.body).fontSize);
        if(dom.fontSizeInput) dom.fontSizeInput.value = currentFontSize;
        if(dom.fontSizeValue) dom.fontSizeValue.textContent = `${currentFontSize.toFixed(0)}px`;
        if(dom.animationLevelSelect) dom.animationLevelSelect.value = state.animationLevel;
        if(dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        if(dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        if(dom.showThinkBubblesToggle) dom.showThinkBubblesToggle.checked = state.showThinkBubbles;

        dom.settingsModal.style.display = 'flex';
        const modalContent = dom.settingsModal.querySelector('.modal-content');
        modalContent.classList.remove('animate__fadeOutDown', 'animate__zoomOut', 'animate__fadeOut');
        const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInUp' : 'animate__fadeIn') : '';
        if (animIn) modalContent.classList.add('animate__animated', animIn);
        if (state.animationLevel !== 'none') modalContent.style.setProperty('--animate-duration', '0.3s');
    }

    function closeSettingsModal(revertChanges = true) {
        if (revertChanges) {
            applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
            applyAnimationLevel(localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full');
            // Revert other settings if they were live-previewed without saving
            state.showThinkBubbles = (localStorage.getItem(APP_PREFIX + 'showThinkBubbles') || 'true') === 'true';
            if(dom.showThinkBubblesToggle) dom.showThinkBubblesToggle.checked = state.showThinkBubbles;
        }

        const modalContent = dom.settingsModal.querySelector('.modal-content');
        modalContent.classList.remove('animate__fadeInUp', 'animate__zoomIn', 'animate__fadeIn');
        const animOut = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeOutDown' : 'animate__fadeOut') : '';
        
        const animationEndHandler = () => {
            dom.settingsModal.style.display = 'none';
        };

        if (state.animationLevel !== 'none' && animOut) {
             modalContent.classList.add('animate__animated', animOut);
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
        state.showThinkBubbles = dom.showThinkBubblesToggle.checked; // This controls chat bubble thinking
        saveSettings();
    }

    function saveSettings() {
        localStorage.setItem(APP_PREFIX + 'theme', state.currentTheme);
        localStorage.setItem(APP_PREFIX + 'fontSize', document.body.style.fontSize.replace('px',''));
        localStorage.setItem(APP_PREFIX + 'animationLevel', state.animationLevel);
        localStorage.setItem(APP_PREFIX + 'autoScroll', state.autoScroll.toString());
        localStorage.setItem(APP_PREFIX + 'soundEnabled', state.soundEnabled.toString());
        localStorage.setItem(APP_PREFIX + 'showThinkBubbles', state.showThinkBubbles.toString()); // For chat
        localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());
        localStorage.setItem(APP_PREFIX + 'sessionManagerCollapsed', state.isSessionManagerCollapsed.toString());
        localStorage.setItem(APP_PREFIX + 'processLogCollapsed', state.isProcessLogCollapsed.toString());
        // Add a separate setting for process log thinking visibility if desired
        // localStorage.setItem(APP_PREFIX + 'showProcessLogThinkBubbles', state.showProcessLogThinkBubbles.toString());
        console.log("Settings saved to localStorage.");
    }

    function loadSettings() {
        state.currentTheme = localStorage.getItem(APP_PREFIX + 'theme') || 'auto';
        // fontSize and animationLevel are applied in initializeApp after load
        state.animationLevel = localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full';

        state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || 'true') === 'true';
        state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || 'false') === 'true';
        state.showThinkBubbles = (localStorage.getItem(APP_PREFIX + 'showThinkBubbles') || 'true') === 'true'; // For chat
        state.isSidebarExpanded = (localStorage.getItem(APP_PREFIX + 'sidebarExpanded') || (window.innerWidth > 768).toString()) === 'true';
        state.isSessionManagerCollapsed = (localStorage.getItem(APP_PREFIX + 'sessionManagerCollapsed') || 'false') === 'true';
        state.isProcessLogCollapsed = (localStorage.getItem(APP_PREFIX + 'processLogCollapsed') || 'true') === 'true';

        // Update modal UI elements if they exist
        if(dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        if(dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        if(dom.showThinkBubblesToggle) dom.showThinkBubblesToggle.checked = state.showThinkBubbles;
    }

    function resetToDefaultSettings() {
        const defaults = {
            theme: 'auto',
            fontSize: '16',
            animationLevel: 'full',
            autoScroll: true,
            soundEnabled: false,
            showThinkBubbles: true, // For chat
            sidebarExpanded: window.innerWidth > 768,
            sessionManagerCollapsed: false,
            processLogCollapsed: true,
        };
        applyTheme(defaults.theme);
        applyFontSize(defaults.fontSize);
        applyAnimationLevel(defaults.animationLevel);
        state.autoScroll = defaults.autoScroll;
        state.soundEnabled = defaults.soundEnabled;
        state.showThinkBubbles = defaults.showThinkBubbles;
        updateSidebarState(defaults.sidebarExpanded, true);
        updateSessionManagerState(defaults.sessionManagerCollapsed, true);
        updateProcessLogCollapseState(defaults.processLogCollapsed, true);


        if(dom.themeSelect) dom.themeSelect.value = defaults.theme;
        if(dom.fontSizeInput) dom.fontSizeInput.value = defaults.fontSize;
        if(dom.fontSizeValue) dom.fontSizeValue.textContent = `${defaults.fontSize}px`;
        if(dom.animationLevelSelect) dom.animationLevelSelect.value = defaults.animationLevel;
        if(dom.autoScrollToggle) dom.autoScrollToggle.checked = defaults.autoScroll;
        if(dom.soundEnabledToggle) dom.soundEnabledToggle.checked = defaults.soundEnabled;
        if(dom.showThinkBubblesToggle) dom.showThinkBubblesToggle.checked = defaults.showThinkBubbles;
        
        saveSettings();
        showToast('All parameters reset to factory settings!', 'success');
    }

    function showToast(message, type = 'info', duration = 3500) {
        const toast = document.createElement('div');
        toast.classList.add('toast', type);
        const animIn = state.animationLevel === 'full' ? 'animate__fadeInRight' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
        const animOut = state.animationLevel === 'full' ? 'animate__fadeOutRight' : (state.animationLevel === 'basic' ? 'animate__fadeOut' : '');
        
        if (state.animationLevel !== 'none' && animIn) {
            toast.classList.add('animate__animated', animIn);
            toast.style.setProperty('--animate-duration', '0.4s');
        }

        const icons = {'info':'fa-info-circle', 'success':'fa-check-circle', 'warning':'fa-exclamation-triangle', 'error':'fa-times-circle'};
        const iconClass = icons[type] || 'fa-info-circle';
        
        toast.innerHTML = `
            <i class="fas ${iconClass} toast-icon"></i>
            <span class="toast-message">${message}</span>
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
                toast.addEventListener('animationend', () => toast.remove(), {once: true});
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
        }
    }

    initializeApp();
    attachQuickActionButtonListeners(dom.chatBox);
});