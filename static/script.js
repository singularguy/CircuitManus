// 启用 JavaScript 严格模式，有助于捕捉常见错误，提高代码质量
"use strict";

// 当整个 HTML 文档加载完成并解析完毕后执行回调函数
document.addEventListener('DOMContentLoaded', () => {
    // ======== DOM 元素获取 (集中管理，方便维护) ========
    const dom = {
        // 加载动画相关
        loader: document.getElementById('loader'), // 加载动画容器
        loaderProgress: document.querySelector('.loader-progress'), // 加载进度条
        mainContainer: document.getElementById('main-container'), // 主应用容器

        // 聊天核心区域
        chatBox: document.getElementById('chat-box'), // 消息显示区域
        userInput: document.getElementById('user-input'), // 用户输入文本框
        sendButton: document.getElementById('send-button'), // 发送按钮
        sendIcon: document.querySelector('.send-icon'), // 发送按钮内的 SVG 图标
        sendLoadingIcon: document.querySelector('.send-loading-icon'), // 发送按钮内的加载中 FontAwesome 图标

        // 头部与主题
        themeToggleButton: document.getElementById('theme-toggle'), // 主题切换按钮
        themeToggleIcon: document.querySelector('#theme-toggle i'), // 主题切换按钮内的图标
        clearChatButton: document.getElementById('clear-chat'), // 清空当前聊天按钮
        manageSessionsToggle: document.getElementById('manage-sessions-toggle'), // 头部会话管理/侧边栏切换按钮

        // 侧边栏与会话管理
        sidebar: document.getElementById('sidebar'), // 侧边栏容器
        sidebarButtons: document.querySelectorAll('.sidebar-button'), // 侧边栏所有功能模式按钮
        sessionManager: document.getElementById('session-manager'), // 会话历史管理区域
        sessionManagerToggle: document.getElementById('session-manager-toggle'), // 会话历史折叠/展开触发器
        sessionListContainer: document.getElementById('session-list-container'), // 会话列表容器
        sessionList: document.getElementById('session-list'), // 会话列表 (ul元素)
        createNewSessionButton: document.getElementById('create-new-session'), // 新建会话按钮
        chatHeader: document.getElementById('chat-header'), // 聊天区域顶部，显示当前会话名称
        currentSessionNameDisplay: document.getElementById('current-session-name'), // 显示当前会话名称的元素
        editSessionNameButton: document.getElementById('edit-session-name-btn'), // 编辑会话名称按钮

        // 输入区域与文件上传
        attachButton: document.getElementById('attach-button'), // 添加附件按钮
        micButton: document.getElementById('mic-button'), // 语音输入按钮
        charCounter: document.getElementById('char-counter'), // 字符计数器
        fileInput: document.getElementById('file-input'), // 隐藏的文件选择输入框
        filePreviewArea: document.getElementById('file-preview'), // 文件预览区域容器
        filePreviewContent: document.getElementById('file-preview-content'), // 文件预览内容显示区
        closeFilePreviewButton: document.getElementById('close-preview'), // 关闭文件预览按钮

        // Toast 通知
        toastContainer: document.getElementById('toast-container'), // Toast 通知容器

        // Agent 处理过程日志区域
        processLogContainer: document.getElementById('process-log-container'), // 日志容器
        processLogContent: document.getElementById('process-log-content'),     // 日志内容显示区
        toggleProcessLogButton: document.getElementById('toggle-process-log'), // 日志折叠/展开按钮

        // 设置模态框相关
        settingsModal: document.getElementById('settings-modal'), // 设置模态框容器
        openSettingsButton: document.querySelector('.sidebar-button[data-mode="settings"]'), // 侧边栏打开设置的按钮
        closeSettingsButton: document.getElementById('close-settings'), // 关闭设置模态框的按钮
        themeSelect: document.getElementById('theme-select'), // 主题选择下拉框
        fontSizeInput: document.getElementById('font-size'), // 字号调整滑块
        fontSizeValue: document.getElementById('font-size-value'), // 显示当前字号的元素
        animationLevelSelect: document.getElementById('animation-level'), // 动画级别选择下拉框
        autoScrollToggle: document.getElementById('auto-scroll'), // 自动滚动开关
        soundEnabledToggle: document.getElementById('sound-enabled'), // 消息提示音开关
        showThinkBubblesToggle: document.getElementById('show-think-bubbles'), // 是否在日志中显示思考过程开关
        resetSettingsButton: document.getElementById('reset-settings'), // 恢复默认设置按钮
        saveSettingsButton: document.getElementById('save-settings'), // 保存设置按钮

        // 欢迎消息中的快速操作按钮
        quickActionButtons: document.querySelectorAll('.quick-action-btn'), // 所有快速操作按钮
    };

    // ======== 应用状态与配置 ========
    const APP_PREFIX = 'IDTAgentPro_v8_'; // localStorage 存储键的前缀，用于版本区分和避免冲突
    let state = {
        sessions: {}, // 存储所有会话数据，键为 sessionId，值为 { id, name, messages: [], createdAt, lastActivity }
        currentSessionId: null, // 当前活动的会话 ID
        currentTheme: 'auto', // 当前主题 ('auto', 'light', 'dark')
        autoScroll: true, // 是否自动滚动聊天框到底部
        soundEnabled: false, // 是否启用消息提示音 (待实现)
        showThinkBubbles: true, // 是否在处理日志中显示 Agent 的思考过程
        animationLevel: 'full', // 动画效果级别 ('full', 'basic', 'none')
        currentMode: 'chat', // 当前操作模式 ('chat', 'code', 'circuit')，'settings' 通过模态框处理
        uploadedFiles: [], // 存储用户已选择但尚未发送的文件列表 (File 对象数组)
        isAgentTyping: false, // Agent 是否正在生成回复 (用于显示打字指示器)
        isLoading: false, // 应用是否正在处理用户请求 (发送中或等待回复，用于禁用发送按钮等)
        isSidebarExpanded: false, // 左侧边栏是否展开
        isSessionManagerCollapsed: true, // 会话历史区域是否折叠
        isProcessLogCollapsed: false, // 处理日志区域是否折叠 (false 表示默认展开)
        maxInputChars: 2000, // 用户输入框最大字符数
    };

    // ======== WebSocket 相关 ========
    let websocket = null; // WebSocket 实例
    const websocketUrl = `ws://${window.location.host}/ws/chat`; // WebSocket 连接的 URL

    // 函数：连接 WebSocket 服务器
    function connectWebSocket() {
        // 如果 WebSocket 已经连接或正在连接中，则不重复连接
        if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
            console.log("WebSocket 已连接或正在连接中。");
            return;
        }

        console.log(`尝试连接 WebSocket: ${websocketUrl}`);
        websocket = new WebSocket(websocketUrl); // 创建 WebSocket 实例

        // WebSocket 连接成功打开时的回调
        websocket.onopen = (event) => {
            console.log("WebSocket 连接成功", event);
            // 连接成功后，发送初始化消息给后端，包含当前会话 ID (如果存在) 或请求新的
            sendWebSocketMessage({
                type: 'init', // 消息类型为初始化
                session_id: state.currentSessionId // 发送当前会话 ID (可能为 null，后端会处理)
            });
            // 初始化成功的 Toast 提示移到接收到 'init_success' 消息时显示
        };

        // 收到 WebSocket 服务器消息时的回调
        websocket.onmessage = (event) => {
            console.log("RAW WebSocket Data Received:", event.data); // 打印原始数据，方便调试
            try {
                const message = JSON.parse(event.data); // 解析收到的 JSON 字符串消息
                handleWebSocketMessage(message); // 处理不同类型的消息
            } catch (e) {
                console.error("解析 WebSocket 消息失败:", e, "原始数据:", event.data);
                showToast("接收到无效数据格式。", "error");
            }
        };

        // WebSocket 发生错误时的回调
        websocket.onerror = (event) => {
            console.error("WebSocket 错误:", event);
            hideTypingIndicator(); // 错误时隐藏打字指示器
            state.isLoading = false; // 解除加载状态
            dom.sendButton.disabled = false; // 启用发送按钮
            dom.sendIcon.style.display = 'inline-block'; // 显示发送图标
            dom.sendLoadingIcon.style.display = 'none'; // 隐藏加载图标
            showToast("通讯链路发生错误!", "error");
        };

        // WebSocket 连接关闭时的回调
        websocket.onclose = (event) => {
            console.log("WebSocket 连接已关闭:", event);
             hideTypingIndicator(); // 关闭时隐藏打字指示器
             state.isLoading = false; // 解除加载状态
             dom.sendButton.disabled = false;
             dom.sendIcon.style.display = 'inline-block';
             dom.sendLoadingIcon.style.display = 'none';
            if (event.wasClean) { // 判断是否是正常关闭
                console.log(`连接正常关闭, code=${event.code} reason=${event.reason}`);
                showToast(`通讯链路已关闭 (代码: ${event.code})`, "info");
            } else { // 异常断开
                console.error('连接异常断开');
                showToast(`通讯链路异常断开! (${event.code})`, "error");
            }
            websocket = null; // 清除 WebSocket 实例引用，方便重连时重新创建
            // 可以在此实现自动重连逻辑
            // setTimeout(connectWebSocket, 5000); // 例如：5秒后尝试重连
        };
    }

    // 函数：通过 WebSocket 发送消息给服务器
    function sendWebSocketMessage(message) {
        if (websocket && websocket.readyState === WebSocket.OPEN) { // 确保连接已打开
            websocket.send(JSON.stringify(message)); // 发送 JSON 字符串消息
            // console.log("WebSocket 消息已发送:", message); // DEBUG 时启用，过于频繁会影响性能
        } else {
            console.error("WebSocket 连接未开启，无法发送消息:", message);
            showToast("通讯链路未连接，请稍候...", "warning");
            connectWebSocket(); // 尝试重连
        }
    }

    // 函数：处理从 WebSocket 服务器接收到的不同类型的消息
    function handleWebSocketMessage(message) {
        // console.log("收到 WebSocket 消息:", message); // DEBUG 时启用

        if (message.type === 'init_success') { // 后端初始化成功
            state.currentSessionId = message.session_id; // 更新当前会话 ID
            if (message.agent_available === false) { // 如果 Agent 核心模块不可用
                showToast('Agent核心模块未加载，功能受限。', 'error', 8000);
            } else {
                showToast('通讯链路已建立，Agent已准备就绪!', 'success');
            }
            initializeCurrentSession(true); // 初始化或加载当前会话 (true 表示这是首次加载)

            if (dom.loader) {
                dom.loader.classList.add('hidden');
            }
            if (dom.mainContainer) {
                dom.mainContainer.classList.add('loaded');
            }
            return;
        }

        if (message.type === 'init_error') { // 后端初始化失败
            showToast(`Agent 初始化失败: ${message.message}`, 'error', 10000);
            // 即使初始化失败，也隐藏加载动画
            if (dom.loader) dom.loader.classList.add('hidden');
            if (dom.mainContainer) dom.mainContainer.classList.add('loaded');

            if (message.agent_available === false) {
                 appendMessage("抱歉，Agent核心模块未能加载，无法处理您的请求。", 'error', false, null);
            }
            hideTypingIndicator();
            state.isLoading = false;
            dom.sendButton.disabled = false;
            dom.sendIcon.style.display = 'inline-block';
            dom.sendLoadingIcon.style.display = 'none';
            return;
        }

        if (message.type === 'error') { // 通用错误消息
             console.error("服务器报告错误:", message);
             showToast(`服务器错误: ${message.message}`, 'error', 5000);
             if (message.details) {
                 appendMessage(`服务器报告错误 (${message.message}): ${message.details}`, 'error');
                 hideTypingIndicator();
                 state.isLoading = false;
                 dom.sendButton.disabled = false;
                 dom.sendIcon.style.display = 'inline-block';
                 dom.sendLoadingIcon.style.display = 'none';
             }
             return;
        }

        if (message.type === 'status') { // Agent 处理状态更新消息
            handleProcessStatus(message);
            showProcessLog();
            return;
        }

        if (message.type === 'final_response') { // Agent 最终回复消息
            hideTypingIndicator();
            state.isLoading = false;
            dom.sendButton.disabled = false;
            dom.sendIcon.style.display = 'inline-block';
            dom.sendLoadingIcon.style.display = 'none';

            const finalMessageContent = message.content;
            appendMessage(finalMessageContent, 'agent', false, null);

            const agentMessageData = {
                content: finalMessageContent,
                sender: 'agent',
                timestamp: Date.now(),
                isHTML: false,
                rawResponse: finalMessageContent,
            };
            addMessageToCurrentSession(agentMessageData);
            if(state.sessions[state.currentSessionId]) { // Ensure session exists
                state.sessions[state.currentSessionId].lastActivity = Date.now();
            }
            saveSessions();
            renderSessionList();
            return;
        }

        console.warn("收到未知 WebSocket 消息类型:", message.type, message);
    }

    // ======== 处理 Agent 过程状态更新并显示到日志区 ========
    function handleProcessStatus(statusMessage) {
        const stage = statusMessage.stage;
        const status = statusMessage.status; // e.g., 'started', 'completed', 'error', 'thinking_log', 'retrying', 'retrying_exec', 'aborted'
        const details = statusMessage.details || {};
        const messageText = statusMessage.message || '';

        let logItemClass = `log-item stage-${stage} status-${status}`;
        let logIconClass = 'fas fa-info-circle';

        // Default icons based on primary status
        if (status === 'started' || status === 'retrying_exec') logIconClass = 'fas fa-spinner fa-spin';
        else if (status === 'completed' && (!details.error_type && (!details.result || details.result.status === 'success'))) logIconClass = 'fas fa-check-circle'; // More specific success
        else if (status === 'error' || status === 'failure' || (status === 'completed' && (details.error_type || (details.result && details.result.status !== 'success')))) logIconClass = 'fas fa-times-circle';
        else if (status === 'warning') logIconClass = 'fas fa-exclamation-triangle';
        else if (status === 'ignored') logIconClass = 'fas fa-eye-slash';
        else if (status === 'retrying') logIconClass = 'fas fa-history'; // Icon for "waiting to retry"
        else if (status === 'aborted') logIconClass = 'fas fa-ban'; // Icon for aborted operations
        
        let logDescription = messageText;

        // Specific handling for tool status if present in details
        if (stage === 'action' && statusMessage.tool_status) {
            logItemClass = `log-item stage-action tool-status-${statusMessage.tool_status}`;
            if (details.result && details.result.status) { // Add status from tool result
                logItemClass += ` status-${details.result.status}`;
            }
            if (statusMessage.tool_status === 'started') logIconClass = 'fas fa-cog fa-spin';
            else if (statusMessage.tool_status === 'completed' && details.result?.status === 'success') logIconClass = 'fas fa-check';
            else if (statusMessage.tool_status === 'failure' || (statusMessage.tool_status === 'completed' && details.result?.status !== 'success')) logIconClass = 'fas fa-times';
            else if (statusMessage.tool_status === 'retrying') logIconClass = 'fas fa-history';
            else if (statusMessage.tool_status === 'retrying_exec') logIconClass = 'fas fa-spinner fa-spin';
            // logDescription is already set to messageText
        }


        if (status === 'thinking_log' && details.thinking && state.showThinkBubbles) {
            appendLogItemWithThink(messageText || `思考过程 (${stage})`, 'fas fa-brain', logItemClass, details.thinking, stage.charAt(0).toUpperCase() + stage.slice(1) + " 思考");
            return;
        }
        
        // General status messages
        if (stage === 'planning') {
            if (status === 'started') showTypingIndicator();
            else if (status === 'completed' && details.error) logItemClass += ' status-error';
            else if (status === 'error') logItemClass += ' status-error';
        } else if (stage === 'response') {
            if (status === 'started') showTypingIndicator();
        }

        // Fallback if no specific description was generated by messageText
        if (!logDescription) {
            logDescription = `阶段: ${stage}, 状态: ${status}`;
            if (details.tool_name) logDescription += `, 工具: ${details.tool_name}`;
        }

        appendLogItem(logDescription, logIconClass, logItemClass);
    }


    // 辅助函数：向日志区添加一个普通的日志项
    function appendLogItem(text, iconClass, classes = '', isSwitchingSession = false) {
        const logItemDiv = document.createElement('div');
        logItemDiv.classList.add('log-item');
        if(classes) logItemDiv.classList.add(...classes.split(' '));
        logItemDiv.innerHTML = `<i class="${iconClass}"></i><span class="log-item-text">${text}</span>`;
        dom.processLogContent.appendChild(logItemDiv);
        scrollToProcessLogBottom();
    }

    // 辅助函数：向日志区添加一个带思考过程详情的日志项
     function appendLogItemWithThink(text, iconClass, classes, thinkContent, thinkLabel) {
         const logItemDiv = document.createElement('div');
         logItemDiv.classList.add('log-item');
         if(classes) logItemDiv.classList.add(...classes.split(' '));

         logItemDiv.innerHTML = `<i class="${iconClass}"></i><span class="log-item-text">${text}</span>`;

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
                         console.warn("日志区JSON解析失败:", jsonErr);
                         formattedThink = formattedThink.replace(jsonMatch[0], `<pre><code class="language-json error">${jsonContent} (解析错误)</code></pre>`);
                     }
                }
             } catch (e) { console.error("日志区处理JSON代码块错误:", e); }

            thinkDiv.innerHTML = `<strong>${thinkLabel}:</strong> ${formattedThink}`;
            logItemDiv.appendChild(thinkDiv);
         }
         dom.processLogContent.appendChild(logItemDiv);
         scrollToProcessLogBottom();
     }

    // 辅助函数：滚动处理日志区到底部
    function scrollToProcessLogBottom(instant = false) {
         const behavior = instant || state.animationLevel === 'none' ? 'instant' : 'smooth';
         dom.processLogContainer.scrollTo({ top: dom.processLogContainer.scrollHeight, behavior });
    }

    // 函数：显示处理日志区域 (带动画)
    function showProcessLog() {
        dom.processLogContainer.style.display = 'block';
        if (state.animationLevel !== 'none' && !dom.processLogContainer.classList.contains('animate__fadeInDown')) {
             // Remove fadeOutUp before adding fadeInDown to prevent conflict if called rapidly
             dom.processLogContainer.classList.remove('animate__fadeOutUp');
             dom.processLogContainer.classList.add('animate__animated', 'animate__fadeInDown');
        }
        if (state.isProcessLogCollapsed) toggleProcessLogCollapse();
    }

    // 函数：隐藏处理日志区域 (带动画)
    function hideProcessLog() {
        if (state.animationLevel !== 'none') {
            dom.processLogContainer.classList.replace('animate__fadeInDown', 'animate__fadeOutUp') || dom.processLogContainer.classList.add('animate__animated','animate__fadeOutUp');
            dom.processLogContainer.addEventListener('animationend', () => {
                dom.processLogContainer.style.display = 'none';
                dom.processLogContainer.classList.remove('animate__animated','animate__fadeOutUp');
            }, {once: true});
        } else {
            dom.processLogContainer.style.display = 'none';
        }
         // dom.processLogContent.innerHTML = ''; // Clearing content is now handled before new log items are added
    }

    // 函数：折叠/展开处理日志区域
    function toggleProcessLogCollapse() {
        state.isProcessLogCollapsed = !state.isProcessLogCollapsed;
        dom.processLogContainer.classList.toggle('collapsed', state.isProcessLogCollapsed);
        // Update icon based on new state
        const iconElement = dom.toggleProcessLogButton.querySelector('i');
        if (iconElement) {
            iconElement.classList.toggle('fa-chevron-up', !state.isProcessLogCollapsed);
            iconElement.classList.toggle('fa-chevron-down', state.isProcessLogCollapsed);
        }
    }

    // ======== 初始化函数 ========
    async function initializeApp() {
        console.log("IDT Agent Pro 初始化开始...");
        updateLoaderProgress(10);

        loadSettings();
        loadSessions();
        updateLoaderProgress(30);

        applyTheme(state.currentTheme);
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
        applyAnimationLevel(state.animationLevel);
        updateLoaderProgress(50);

        setupEventListeners();
        updateLoaderProgress(70);

        adjustTextareaHeight();
        updateCharCounter();
        updateLoaderProgress(80);

        connectWebSocket(); // WebSocket connection will handle hiding loader
        updateLoaderProgress(95);

        // No longer hiding loader here, websocket onopen/init_success handles it
        setTimeout(() => {
             if (dom.loaderProgress) dom.loaderProgress.style.width = '100%';
        }, 200);

        console.log("IDT Agent Pro 初始化基本完成, 等待WebSocket连接确认...");
    }

    // 函数：更新加载进度条的显示
    function updateLoaderProgress(percentage) {
        if (dom.loaderProgress) {
            dom.loaderProgress.style.width = `${percentage}%`;
        }
    }

    // ======== 事件监听器设置 ========
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
            saveSettings();
            showToast(`主题已切换为: ${getThemeDisplayName(state.currentTheme)}`, 'info');
        });

        dom.clearChatButton.addEventListener('click', handleClearCurrentChat);
        dom.manageSessionsToggle.addEventListener('click', toggleSidebarExpansion);

        dom.sidebarButtons.forEach(button => {
            button.addEventListener('click', () => {
                const mode = button.dataset.mode;
                if (mode === 'settings') openSettingsModal();
                else handleModeChange(mode);
            });
        });

        dom.sessionManagerToggle.addEventListener('click', toggleSessionManagerCollapse);
        dom.createNewSessionButton.addEventListener('click', createNewSession);
        dom.editSessionNameButton.addEventListener('click', handleEditSessionName);

        dom.attachButton.addEventListener('click', () => dom.fileInput.click());
        dom.fileInput.addEventListener('change', handleFileSelection);
        dom.closeFilePreviewButton.addEventListener('click', closeFilePreview);

        dom.micButton.addEventListener('click', () => showToast('高级声纳探测模块（语音输入）正在校准中...', 'info'));

        dom.openSettingsButton.addEventListener('click', openSettingsModal);
        dom.closeSettingsButton.addEventListener('click', closeSettingsModal);
        dom.saveSettingsButton.addEventListener('click', () => {
            collectAndSaveSettings();
            closeSettingsModal();
            showToast('个性化参数已校准并保存!', 'success');
        });
        dom.resetSettingsButton.addEventListener('click', resetToDefaultSettings);
        dom.fontSizeInput.addEventListener('input', () => {
            const newSize = dom.fontSizeInput.value;
            dom.fontSizeValue.textContent = `${newSize}px`;
            if (state.animationLevel !== 'none') {
                 document.body.style.transition = 'font-size 0.1s ease-out';
            }
            document.body.style.fontSize = `${newSize}px`;
            requestAnimationFrame(() => {
                 document.body.style.transition = '';
            });
        });
        dom.settingsModal.addEventListener('click', (e) => {
            if (e.target === dom.settingsModal) closeSettingsModal();
        });
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (state.currentTheme === 'auto') applyTheme('auto');
        });
        dom.animationLevelSelect.addEventListener('change', (e) => {
            applyAnimationLevel(e.target.value);
        });

        dom.toggleProcessLogButton.parentElement.addEventListener('click', toggleProcessLogCollapse);

        dom.quickActionButtons.forEach(button => {
             button.addEventListener('click', (e) => {
                e.preventDefault();
                const messageToSend = button.dataset.message;
                if (messageToSend) {
                    dom.userInput.value = messageToSend;
                    adjustTextareaHeight();
                    updateCharCounter();
                    dom.userInput.focus();
                }
             });
        });
    }

    // 函数：更新输入框字数统计显示
    function updateCharCounter() {
        const currentLength = dom.userInput.value.length;
        dom.charCounter.textContent = `${currentLength}/${state.maxInputChars}`;
        if (currentLength > state.maxInputChars) {
            dom.charCounter.style.color = 'var(--error-color)';
        } else if (currentLength > state.maxInputChars * 0.9) {
            dom.charCounter.style.color = 'var(--warning-color)';
        } else {
            dom.charCounter.style.color = 'var(--text-muted)';
        }
    }

    // ======== 会话管理 ========
    function generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).substring(2, 12)}`;
    }

    function initializeCurrentSession(isInitialLoad = false) {
        const lastSessionId = localStorage.getItem(APP_PREFIX + 'lastSessionId');
        let targetSessionId = null;

        if (lastSessionId && state.sessions[lastSessionId]) {
            targetSessionId = lastSessionId;
        } else if (Object.keys(state.sessions).length > 0) {
            const sortedSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
            targetSessionId = sortedSessions[0].id;
        } else {
            targetSessionId = createNewSession(true);
        }

        if (targetSessionId) {
             state.currentSessionId = targetSessionId;
             if (isInitialLoad) switchSession(state.currentSessionId);
        } else {
             console.error("无法确定或创建初始会话ID。");
             dom.currentSessionNameDisplay.textContent = "错误会话";
        }
        renderSessionList();
    }

    function createNewSession(isInitial = false) {
        const newId = generateSessionId();
        const now = Date.now();
        const sessionCount = Object.keys(state.sessions).length + 1;
        state.sessions[newId] = {
            id: newId,
            name: `会话 ${sessionCount}`,
            messages: [],
            createdAt: now,
            lastActivity: now,
        };
        saveSessions();

        if (!isInitial) {
            switchSession(newId);
            showToast('新的通讯链路已建立!', 'success');
            if (!state.isSidebarExpanded) toggleSidebarExpansion();
            if (state.isSessionManagerCollapsed) toggleSessionManagerCollapse();
        }
        return newId;
    }

    function switchSession(sessionId) {
        if (state.currentSessionId === sessionId) return;
        if (!state.sessions[sessionId]) {
            console.error(`尝试切换到不存在的会话: ${sessionId}`);
            if (Object.keys(state.sessions).length > 0) {
                const sortedSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
                switchSession(sortedSessions[0].id);
            } else {
                createNewSession(true);
            }
            return;
        }
        state.currentSessionId = sessionId;
        state.sessions[sessionId].lastActivity = Date.now();
        localStorage.setItem(APP_PREFIX + 'lastSessionId', sessionId);
        saveSessions();

        dom.currentSessionNameDisplay.textContent = state.sessions[sessionId].name;
        dom.chatBox.innerHTML = '';

        state.sessions[sessionId].messages.forEach(msg => {
            appendMessage(msg.content, msg.sender, msg.isHTML, null, true);
        });
        scrollToBottom(true);
        renderSessionList();
        dom.userInput.focus();
        // Clear process log when switching sessions
        dom.processLogContent.innerHTML = ''; // Clear old logs
        if (dom.processLogContainer.style.display !== 'none' && !state.isProcessLogCollapsed) {
            // If log was visible and expanded, you might want to hide it or keep it cleared
            // For now, just clearing. User can re-open if needed for new session.
        }
        console.log(`已切换到会话: ${state.sessions[sessionId].name} (ID: ${sessionId})`);
    }

    function deleteSession(sessionId, event) {
        if (event) event.stopPropagation();
        if (!state.sessions[sessionId]) return;

        const sessionName = state.sessions[sessionId].name;
        if (!confirm(`确定要归档（删除）会话 "${sessionName}" 吗？此操作无法撤销。`)) {
            return;
        }

        const listItem = dom.sessionList.querySelector(`[data-session-id="${sessionId}"]`);
        if (listItem) {
             if (state.animationLevel !== 'none') {
                listItem.classList.add('animate__animated', 'animate__fadeOutLeft');
                listItem.addEventListener('animationend', () => listItem.remove(), {once: true});
             } else {
                listItem.remove();
             }
        }

        delete state.sessions[sessionId];

        if (state.currentSessionId === sessionId) {
            const remainingSessions = Object.keys(state.sessions);
            if (remainingSessions.length > 0) {
                const sortedSessions = Object.values(state.sessions).sort((a,b)=> b.lastActivity - a.lastActivity);
                switchSession(sortedSessions[0].id);
            } else {
                createNewSession();
            }
        }
        saveSessions();
        showToast(`会话 "${sessionName}" 已归档。`, 'info');
    }

    function handleEditSessionName() {
        const currentSession = state.sessions[state.currentSessionId];
        if (!currentSession) return;

        const newName = prompt("请输入新的会话名称：", currentSession.name);
        if (newName && newName.trim() !== "" && newName.trim() !== currentSession.name) {
            currentSession.name = newName.trim();
            currentSession.lastActivity = Date.now();
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            saveSessions();
            renderSessionList();
            showToast("会话名称已更新。", "success");
        }
    }

    function renderSessionList() {
        dom.sessionList.innerHTML = '';
        const sortedSessions = Object.values(state.sessions)
            .sort((a, b) => b.lastActivity - a.lastActivity);

        if (sortedSessions.length === 0) {
            const emptyItem = document.createElement('li');
            emptyItem.classList.add('session-list-empty');
            emptyItem.textContent = '暂无历史会话';
            dom.sessionList.appendChild(emptyItem);
            return;
        }

        sortedSessions.forEach(session => {
            const listItem = document.createElement('li');
            listItem.classList.add('session-list-item');
             if (state.animationLevel === 'full') {
                listItem.classList.add('animate__animated', 'animate__fadeInRight');
                listItem.style.setProperty('--animate-duration', '0.3s');
            }
            if (session.id === state.currentSessionId) {
                listItem.classList.add('active-session');
            }
            listItem.dataset.sessionId = session.id;
            listItem.title = `最后活动: ${new Date(session.lastActivity).toLocaleString()}\n创建于: ${new Date(session.createdAt).toLocaleString()}`;

            const nameSpan = document.createElement('span');
            nameSpan.classList.add('session-name');
            nameSpan.textContent = session.name;

            const deleteBtn = document.createElement('button');
            deleteBtn.classList.add('session-delete-btn', 'icon-btn');
            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
            deleteBtn.title = "删除此会话";
            deleteBtn.addEventListener('click', (e) => deleteSession(session.id, e));

            listItem.appendChild(nameSpan);
            listItem.appendChild(deleteBtn);
            listItem.addEventListener('click', () => switchSession(session.id));
            dom.sessionList.appendChild(listItem);
        });
    }

    function saveSessions() {
        localStorage.setItem(APP_PREFIX + 'sessions', JSON.stringify(state.sessions));
    }

    function loadSessions() {
        const storedSessions = localStorage.getItem(APP_PREFIX + 'sessions');
        if (storedSessions) {
            try {
                 state.sessions = JSON.parse(storedSessions);
                 if (typeof state.sessions !== 'object' || state.sessions === null) state.sessions = {};
                 for (const id in state.sessions) {
                    const session = state.sessions[id];
                     if (typeof session.id !== 'string' || typeof session.name !== 'string' || !Array.isArray(session.messages)) {
                         console.warn(`ID 为 ${id} 的会话数据无效，已移除。`, session);
                         delete state.sessions[id];
                     } else {
                         session.messages = session.messages.map(msg => {
                             return {
                                 content: typeof msg.content === 'string' ? msg.content : String(msg.content || ''),
                                 sender: ['user', 'agent', 'system', 'error'].includes(msg.sender) ? msg.sender : 'system',
                                 timestamp: typeof msg.timestamp === 'number' ? msg.timestamp : Date.now(),
                                 isHTML: typeof msg.isHTML === 'boolean' ? msg.isHTML : false,
                                 rawResponse: typeof msg.rawResponse === 'string' ? msg.rawResponse : (msg.sender === 'agent' ? msg.content : undefined),
                             };
                         });
                         session.createdAt = typeof session.createdAt === 'number' ? session.createdAt : Date.now();
                         session.lastActivity = typeof session.lastActivity === 'number' ? session.lastActivity : Date.now();
                     }
                 }
            } catch (e) {
                 console.error("加载或解析历史会话数据失败:", e);
                 state.sessions = {};
                 localStorage.removeItem(APP_PREFIX + 'sessions');
            }
        } else {
            state.sessions = {};
        }
    }

    function toggleSidebarExpansion() {
        state.isSidebarExpanded = !state.isSidebarExpanded;
        dom.sidebar.classList.toggle('expanded', state.isSidebarExpanded);
        if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
            toggleSessionManagerCollapse();
        }
    }

    function toggleSessionManagerCollapse() {
        if (!state.isSidebarExpanded && state.isSessionManagerCollapsed) {
            toggleSidebarExpansion();
            if(state.isSessionManagerCollapsed) {
                 state.isSessionManagerCollapsed = false;
                 dom.sessionManager.classList.remove('collapsed');
            }
            return;
        }
        if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
            state.isSessionManagerCollapsed = true;
            dom.sessionManager.classList.add('collapsed');
            return;
        }
        state.isSessionManagerCollapsed = !state.isSessionManagerCollapsed;
        dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
    }


    // ======== 核心聊天功能 (通过 WebSocket 与后端交互) ========
    async function handleSendMessage() {
        if (state.isLoading) {
            showToast("正在处理上一条消息，请稍候...", "warning");
            return;
        }
        const messageText = dom.userInput.value.trim();
        const filesToSend = [...state.uploadedFiles];

        if (messageText === '' && filesToSend.length === 0) {
            showToast("请输入消息或选择文件后再发送哦~", "warning");
            return;
        }
        if (dom.userInput.value.length > state.maxInputChars) {
            showToast(`输入内容过长，请删减至 ${state.maxInputChars} 字以内。`, "error");
            return;
        }

        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
             showToast("通讯链路未连接，正在尝试重新连接...", "warning");
             connectWebSocket();
             // Do not proceed with sending message now, wait for reconnection.
             // User can retry sending after connection is re-established.
             // dom.sendButton.disabled = true; // Temporarily disable, re-enabled on WS open or error
             return;
        }

        state.isLoading = true;
        dom.sendButton.disabled = true;
        dom.sendIcon.style.display = 'none';
        dom.sendLoadingIcon.style.display = 'inline-block';

        let userMessageDisplay = messageText;
        if (filesToSend.length > 0) {
            userMessageDisplay += `\n\n<div class="message-attachment-summary"><i class="fas fa-paperclip"></i> 附件 (${filesToSend.length}): ${filesToSend.map(f => `<span class="filename-chip">${f.name}</span>`).join(' ')}</div>`;
        }

        const currentUserMessage = {
            content: userMessageDisplay,
            sender: 'user',
            timestamp: Date.now(),
            isHTML: true,
            rawResponse: messageText,
        };
        addMessageToCurrentSession(currentUserMessage);
        appendMessage(userMessageDisplay, 'user', true);

        const currentSession = state.sessions[state.currentSessionId];
        if (currentSession && currentSession.name.startsWith("会话 ") && currentSession.messages.filter(m => m.sender === 'user').length === 1) {
            const autoName = messageText.substring(0, 25).trim() || "新对话";
            currentSession.name = autoName + (messageText.length > 25 ? "..." : "");
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            renderSessionList();
        }

        dom.userInput.value = '';
        adjustTextareaHeight();
        updateCharCounter();
        closeFilePreview();
        state.uploadedFiles = [];

        // Clear previous log content before new process starts
        dom.processLogContent.innerHTML = '';
        showProcessLog(); // Ensure log container is visible for new process

        let backendMessage = messageText;
        if (filesToSend.length > 0) {
             backendMessage += `\n[用户上传了文件: ${filesToSend.map(f => `${f.name} (${f.size} bytes)`).join(', ')}]`;
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
                 delete messageObject.rawResponse;
            }
            state.sessions[state.currentSessionId].messages.push(messageObject);
            saveSessions();
        }
    }

    function handleUserInputKeypress(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleSendMessage();
        }
    }

    function appendMessage(content, sender, isHTML = false, thinkContent = null, isSwitchingSession = false) {
        const messageDiv = document.createElement('div');
        const messageSenderClass = sender === 'user' ? 'user-message' : (sender === 'agent' ? 'agent-message' : `${sender}-message`);
        messageDiv.classList.add('message', messageSenderClass);

        if (!isSwitchingSession && state.animationLevel !== 'none') {
            const animationClass = state.animationLevel === 'full' ? 'animate__fadeInUp' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
            if (animationClass) {
                messageDiv.classList.add('animate__animated', animationClass);
                messageDiv.style.setProperty('--animate-duration', state.animationLevel === 'full' ? '0.5s' : '0.3s');
            }
        }

        const messageContentDiv = document.createElement('div');
        messageContentDiv.classList.add('message-content');

        if (isHTML) {
            messageContentDiv.insertAdjacentHTML('beforeend', content);
        } else {
            const textNodeContainer = document.createElement('div');
            const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
            const linkedContent = content.replace(/\n/g, '<br>').replace(urlRegex, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
            textNodeContainer.innerHTML = linkedContent;
            messageContentDiv.appendChild(textNodeContainer);
        }

        messageDiv.appendChild(messageContentDiv);
        dom.chatBox.appendChild(messageDiv);

        if (!isSwitchingSession) {
           scrollToBottom();
        }
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
        typingDiv.classList.add('message', 'agent-message', 'typing-indicator'); // Use agent-message for consistent styling
        if (animationClass) {
            typingDiv.classList.add('animate__animated', animationClass);
            typingDiv.style.setProperty('--animate-duration', '0.3s');
        }

        let dotsHTML = Array(3).fill('<span class="typing-dot"></span>').join('');
        typingDiv.innerHTML = `IDT Agent Pro 正在分析<span class="typing-dots">${dotsHTML}</span>`;
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
        const maxHeight = parseInt(getComputedStyle(dom.userInput).maxHeight, 10) || 200; // Ensure max-height is respected
        const minHeight = parseInt(getComputedStyle(dom.userInput).minHeight, 10) || 70; // Ensure min-height is respected

        if (scrollHeight > maxHeight) {
            dom.userInput.style.height = maxHeight + 'px';
            dom.userInput.style.overflowY = 'auto';
        } else {
            dom.userInput.style.height = Math.max(scrollHeight, minHeight) + 'px';
            dom.userInput.style.overflowY = 'hidden';
        }
    }

    // ======== UI辅助功能 ========
    function handleClearCurrentChat() {
        if (!state.currentSessionId || !state.sessions[state.currentSessionId]) return;

        if (!confirm(`确定要清空当前会话 "${state.sessions[state.currentSessionId].name}" 内的所有消息吗？`)) {
            return;
        }

        state.sessions[state.currentSessionId].messages = [];
        state.sessions[state.currentSessionId].lastActivity = Date.now();
        saveSessions();

        dom.chatBox.innerHTML = '';
        dom.processLogContent.innerHTML = '';
        // hideProcessLog(); // Hiding might be too abrupt, just clearing is fine

        const systemMessage = document.createElement('div');
        systemMessage.classList.add('message', 'system-message');
        if(state.animationLevel !== 'none') systemMessage.classList.add('animate__animated', 'animate__fadeInUp');
        systemMessage.innerHTML = `
            <div class="message-content">
                <div class="welcome-header">
                    <i class="fas fa-robot robot-icon animate__animated animate__pulse animate__infinite"></i>
                    <h2>IDT 智能助手 Pro <span class="version-tag">v8.1.0</span></h2>
                </div>
                <p>我是您的电路设计与编程高级助理！</p>
                <div class="capabilities">
                    <div class="capability"><i class="fas fa-bolt"></i><span>快速响应</span></div>
                    <div class="capability"><i class="fas fa-brain"></i><span>深度分析</span></div>
                    <div class="capability"><i class="fas fa-code-branch"></i><span>多任务处理</span></div>
                </div>
                 <div class="quick-actions">
                    <p>您好！很高兴为您服务。请问有什么可以帮助您的？您可以尝试：</p>
                    <ul>
                        <li><a href="#" class="quick-action-btn" data-message="添加一个1kΩ的电阻R1">添加电阻 R1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="添加一个3V的电池B1">添加电池 B1</a></li>
                         <li><a href="#" class="quick-action-btn" data-message="将R1和B1连接起来">连接 R1 和 B1</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="电路现在什么样？">描述电路</a></li>
                        <li><a href="#" class="quick-action-btn" data-message="清空当前电路设计">清空电路</a></li>
                         <li><a href="#" class="quick-action-btn" data-message="给我讲讲什么是RC电路">什么是RC电路？</a></li>
                    </ul>
                 </div>
            </div>
        `;
        dom.chatBox.appendChild(systemMessage);
        attachQuickActionButtonListeners(systemMessage);
        showToast('当前会话消息已清空!', 'info');
        renderSessionList();
    }

    function handleModeChange(newMode) {
        if (state.currentMode === newMode) return;
        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === newMode));
        state.currentMode = newMode;
        console.log(`模式切换为: ${newMode}`);
        showToast(`已切换到 ${getModeDisplayName(newMode)} 模式`, 'info');
        dom.userInput.placeholder = `在${getModeDisplayName(newMode)}模式下 (${state.sessions[state.currentSessionId]?.name || '当前会话'})...`;
    }

    function getModeDisplayName(mode) {
        const names = { chat: '对话', code: '编程', circuit: '电路', settings: '设置'};
        return names[mode] || '未知';
    }

    // ======== 文件上传与预览 ========
    function handleFileSelection(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        const MAX_FILES = 5, MAX_SIZE_MB = 5;

        files.forEach(file => {
            if (state.uploadedFiles.length >= MAX_FILES) {
                showToast(`最多只能上传 ${MAX_FILES} 个文件。`, 'warning'); return;
            }
            if (file.size > MAX_SIZE_MB * 1024 * 1024) {
                showToast(`文件 "${file.name}" 过大 (>${MAX_SIZE_MB}MB)。`, 'warning'); return;
            }
            if (!state.uploadedFiles.find(f => f.name === file.name && f.size === file.size)) {
                 state.uploadedFiles.push(file);
                 addFileToPreview(file);
            } else {
                 showToast(`文件 "${file.name}" 已在待上传列表中。`, 'warning');
            }
        });
        if (state.uploadedFiles.length > 0) dom.filePreviewArea.classList.add('active');
        dom.fileInput.value = '';
    }

    function addFileToPreview(file) {
        const fileItem = document.createElement('div');
        fileItem.classList.add('file-item');
        if(state.animationLevel !== 'none') fileItem.classList.add('animate__animated', 'animate__bounceIn');
        fileItem.dataset.fileName = file.name;
        fileItem.dataset.fileSize = file.size;
        fileItem.innerHTML = `<i class="fas ${getFileIconClass(file.type, file.name)} file-icon"></i><span class="file-name" title="${file.name}">${file.name}</span><button class="file-remove icon-btn" title="移除"><i class="fas fa-times-circle"></i></button>`;
        fileItem.querySelector('.file-remove').addEventListener('click', (e) => { e.stopPropagation(); removeFileFromPreview(file.name, file.size); });
        dom.filePreviewContent.appendChild(fileItem);
    }

    function getFileIconClass(fileType, fileName) {
        if (fileType.startsWith('image/')) return 'fa-file-image';
        if (fileType.startsWith('audio/')) return 'fa-file-audio';
        if (fileType.startsWith('video/')) return 'fa-file-video';
        if (fileType === 'application/pdf') return 'fa-file-pdf';
        if (fileType === 'application/zip' || fileName.endsWith('.zip') || fileName.endsWith('.rar') || fileName.endsWith('.7z')) return 'fa-file-archive';
        const codeExtensions = ['.js', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bat', '.v', '.sv', '.vhd'];
        if (codeExtensions.some(ext => fileName.toLowerCase().endsWith(ext)) || fileType.includes('text')) return 'fa-file-code';
        if (fileName.endsWith('.doc') || fileName.endsWith('.docx')) return 'fa-file-word';
        if (fileName.endsWith('.xls') || fileName.endsWith('.xlsx')) return 'fa-file-excel';
        if (fileName.endsWith('.ppt') || fileName.endsWith('.pptx')) return 'fa-file-powerpoint';
        return 'fa-file';
    }

    function removeFileFromPreview(fileName, fileSize) {
        state.uploadedFiles = state.uploadedFiles.filter(f => !(f.name === fileName && f.size === fileSize));
        const fileItemElement = dom.filePreviewContent.querySelector(`.file-item[data-file-name="${CSS.escape(fileName)}"][data-file-size="${fileSize}"]`);
        if (fileItemElement) {
            if(state.animationLevel !== 'none') {
                fileItemElement.classList.replace('animate__bounceIn', 'animate__bounceOut') || fileItemElement.classList.add('animate__bounceOut');
                fileItemElement.addEventListener('animationend', () => { fileItemElement.remove(); if (state.uploadedFiles.length === 0) closeFilePreview(); }, {once: true});
            } else {
                fileItemElement.remove(); if (state.uploadedFiles.length === 0) closeFilePreview();
            }
        }
    }
    function closeFilePreview() { dom.filePreviewArea.classList.remove('active'); }

    // ======== 主题、字体、动画级别管理 ========
    function applyTheme(themeName) {
        let newTheme = themeName;
        document.body.classList.remove('light-theme', 'dark-theme');
        dom.themeToggleIcon.classList.remove('fa-sun', 'fa-moon', 'fa-desktop');

        if (themeName === 'auto') {
            newTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            dom.themeToggleIcon.classList.add('fa-desktop');
        }

        if (newTheme === 'dark') {
            document.body.classList.add('dark-theme');
            if (themeName !== 'auto') dom.themeToggleIcon.classList.add('fa-sun');
        } else { // light
            document.body.classList.add('light-theme'); // Ensure light-theme is added by default
            if (themeName !== 'auto') dom.themeToggleIcon.classList.add('fa-moon');
        }
        state.currentTheme = themeName;
        if (dom.themeSelect.value !== themeName) dom.themeSelect.value = themeName;
        console.log(`主题已应用: ${themeName} (实际生效: ${newTheme})`);
    }
    function getThemeDisplayName(theme) { return {'light':'晨曦之光','dark':'静谧之夜','auto':'智能感知'}[theme] || '未知'; }

    function applyFontSize(size) {
        const newSize = parseInt(size, 10);
        if (isNaN(newSize) || newSize < 12 || newSize > 20) {
            document.body.style.fontSize = '16px';
            dom.fontSizeInput.value = '16'; dom.fontSizeValue.textContent = '16px'; return;
        }
        document.body.style.fontSize = `${newSize}px`;
        dom.fontSizeInput.value = newSize; dom.fontSizeValue.textContent = `${newSize}px`;
    }
    function applyAnimationLevel(level) {
        document.body.dataset.animationLevel = level;
        state.animationLevel = level;
        if (dom.animationLevelSelect.value !== level) dom.animationLevelSelect.value = level;
        console.log(`动画级别已设置为: ${level}`);
    }


    // ======== 设置模态框管理 ========
    function openSettingsModal() {
        dom.themeSelect.value = state.currentTheme;
        const currentFontSize = parseFloat(getComputedStyle(document.body).fontSize);
        dom.fontSizeInput.value = currentFontSize;
        dom.fontSizeValue.textContent = `${currentFontSize}px`;
        dom.animationLevelSelect.value = state.animationLevel;
        dom.autoScrollToggle.checked = state.autoScroll;
        dom.soundEnabledToggle.checked = state.soundEnabled;
        dom.showThinkBubblesToggle.checked = state.showThinkBubbles;

        dom.settingsModal.style.display = 'flex';
        const modalContent = dom.settingsModal.querySelector('.modal-content');
        modalContent.classList.remove('animate__fadeOutDown', 'animate__zoomOut', 'animate__fadeOut');
        const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInUp' : 'animate__fadeIn') : '';
        if (animIn) modalContent.classList.add('animate__animated', animIn);
        if (state.animationLevel !== 'none') modalContent.style.setProperty('--animate-duration', '0.4s');
    }

    function closeSettingsModal() {
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
        applyAnimationLevel(localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full');

        const modalContent = dom.settingsModal.querySelector('.modal-content');
        modalContent.classList.remove('animate__fadeInUp', 'animate__zoomIn', 'animate__fadeIn');
        const animOut = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeOutDown' : 'animate__fadeOut') : '';
        if (animOut) modalContent.classList.add('animate__animated', animOut);

        const animationEndHandler = () => {
            dom.settingsModal.style.display = 'none';
            // modalContent.removeEventListener('animationend', animationEndHandler); // Removed as addEventListener had {once: true}
        };
        if (state.animationLevel !== 'none' && animOut) {
             modalContent.addEventListener('animationend', animationEndHandler, { once: true });
        } else {
            dom.settingsModal.style.display = 'none';
        }
    }

    function collectAndSaveSettings() {
        applyTheme(dom.themeSelect.value);
        applyFontSize(dom.fontSizeInput.value);
        applyAnimationLevel(dom.animationLevelSelect.value);
        state.autoScroll = dom.autoScrollToggle.checked;
        state.soundEnabled = dom.soundEnabledToggle.checked;
        state.showThinkBubbles = dom.showThinkBubblesToggle.checked;
        saveSettings();
    }

    function saveSettings() {
        localStorage.setItem(APP_PREFIX + 'theme', state.currentTheme);
        localStorage.setItem(APP_PREFIX + 'fontSize', dom.fontSizeInput.value);
        localStorage.setItem(APP_PREFIX + 'animationLevel', state.animationLevel);
        localStorage.setItem(APP_PREFIX + 'autoScroll', state.autoScroll.toString());
        localStorage.setItem(APP_PREFIX + 'soundEnabled', state.soundEnabled.toString());
        localStorage.setItem(APP_PREFIX + 'showThinkBubbles', state.showThinkBubbles.toString());
        console.log("设置已保存到 localStorage");
    }

    function loadSettings() {
        state.currentTheme = localStorage.getItem(APP_PREFIX + 'theme') || 'auto';
        const savedFontSize = localStorage.getItem(APP_PREFIX + 'fontSize') || '16';
        dom.fontSizeInput.value = savedFontSize; dom.fontSizeValue.textContent = `${savedFontSize}px`;
        state.animationLevel = localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full';
        dom.animationLevelSelect.value = state.animationLevel;
        state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || 'true') === 'true';
        state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || 'false') === 'true';
        state.showThinkBubbles = (localStorage.getItem(APP_PREFIX + 'showThinkBubbles') || 'true') === 'true';
        dom.autoScrollToggle.checked = state.autoScroll;
        dom.soundEnabledToggle.checked = state.soundEnabled;
        dom.showThinkBubblesToggle.checked = state.showThinkBubbles;
    }

    function resetToDefaultSettings() {
        const defaults = { theme: 'auto', fontSize: '16', animationLevel: 'full', autoScroll: true, soundEnabled: false, showThinkBubbles: true };
        applyTheme(defaults.theme); applyFontSize(defaults.fontSize); applyAnimationLevel(defaults.animationLevel);
        state.autoScroll = defaults.autoScroll; state.soundEnabled = defaults.soundEnabled; state.showThinkBubbles = defaults.showThinkBubbles;
        dom.themeSelect.value = defaults.theme;
        dom.fontSizeInput.value = defaults.fontSize; dom.fontSizeValue.textContent = `${defaults.fontSize}px`;
        dom.animationLevelSelect.value = defaults.animationLevel;
        dom.autoScrollToggle.checked = defaults.autoScroll;
        dom.soundEnabledToggle.checked = defaults.soundEnabled;
        dom.showThinkBubblesToggle.checked = defaults.showThinkBubbles;
        saveSettings();
        showToast('所有参数已重置为出厂设定!', 'success');
    }

    // ======== Toast 通知 ========
    function showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.classList.add('toast', type);
        const animIn = state.animationLevel === 'full' ? 'animate__fadeInRight' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
        const animOut = state.animationLevel === 'full' ? 'animate__fadeOutRight' : (state.animationLevel === 'basic' ? 'animate__fadeOut' : '');
        if (state.animationLevel !== 'none' && animIn) toast.classList.add('animate__animated', animIn);

        let iconClass = {'info':'fa-info-circle', 'success':'fa-check-circle', 'warning':'fa-exclamation-triangle', 'error':'fa-times-circle'}[type] || 'fa-info-circle';
        toast.innerHTML = `<i class="fas ${iconClass} toast-icon"></i><span class="toast-message">${message}</span><button class="toast-close icon-btn"><i class="fas fa-times"></i></button>`;
        toast.querySelector('.toast-close').addEventListener('click', () => removeToast(toast, animOut));
        dom.toastContainer.appendChild(toast);
        if (state.animationLevel !== 'none') toast.style.setProperty('--animate-duration', '0.4s');

        setTimeout(() => removeToast(toast, animOut), duration);
    }
    function removeToast(toast, animOut) {
        if (toast.parentElement) {
            if (state.animationLevel !== 'none' && animOut) {
                toast.classList.remove(toast.classList.contains('animate__fadeInRight') ? 'animate__fadeInRight' : 'animate__fadeIn');
                toast.classList.add(animOut);
                toast.addEventListener('animationend', () => toast.remove(), {once: true});
            } else {
                toast.remove();
            }
        }
    }

    // ======== 欢迎消息中的快速操作按钮事件 ========
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

    // ======== 启动应用 ========
    initializeApp();
    attachQuickActionButtonListeners(dom.chatBox);
});