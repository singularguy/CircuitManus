// 当整个 HTML 文档加载完成并解析完毕后执行回调函数
document.addEventListener('DOMContentLoaded', () => {
    // ======== DOM 元素获取 (集中管理，方便维护) ========
    // 定义一个 dom 对象，用于存储所有获取到的 DOM 元素，方便统一管理和后续引用。
    const dom = {
        // 动态背景相关
        dynamicBackground: document.querySelector('.dynamic-crystal-background'), // 获取类名为 'dynamic-crystal-background' 的元素，用作动态背景容器。类名保持，效果由CSS内部调整

        // 加载动画相关
        loader: document.getElementById('loader'), // 获取 ID 为 'loader' 的元素，用作加载动画的容器。
        loaderCore: document.querySelector('.lumina-loader-core'), // 获取类名为 'lumina-loader-core' 的元素，这是新的加载动画核心部分。
        mainContainer: document.getElementById('main-container'), // 获取 ID 为 'main-container' 的元素，这是应用的主内容区域容器。
        appBodyContainer: document.getElementById('appBodyContainer'), // 获取 ID 为 'appBodyContainer' 的元素，这是应用主体内容的容器，用于布局调整。

        // 聊天核心区域
        chatArea: document.getElementById('chat-area'), // 获取 ID 为 'chat-area' 的元素，包含聊天框和输入区域。
        chatBox: document.getElementById('chat-box'), // 获取 ID 为 'chat-box' 的元素，用于显示聊天消息。
        userInput: document.getElementById('user-input'), // 获取 ID 为 'user-input' 的元素，用户输入消息的文本框。
        sendButton: document.getElementById('send-button'), // 获取 ID 为 'send-button' 的元素，发送消息的按钮。ID保持，但其 class 会在HTML中更新
        sendIcon: document.querySelector('.send-icon'), // 获取类名为 'send-icon' 的元素，发送按钮上的默认图标。
        sendLoadingIcon: document.querySelector('.send-loading-icon'), // 获取类名为 'send-loading-icon' 的元素，发送按钮上表示加载中的图标。

        // 头部与主题
        appHeader: document.getElementById('app-header'), // 获取 ID 为 'app-header' 的元素，应用的头部区域。
        themeToggleButton: document.getElementById('theme-toggle'), // 获取 ID 为 'theme-toggle' 的元素，切换主题的按钮。
        themeToggleIcon: document.querySelector('#theme-toggle i'), // 获取 ID 为 'theme-toggle' 按钮内的 <i> 图标元素。选择器不变
        clearChatButton: document.getElementById('clear-chat'), // 获取 ID 为 'clear-chat' 的元素，清除当前聊天记录的按钮。
        leftSidebarToggle: document.getElementById('left-sidebar-toggle'), // 获取 ID 为 'left-sidebar-toggle' 的元素，切换左侧边栏显示/隐藏的按钮。
        toggleProcessLogVisibilityButton: document.getElementById('toggle-process-log-visibility'), // 获取 ID 为 'toggle-process-log-visibility' 的元素，用于切换右侧处理过程日志侧边栏的可见性。

        // 侧边栏与会话管理 (左侧边栏)
        sidebar: document.getElementById('sidebar'), // 获取 ID 为 'sidebar' 的元素，左侧边栏容器。
        sidebarButtons: document.querySelectorAll('.sidebar-button'), // 获取所有类名为 'sidebar-button' 的元素，用于模式切换等。class 会在HTML中更新
        sessionManager: document.getElementById('session-manager'), // 获取 ID 为 'session-manager' 的元素，会话管理器区域。
        sessionManagerToggle: document.getElementById('session-manager-toggle'), // 获取 ID 为 'session-manager-toggle' 的元素，展开/折叠会话列表的按钮。
        sessionListContainer: document.getElementById('session-list-container'), // 获取 ID 为 'session-list-container' 的元素，会话列表的容器。
        sessionList: document.getElementById('session-list'), // 获取 ID 为 'session-list' 的元素 (ul)，用于显示会话列表项。
        createNewSessionButton: document.getElementById('create-new-session'), // 获取 ID 为 'create-new-session' 的元素，创建新会话的按钮。ID保持，class 会更新
        currentSessionNameDisplay: document.getElementById('current-session-name'), // 获取 ID 为 'current-session-name' 的元素，显示当前会话名称。
        editSessionNameButton: document.getElementById('edit-session-name-btn'), // 获取 ID 为 'edit-session-name-btn' 的元素，编辑当前会话名称的按钮。ID保持，class 会更新

        // 输入区域与文件上传
        inputArea: document.getElementById('input-area'), // 获取 ID 为 'input-area' 的元素，整个输入区域的容器。
        attachButton: document.getElementById('attach-button'), // 获取 ID 为 'attach-button' 的元素，附加文件按钮。ID保持，class 会更新
        micButton: document.getElementById('mic-button'), // 获取 ID 为 'mic-button' 的元素，麦克风/语音输入按钮。ID保持，class 会更新
        charCounter: document.getElementById('char-counter'), // 获取 ID 为 'char-counter' 的元素，显示用户输入字符数。
        fileInput: document.getElementById('file-input'), // 获取 ID 为 'file-input' 的元素 (type="file")，用于选择文件。
        filePreviewArea: document.getElementById('file-preview'), // 获取 ID 为 'file-preview' 的元素，显示已选择文件预览的区域。
        filePreviewContent: document.getElementById('file-preview-content'), // 获取 ID 为 'file-preview-content' 的元素，文件预览项的具体容器。
        closeFilePreviewButton: document.getElementById('close-preview'), // 获取 ID 为 'close-preview' 的元素，关闭文件预览区域的按钮。ID保持，class 会更新

        // Toast 通知
        toastContainer: document.getElementById('toast-container'), // 获取 ID 为 'toast-container' 的元素，显示 Toast 通知的容器。

        // Agent 处理过程日志区域 (右侧悬浮侧栏)
        processLogSidebarContainer: document.getElementById('agent-process-sidebar'), // 获取 ID 为 'agent-process-sidebar' 的元素，右侧Agent处理过程日志侧边栏的容器。
        processLogSidebarHeader: document.querySelector('#agent-process-sidebar .process-log-header'), // 获取右侧日志侧边栏内的头部元素。
        processLogSidebarContent: document.getElementById('process-log-content-sidebar'), // 获取 ID 为 'process-log-content-sidebar' 的元素，用于显示日志条目。
        toggleProcessLogSidebarCollapseButton: document.getElementById('toggle-process-log-sidebar-collapse'), // 获取 ID 为 'toggle-process-log-sidebar-collapse' 的元素，折叠/展开右侧日志侧边栏的按钮。ID保持
        closeProcessLogSidebarButton: document.getElementById('close-process-log-sidebar'), // 获取 ID 为 'close-process-log-sidebar' 的元素，关闭右侧日志侧边栏的按钮。ID保持

        // 设置模态框相关
        settingsModal: document.getElementById('settings-modal'), // 获取 ID 为 'settings-modal' 的元素，设置模态框。
        openSettingsButton: document.querySelector('.sidebar-button[data-mode="settings"]'), // 获取侧边栏中用于打开设置的按钮。
        closeSettingsButton: document.getElementById('close-settings'), // 获取 ID 为 'close-settings' 的元素，关闭设置模态框的按钮。ID保持
        themeSelect: document.getElementById('theme-select'), // 获取 ID 为 'theme-select' 的元素 (select)，选择主题。class 会更新
        fontSizeInput: document.getElementById('font-size'), // 获取 ID 为 'font-size' 的元素 (input type="range")，调整字体大小。class 会更新
        fontSizeValue: document.getElementById('font-size-value'), // 获取 ID 为 'font-size-value' 的元素，显示当前字体大小值。
        animationLevelSelect: document.getElementById('animation-level'), // 获取 ID 为 'animation-level' 的元素 (select)，选择动画级别。class 会更新
        autoScrollToggle: document.getElementById('auto-scroll'), // 获取 ID 为 'auto-scroll' 的元素 (input type="checkbox")，切换自动滚动。class 会更新
        soundEnabledToggle: document.getElementById('sound-enabled'), // 获取 ID 为 'sound-enabled' 的元素 (input type="checkbox")，切换声音提示。class 会更新
        showChatBubblesThinkToggle: document.getElementById('show-chat-bubbles-think'), // 获取 ID 为 'show-chat-bubbles-think' 的元素 (checkbox)，切换是否在聊天气泡中显示思考过程。class 会更新
        showLogBubblesThinkToggle: document.getElementById('show-log-bubbles-think'), // 获取 ID 为 'show-log-bubbles-think' 的元素 (checkbox)，切换是否在日志条目中显示思考气泡。class 会更新
        autoSubmitQuickActionsToggle: document.getElementById('auto-submit-quick-actions'), // 获取 ID 为 'auto-submit-quick-actions' 的元素 (checkbox), 切换快捷操作是否自动提交。class 会更新
        componentVisibilityToggle: document.getElementById('component-visibility-toggle'), // 获取 ID 为 'component-visibility-toggle' 的元素 (checkbox), 用于切换3D组件的显示。class 会更新
        resetSettingsButton: document.getElementById('reset-settings'), // 获取 ID 为 'reset-settings' 的元素，重置所有设置的按钮。ID保持
        saveSettingsButton: document.getElementById('save-settings'), // 获取 ID 为 'save-settings' 的元素，保存设置的按钮。ID保持

        // 3D组件显示开关与包装器
        idtComponentToggleBtn: document.getElementById('toggleIdtComponentBtn'), // 获取 ID 为 'toggleIdtComponentBtn' 的元素，用于切换3D组件（黑洞特效）的按钮。ID保持
        idtComponentWrapper: document.getElementById('idtTechComponentWrapper') // 获取 ID 为 'idtTechComponentWrapper' 的元素，3D组件（黑洞特效）的容器。ID保持
    };

    // ======== 应用状态与配置 ========
    // 定义应用的前缀，用于 localStorage 存储，以区分旧版或其他应用设置。
    const APP_PREFIX = 'CircuitManusPro_LuminaScript_'; // 更新应用前缀以区分旧设置
    // 定义一个 state 对象，用于存储应用的运行时状态和用户配置。
    let state = {
        sessions: {}, // 存储所有会话数据，以会话ID为键。
        currentSessionId: null, // 当前活动的会话ID。
        currentTheme: 'auto-crystal', // 当前主题设置 ('auto-crystal', 'light-crystal', 'dark-crystal')。初始值保持，applyTheme会处理
        autoScroll: true, // 是否自动滚动聊天框到底部。
        soundEnabled: false, // 是否启用声音提示。
        showChatBubblesThink: true, // 是否在聊天气泡中显示Agent的思考过程。
        showLogBubblesThink: true, // 是否在日志条目中显示Agent的思考过程。
        animationLevel: 'full', // 动画效果级别 ('full', 'basic', 'none')。
        currentMode: 'chat', // 当前应用模式 (如 'chat', 'code', 'circuit')。
        uploadedFiles: [], // 当前已选择待上传的文件列表。
        isAgentTyping: false, // Agent是否正在输入（用于显示打字指示器）。
        isLoading: false, // 应用是否处于加载状态（例如，等待Agent回复）。
        isSidebarExpanded: window.innerWidth > 1024, // 左侧边栏是否展开，默认为展开如果屏幕宽度大于1024px。
        isSessionManagerCollapsed: false, // 会话管理器（在左侧边栏内）是否折叠。
        isProcessLogSidebarVisible: false, // 右侧Agent处理过程日志侧边栏是否可见。
        isProcessLogSidebarCollapsed: true, // 右侧Agent处理过程日志侧边栏是否折叠。
        maxInputChars: 8000, // 用户输入框的最大字符数限制。
        currentClientRequestId: null, // 当前发送给后端的请求ID，用于追踪响应。
        lastResponseThinking: null, // 最近一次Agent响应中包含的思考过程内容。
        autoSubmitQuickActions: true, // 点击快捷操作按钮后是否自动发送消息。
        isIdtComponentVisible: true, // 3D技术组件（如黑洞特效）是否可见。
        isDraggingComponent: false, // 3D组件是否正在被拖拽。
        componentDragStartX: 0, // 3D组件拖拽开始时的鼠标X坐标。
        componentDragStartY: 0, // 3D组件拖拽开始时的鼠标Y坐标。
        componentInitialTopPx: 0, // 3D组件拖拽开始时的初始顶部位置 (px)。
        componentInitialLeftPx: 0, // 3D组件拖拽开始时的初始左侧位置 (px)。
        threeJsScene: null, // Three.js 场景对象。
        threeJsRenderer: null, // Three.js 渲染器对象。
        threeJsCamera: null, // Three.js 相机对象。
        threeJsAnimationId: null, // Three.js 动画循环的ID (用于取消动画)。
        threeJsInitialized: false, // Three.js 特效是否已初始化。
        threeBlackHoleGroup: null, // Three.js 黑洞对象的组合。
        threeAccretionDiskOuter: null, // Three.js 吸积盘 (外层)。
        threeAccretionDiskMiddle: null, // Three.js 吸积盘 (中层)。
        threeAccretionDiskInner: null, // Three.js 吸积盘 (内层)。
        threeStarField: null // Three.js 星空背景。
    };

    // ======== WebSocket 相关 ========
    let websocket = null; // WebSocket 连接实例。
    const websocketUrl = `ws://${window.location.host}/ws/chat`; // WebSocket 服务器的URL。
    let wsReconnectAttempts = 0; // 当前 WebSocket 重连尝试次数。
    const MAX_WS_RECONNECT_ATTEMPTS = 3; // 最大 WebSocket 重连尝试次数。
    const WS_RECONNECT_INTERVAL = 3000; // WebSocket 重连间隔时间 (毫秒)。

    /**
     * 连接WebSocket服务器。
     * 包含重连逻辑和加载状态更新。
     * 此函数负责建立与后端WebSocket的连接，并在连接成功、失败或关闭时执行相应操作。
     */
    function connectWebSocket() {
        // 如果 WebSocket 已经连接或正在连接，则不执行任何操作
        if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
            console.log("WebSocket: Connection established.", event); // 在控制台打印已连接或正在连接的信息
            return; // 退出函数
        }
        // 在控制台打印连接尝试信息
        console.log(`WebSocket: Attempting connection (Attempt ${wsReconnectAttempts + 1}) to ${websocketUrl}`);
        // 如果加载动画元素存在，并且是第一次尝试连接，并且没有显示致命错误
        if (dom.loader && wsReconnectAttempts === 0 && !dom.loader.classList.contains('loader-fatal-error')) {
            const loadingText = dom.loader.querySelector('.loading-text'); // 获取加载文本元素
            if (loadingText) loadingText.textContent = "同步光绘墨迹流 (V1.0.0 Lumina)..."; // 更新加载文本，版本号同步
        }

        websocket = new WebSocket(websocketUrl); // 创建新的 WebSocket 实例

        // WebSocket 连接成功打开时的回调函数
        websocket.onopen = (event) => {
            console.log("WebSocket: Connection established.", event); // 在控制台打印连接成功信息
            wsReconnectAttempts = 0; // 重置重连尝试次数
            showToast("光绘墨迹数据流 ACTIVE (V1.0.0 Lumina).", "success", 4000); // 显示连接成功的 Toast 通知，版本号同步
            // 发送初始化消息到 WebSocket 服务器
            sendWebSocketMessage({
                type: 'init', // 消息类型为 'init'
                session_id: state.currentSessionId // 包含当前会话 ID
            });
            // 如果加载动画元素存在且未显示致命错误，则隐藏加载动画
            if (dom.loader && !dom.loader.classList.contains('loader-fatal-error')) dom.loader.classList.add('hidden');
            // 如果主容器元素存在，则添加 'loaded' 类，表示内容已加载
            if (dom.mainContainer) dom.mainContainer.classList.add('loaded');
        };

        // WebSocket 收到消息时的回调函数
        websocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data); // 解析收到的 JSON 格式消息
                console.log("WS RX:", message); // 在控制台打印收到的消息
                handleWebSocketMessage(message); // 调用消息处理函数
            } catch (e) {
                console.error("WebSocket: Failed to parse message.", e, "Raw data:", event.data); // 在控制台打印解析失败的错误信息和原始数据
                showToast("收到损坏的数据包流 (JSON解析失败).", "error"); // 显示解析失败的 Toast 通知
            }
        };

        // WebSocket 发生错误时的回调函数
        websocket.onerror = (event) => {
            console.error("WebSocket: Error occurred.", event); // 在控制台打印错误信息
        };

        // WebSocket 连接关闭时的回调函数
        websocket.onclose = (event) => {
            console.log("WebSocket: Connection closed.", event); // 在控制台打印连接关闭信息
            hideTypingIndicator(); // 隐藏打字指示器
            setLoadingState(false); // 设置加载状态为 false
            websocket = null; // 将 WebSocket 实例置为 null

            // 获取关闭原因和代码
            const reason = event.reason ? `Reason: ${event.reason}` : (event.wasClean ? '连接正常关闭.' : '连接异常断开.');
            const codeMsg = `(Code: ${event.code})`;

            // 如果连接不是正常关闭且重连次数未达到上限
            if (!event.wasClean && wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                wsReconnectAttempts++; // 增加重连尝试次数
                showToast(`墨迹数据链接不稳定. 尝试重新校准 (${wsReconnectAttempts}/${MAX_WS_RECONNECT_ATTEMPTS})... ${codeMsg}`, "warning", WS_RECONNECT_INTERVAL + 500); // 显示重连尝试的 Toast 通知
                setTimeout(connectWebSocket, WS_RECONNECT_INTERVAL); // 延迟指定时间后尝试重连
            } else if (!event.wasClean) { // 如果连接不是正常关闭且已达到最大重连次数
                // 隐藏主容器
                if (dom.mainContainer) {
                    dom.mainContainer.style.display = 'none';
                }
                // 清空 Toast 通知容器
                if (dom.toastContainer) {
                    dom.toastContainer.innerHTML = '';
                }

                // 如果加载动画元素存在
                if (dom.loader) {
                    dom.loader.classList.add('loader-fatal-error'); // 添加致命错误类
                    dom.loader.classList.remove('hidden'); // 移除隐藏类，显示加载动画
                    dom.loader.innerHTML = ''; // 清空加载动画原有内容

                    // 创建致命错误状态下的加载核心元素
                    const fatalErrorCore = document.createElement('div');
                    fatalErrorCore.className = 'lumina-loader-core error-state'; // 设置类名
                    fatalErrorCore.innerHTML = `<div class="lumina-loader-center-pulse"></div>`; // 设置内部 HTML

                    // 创建致命错误状态下的 Logo 文本元素
                    const fatalErrorLogo = document.createElement('div');
                    fatalErrorLogo.className = 'loader-logo-text'; // 设置类名
                    fatalErrorLogo.innerHTML = `<span>CIRCUIT</span>MANUS<span class="loader-version-pro">PRO</span> - 链接故障`; // 设置内部 HTML

                    // 创建致命错误标题元素
                    const fatalErrorHeading = document.createElement('p');
                    fatalErrorHeading.className = 'loading-text'; // 设置类名
                    fatalErrorHeading.textContent = "通信链接已断开且无法恢复"; // 设置文本内容

                    // 创建致命错误详情文本元素
                    const fatalErrorDetails = document.createElement('p');
                    fatalErrorDetails.className = 'error-details-text'; // 设置类名
                    fatalErrorDetails.textContent = `与后端核心的连接已彻底中断 (${MAX_WS_RECONNECT_ATTEMPTS} 次校准尝试失败)。请检查您的网络连接或服务器状态。${codeMsg} ${reason}`; // 设置文本内容

                    // 创建刷新页面按钮
                    const refreshButton = document.createElement('button');
                    refreshButton.id = 'refresh-page-button'; // 设置 ID
                    refreshButton.className = 'lumina-button lumina-button-primary refresh-button'; // 设置类名
                    refreshButton.innerHTML = '<i class="fas fa-sync-alt"></i> 刷新页面'; // 设置内部 HTML (图标和文本)
                    refreshButton.onclick = () => window.location.reload(); // 点击时刷新页面

                    // 将创建的元素添加到加载动画容器中
                    dom.loader.appendChild(fatalErrorCore);
                    dom.loader.appendChild(fatalErrorLogo);
                    dom.loader.appendChild(fatalErrorHeading);
                    dom.loader.appendChild(fatalErrorDetails);
                    dom.loader.appendChild(refreshButton);
                }
            } else { // 如果连接是正常关闭的
                showToast(`通信链接已终止. ${codeMsg} ${reason}`, "info", 6000); // 显示连接终止的 Toast 通知
            }
        };
    }

    /**
     * 通过WebSocket发送消息到服务器。
     * @param {object} message - 要发送的消息对象。
     * 此函数负责将前端构造的消息对象序列化为JSON字符串，并通过已建立的WebSocket连接发送。
     * 如果连接未打开，则会尝试重新连接或提示用户。
     */
    function sendWebSocketMessage(message) {
        // 检查 WebSocket 是否存在并且连接状态为 OPEN
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            const messageStr = JSON.stringify(message); // 将消息对象转换为 JSON 字符串
            console.log("WS TX:", message); // 在控制台记录发送的消息对象
            websocket.send(messageStr); // 通过 WebSocket 发送消息字符串
        } else {
            // 如果 WebSocket 连接未打开，则记录错误信息
            console.error("WebSocket: Connection not open. Cannot send message:", message);
            showToast("通信链接不活跃. 尝试重新建立链接...", "warning"); // 显示警告 Toast 通知
            // 检查 WebSocket 是否不存在，或连接状态为 CLOSED 或 CLOSING
            if (!websocket || websocket.readyState === WebSocket.CLOSED || websocket.readyState === WebSocket.CLOSING) {
                // 如果重连尝试次数未达到最大限制
                if (wsReconnectAttempts < MAX_WS_RECONNECT_ATTEMPTS) {
                    connectWebSocket(); // 尝试重新连接 WebSocket
                } else {
                    // 如果已达到最大重连尝试次数，显示错误 Toast 通知
                    showToast("无法发送: 达到最大重连尝试次数. 请刷新页面.", "error");
                }
            }
        }
    }

    /**
     * 处理从WebSocket接收到的消息。
     * 根据消息类型分发到不同的处理函数。
     * @param {object} message - 从服务器接收到的已解析的JSON消息。
     * 这是WebSocket消息处理的核心分发器。
     */
    function handleWebSocketMessage(message) {
        try {
            // 根据消息类型进行分发处理
            switch (message.type) {
                case 'init_success': // 初始化成功消息
                    try {
                        // 设置当前会话 ID
                        state.currentSessionId = message.session_id;
                        // 将最后会话 ID 存储到 localStorage
                        localStorage.setItem(APP_PREFIX + 'lastSessionId', state.currentSessionId);

                        // 根据 Agent 可用状态设置提示消息和类型
                        const agentStatusMessage = message.agent_available === false
                            ? 'Lumina AI核心 OFFLINE. 功能受限. (V1.0.0 Lumina)' // Agent 不可用时的消息，版本号同步
                            : 'Lumina核心 (V1.0.0 Lumina) 已同步到光绘网络!'; // Agent 可用时的消息，版本号同步
                        const agentStatusType = message.agent_available === false ? 'warning' : 'success'; // Agent 不可用时为警告，可用时为成功
                        // 显示 Toast 通知
                        showToast(agentStatusMessage, agentStatusType, message.agent_available ? 4500 : 8000);

                        // 如果当前会话 ID 在会话列表中不存在，则创建新会话
                        if (!state.sessions[state.currentSessionId]) {
                            const now = Date.now(); // 获取当前时间戳
                            // 创建新的会话对象
                            state.sessions[state.currentSessionId] = {
                                id: state.currentSessionId, // 会话 ID
                                name: `光绘墨迹项目 ${Object.keys(state.sessions).length + 1}`, // 会话名称，包含序号
                                messages: [], // 消息列表，初始为空
                                createdAt: now, // 创建时间
                                lastActivity: now, // 最后活动时间
                            };
                            saveSessions(); // 保存会话数据
                        }
                        initializeCurrentSessionUI(true); // 初始化当前会话的 UI，标记为初始加载
                    } catch (e) {
                        // 捕获处理 init_success 时的错误
                        console.error(`Error handling init_success:`, e, message);
                        showToast(`处理初始化成功消息时出错: ${e.message}`, 'error');
                    }
                    break;

                case 'init_error': // 初始化错误消息
                    try {
                        // 显示初始化失败的 Toast 通知
                        showToast(`AI核心同步失败: ${message.message}`, 'error', 10000);
                        // 如果加载动画存在且未显示致命错误，则隐藏加载动画
                        if (dom.loader && !dom.loader.classList.contains('loader-fatal-error')) dom.loader.classList.add('hidden');
                        // 如果主容器存在，则添加 'loaded' 类
                        if (dom.mainContainer) dom.mainContainer.classList.add('loaded');
                        // 如果 Agent 不可用
                        if (message.agent_available === false) {
                            // 在聊天框追加系统错误消息
                            appendMessage("CRITICAL SYSTEM ALERT: Lumina AI核心未能初始化. 子系统无响应. (V1.0.0 Lumina)", 'error-system', false, null, false, [], "System Error"); // 版本号同步
                        }
                        setLoadingState(false); // 设置加载状态为 false
                    } catch (e) {
                        // 捕获处理 init_error 时的错误
                        console.error(`Error handling init_error:`, e, message);
                        showToast(`处理初始化错误消息时出错: ${e.message}`, 'error');
                    }
                    break;

                case 'error': // 通用错误消息
                    try {
                        // 在控制台记录服务器报告的错误
                        console.error("Server-reported error:", message);
                        // 显示服务器异常的 Toast 通知
                        showToast(`服务器异常: ${message.message}`, 'error', 7000);
                        // 如果错误消息包含详细信息
                        if (message.details) {
                            // 在聊天框追加服务器错误消息
                            appendMessage(`SERVER ERROR (${message.message}): ${message.details}`, 'error-system', false, null, false, [], "Server Error");
                        }
                        setLoadingState(false); // 设置加载状态为 false
                    } catch (e) {
                        // 捕获处理服务器 'error' 消息时的错误
                        console.error(`Error handling server 'error' message:`, e, message);
                        showToast(`处理服务器错误报告时出错: ${e.message}`, 'error');
                    }
                    break;

                case 'general_status': handleGeneralStatus(message); break; // 处理通用状态消息
                case 'llm_communication_status': handleLlmCommStatus(message); break; // 处理 LLM 通信状态消息
                case 'thinking_log': handleThinkingLog(message); break; // 处理思考日志消息
                case 'plan_details': handlePlanDetails(message); break; // 处理计划详情消息
                case 'tool_status_update': handleToolStatusUpdate(message); break; // 处理工具状态更新消息
                case 'interim_response': handleInterimResponse(message); break; // 处理临时响应消息
                case 'final_response': // 处理最终响应消息
                    try {
                        handleFinalResponse(message); // 调用最终响应处理函数
                    } catch (e_final_resp) {
                        // 捕获处理 final_response 时的错误
                        console.error(`Error handling final_response:`, e_final_resp, message);
                        showToast(`处理最终响应时发生内部错误: ${e_final_resp.message}`, 'error');
                        hideTypingIndicator(); // 隐藏打字指示器
                        setLoadingState(false); // 设置加载状态为 false
                    }
                    break;

                default: // 未知消息类型
                    console.warn("收到未知数据包类型:", message.type, message); // 在控制台记录未知消息类型
                    showToast(`未知数据包类型: ${message.type}`, 'warning'); // 显示未知消息类型的 Toast 通知
            }
        } catch (e_outer_switch) {
            // 捕获 handleWebSocketMessage switch 逻辑中的严重错误
            console.error("Critical error in handleWebSocketMessage switch logic.", e_outer_switch, "Original message:", message);
            showToast("处理服务器消息时发生严重内部错误。", "error"); // 显示严重内部错误的 Toast 通知
            hideTypingIndicator(); // 隐藏打字指示器
            setLoadingState(false); // 设置加载状态为 false
        }
    }

    // ======== 辅助函数定义区 ========

    /**
     * 获取当前模式的显示名称。
     * @param {string} mode - 模式的内部标识符 (如 'chat', 'code')。
     * @returns {string} 对应模式的用户友好显示名称。
     */
    function getModeDisplayName(mode) {
        // 定义一个对象，存储模式标识符和对应的显示名称
        const names = { chat: '灵感交流', code: '代码绘卷', circuit: '电路拓印', settings: '参数调校' };
        // 返回对应模式的显示名称，如果找不到则返回 '未知领域'
        return names[mode] || '未知领域';
    }

    /**
     * 应用右侧固定日志侧边栏的布局。
     * 根据侧边栏的可见性和折叠状态，调整聊天区域的右边距和侧边栏的宽度。
     */
    function applyFixedLogSidebarLayout() {
        // 检查右侧日志侧边栏容器和聊天区域是否存在，如果不存在则直接返回
        if (!dom.processLogSidebarContainer || !dom.chatArea) return;
        // 从CSS变量获取日志侧边栏的固定宽度，并转换为数字，默认值为350
        const logSidebarFixedWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--process-log-sidebar-width').replace('px', '')) || 350;
        // 从CSS变量获取日志侧边栏折叠后的宽度，并转换为数字，默认值为55
        const logSidebarCollapsedWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--process-log-sidebar-width-collapsed').replace('px', '')) || 55;

        // 如果右侧日志侧边栏可见
        if (state.isProcessLogSidebarVisible) {
            // 如果右侧日志侧边栏已折叠
            if (state.isProcessLogSidebarCollapsed) {
                // 设置聊天区域的右边距为折叠后的侧边栏宽度加上原有的右内边距
                dom.chatArea.style.marginRight = `${logSidebarCollapsedWidth + parseInt(getComputedStyle(dom.chatArea).paddingRight || '0', 10)}px`;
                // 设置右侧日志侧边栏容器的宽度为折叠后的宽度
                dom.processLogSidebarContainer.style.width = `${logSidebarCollapsedWidth}px`;
                 // 隐藏关闭按钮，显示折叠按钮
                 dom.closeProcessLogSidebarButton.style.display = 'none';
                 dom.toggleProcessLogSidebarCollapseButton.style.display = 'flex'; // Ensure it's visible
            } else { // 如果右侧日志侧边栏未折叠
                // 设置聊天区域的右边距为固定宽度的侧边栏宽度加上原有的右内边距
                dom.chatArea.style.marginRight = `${logSidebarFixedWidth + parseInt(getComputedStyle(dom.chatArea).paddingRight || '0', 10)}px`;
                // 设置右侧日志侧边栏容器的宽度为固定宽度
                dom.processLogSidebarContainer.style.width = `${logSidebarFixedWidth}px`;
                 // 显示关闭按钮，确保折叠按钮也是可见的
                 dom.closeProcessLogSidebarButton.style.display = 'flex';
                 dom.toggleProcessLogSidebarCollapseButton.style.display = 'flex';
            }
        } else { // 如果右侧日志侧边栏不可见
            // 清除聊天区域的右边距设置，恢复默认
            dom.chatArea.style.marginRight = '';
            // 隐藏关闭按钮，确保折叠按钮可见 (虽然侧边栏不可见，但按钮仍然可能在UI中)
            dom.closeProcessLogSidebarButton.style.display = 'none';
            dom.toggleProcessLogSidebarCollapseButton.style.display = 'flex';
        }
    }

    /**
     * 更新右侧日志侧边栏的折叠/展开状态。
     * @param {boolean} collapse - 是否折叠侧边栏。
     * @param {boolean} [instant=false] - 是否立即更新，无动画。
     * 此函数会切换相关的CSS类，更新图标，并重新应用布局。
     */
    function updateProcessLogSidebarCollapseState(collapse, instant = false) {
        // 更新状态中的折叠标记
        state.isProcessLogSidebarCollapsed = collapse;
        // 如果右侧日志侧边栏容器存在
        if (dom.processLogSidebarContainer) {
            // 根据折叠状态切换 'collapsed' CSS 类
            dom.processLogSidebarContainer.classList.toggle('collapsed', state.isProcessLogSidebarCollapsed);
            // 获取折叠/展开按钮内的图标元素
            const iconElement = dom.toggleProcessLogSidebarCollapseButton.querySelector('i');
            // 如果图标元素存在，则根据折叠状态更新其类名 (切换箭头方向)
            if (iconElement) {
                iconElement.className = state.isProcessLogSidebarCollapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-left';
            }
        }
        // 应用新的布局设置
        applyFixedLogSidebarLayout();
        // 将折叠状态保存到 localStorage
        localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarCollapsed', state.isProcessLogSidebarCollapsed.toString());
    }

    /**
     * 隐藏右侧日志侧边栏。
     * 更新状态，移除相关CSS类，并重新应用布局。
     */
    function hideProcessLogSidebar() {
        // 如果右侧日志侧边栏容器不存在，则直接返回
        if (!dom.processLogSidebarContainer) return;
        // 更新状态，标记侧边栏为不可见
        state.isProcessLogSidebarVisible = false;
        // 移除 'visible' CSS 类，使其隐藏
        dom.processLogSidebarContainer.classList.remove('visible');
        // 如果应用主体内容容器存在
        if (dom.appBodyContainer) {
            // 移除表示日志侧边栏打开和折叠状态的 CSS 类
            dom.appBodyContainer.classList.remove('with-process-log-open', 'log-sidebar-collapsed');
        }
        // 应用布局更改
        applyFixedLogSidebarLayout();
        // 将可见性状态保存到 localStorage
        localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarVisible', state.isProcessLogSidebarVisible.toString());
        // 在控制台记录日志侧边栏已隐藏
        console.log("右侧日志侧栏已隐藏。");
    }

    /**
     * 显示右侧日志侧边栏。
     * @param {boolean} [ensureExpanded=false] - 如果为true且侧边栏当前是折叠的，则强制展开它。
     * 更新状态，添加相关CSS类，并根据需要调整布局。
     */
    function showProcessLogSidebar(ensureExpanded = false) {
        // 如果右侧日志侧边栏容器不存在，则直接返回
        if (!dom.processLogSidebarContainer) return;
        // 更新状态，标记侧边栏为可见
        state.isProcessLogSidebarVisible = true;
        // 添加 'visible' CSS 类，使其显示
        dom.processLogSidebarContainer.classList.add('visible');

        // 如果应用主体内容容器存在
        if (dom.appBodyContainer) {
            // 添加表示日志侧边栏打开的 CSS 类
            dom.appBodyContainer.classList.add('with-process-log-open');
            // 根据侧边栏的折叠状态，切换 'log-sidebar-collapsed' CSS 类
            dom.appBodyContainer.classList.toggle('log-sidebar-collapsed', state.isProcessLogSidebarCollapsed);
        }

        // 如果需要确保展开，并且当前侧边栏是折叠的
        if (ensureExpanded && state.isProcessLogSidebarCollapsed) {
            toggleProcessLogSidebarCollapse(false); // 调用切换折叠状态的函数，传入 false 表示展开
        } else {
            // 否则，仅应用布局更改
            applyFixedLogSidebarLayout();
        }
        // 将可见性状态保存到 localStorage
        localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarVisible', state.isProcessLogSidebarVisible.toString());
        // 在控制台记录日志侧边栏的显示状态
        console.log(`右侧日志侧栏已显示 (强制展开: ${ensureExpanded}, 当前折叠状态: ${state.isProcessLogSidebarCollapsed}).`);
    }

    /**
     * 切换右侧日志侧边栏的折叠/展开状态。
     * @param {boolean} [instant=false] - 是否立即切换，无动画。
     */
    function toggleProcessLogSidebarCollapse(instant = false) {
        // 如果右侧日志侧边栏容器或切换按钮不存在，则直接返回
        if (!dom.processLogSidebarContainer || !dom.toggleProcessLogSidebarCollapseButton) return;
        // 调用更新折叠状态的函数，传入当前折叠状态的相反值
        updateProcessLogSidebarCollapseState(!state.isProcessLogSidebarCollapsed, instant);
        // 在控制台记录新的折叠状态
        console.log(`右侧日志侧栏折叠状态切换为: ${state.isProcessLogSidebarCollapsed ? '已折叠' : '已展开'}`);
    }

    /**
     * 设置应用的加载状态。
     * @param {boolean} isLoading - 是否处于加载中。
     * 此函数会禁用/启用发送按钮和输入框，并切换发送按钮的图标。
     */
    function setLoadingState(isLoading) {
        // 更新应用状态中的 isLoading 标志
        state.isLoading = isLoading;
        // 如果发送按钮存在，则根据 isLoading 状态设置其 disabled 属性
        if (dom.sendButton) dom.sendButton.disabled = isLoading;
        // 如果用户输入框存在，则根据 isLoading 状态设置其 disabled 属性
        if (dom.userInput) dom.userInput.disabled = isLoading;
        // 如果发送图标存在，则根据 isLoading 状态设置其显示/隐藏
        if (dom.sendIcon) dom.sendIcon.style.display = isLoading ? 'none' : 'inline-block';
        // 如果发送加载中图标存在，则根据 isLoading 状态设置其显示/隐藏
        if (dom.sendLoadingIcon) dom.sendLoadingIcon.style.display = isLoading ? 'inline-block' : 'none';
        // 如果发送按钮存在，则根据 isLoading 状态更新其 title 属性 (鼠标悬停提示)
        if (dom.sendButton) dom.sendButton.title = isLoading ? "墨迹传输中..." : "发送指令";
        // 如果输入区域容器存在
        if (dom.inputArea) {
            // 根据 isLoading 状态切换 'processing' CSS 类
            dom.inputArea.classList.toggle('processing', isLoading);
        }
        // 如果发送按钮存在
        if (dom.sendButton) {
            // 根据 isLoading 状态切换 'processing-active' CSS 类
            dom.sendButton.classList.toggle('processing-active', isLoading);
        }
    }

    /**
     * 将右侧日志侧边栏滚动到底部。
     * @param {boolean} [instant=false] - 是否立即滚动，无平滑效果。
     */
    function scrollToProcessLogBottom(instant = false) {
        // 检查日志侧栏内容元素是否存在
        if (!dom.processLogSidebarContent) {
            // 如果不存在，则在控制台输出错误信息并返回
            console.error("日志侧栏内容元素 (processLogSidebarContent) 未找到，无法滚动。");
            return;
        }
        // 获取日志侧栏内容容器元素
        const container = dom.processLogSidebarContent;
        // 根据 instant 参数和动画级别设置滚动行为 ('auto' 或 'smooth')
        const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth';
        // 执行滚动操作，将容器滚动到其最底部
        container.scrollTo({ top: container.scrollHeight, behavior: behavior });
    }

    /**
     * 解析日志项的CSS类字符串，提取类型、阶段和状态。
     * @param {string} itemClassesStr - 包含多个CSS类的字符串。
     * @returns {object} 解析后的对象，包含 type, stage, status 属性。
     */
    function parseItemClasses(itemClassesStr) {
        // 如果类字符串存在，则按空格分割成数组；否则使用空数组
        const classes = itemClassesStr ? itemClassesStr.split(' ') : [];
        // 初始化解析结果对象
        const parsed = { type: null, stage: null, status: null };
        // 遍历所有类名
        classes.forEach(cls => {
            // 如果类名以 'type-' 开头，则提取类型
            if (cls.startsWith('type-')) parsed.type = cls.substring(5);
            // 如果类名以 'stage-' 开头，则提取阶段
            else if (cls.startsWith('stage-')) parsed.stage = cls.substring(6);
            // 如果类名以 'status-' 开头，则提取状态
            else if (cls.startsWith('status-')) parsed.status = cls.substring(7);
            // 如果类名以 'phase-' 开头，也作为阶段处理 (兼容旧命名)
            else if (cls.startsWith('phase-')) parsed.stage = cls.substring(6);
        });
        // 返回解析后的对象
        return parsed;
    }

    /**
     * 总结工具调用的参数对象，用于日志显示。
     * @param {object} argsObj - 工具参数对象。
     * @returns {string} 参数的简短字符串表示。
     */
    function summarizeArguments(argsObj) {
        // 检查参数对象是否有效，如果无效或为空，则返回 "(无参数)"
        if (!argsObj || typeof argsObj !== 'object' || Object.keys(argsObj).length === 0) {
            return "(无参数)";
        }
        try {
            // 使用 JSON.stringify 将参数对象转换为字符串
            // replacer 函数用于处理长字符串，截断超过40个字符的字符串
            // 最后限制总长度不超过200个字符
            return JSON.stringify(argsObj, (key, value) => {
                if (typeof value === 'string' && value.length > 40) {
                    return value.substring(0, 37) + "..."; // 截断长字符串并添加省略号
                }
                return value; // 其他值保持不变
            }).substring(0, 200); // 限制总长度
        } catch (e) {
            // 如果转换过程中发生错误，则在控制台打印警告并返回 "(参数总结出错)"
            console.warn("总结参数时发生错误:", e);
            return "(参数总结出错)";
        }
    }

    /**
     * 格式化日志项的详细信息对象为HTML字符串。
     * @param {object} details - 包含详细信息的对象。
     * @param {string|null} type - 日志项类型。
     * @param {string|null} stage - 日志项阶段。
     * @param {string|null} status - 日志项状态。
     * @returns {string|null} 格式化后的HTML字符串，如果无有效细节则返回null。
     */
    function formatLogDetails(details, type, stage, status) {
        // 检查 details 对象是否有效，如果无效或为空，则返回 null
        if (!details || typeof details !== 'object' || Object.keys(details).length === 0) {
            return null;
        }
        let html = ''; // 初始化 HTML 字符串
        // 定义一个递归函数来格式化对象
        const formatRecursive = (obj, currentType, currentStage, currentStatus, indentLevel = 0) => {
            let partHtml = ''; // 初始化部分 HTML 字符串
            // 遍历对象的每个属性
            for (const key in obj) {
                // 确保属性是对象自身的属性，而不是原型链上的
                if (Object.prototype.hasOwnProperty.call(obj, key)) {
                    const value = obj[key]; // 获取属性值
                    // 格式化属性键名：将驼峰命名转换为空格分隔，替换下划线，并首字母大写
                    const displayKey = key
                        .replace(/([A-Z])/g, " $1") // 在大写字母前添加空格
                        .replace(/_/g, ' ')         // 将下划线替换为空格
                        .trim()                      // 去除首尾空格
                        .replace(/\b\w/g, char => char.toUpperCase()); // 将每个单词的首字母大写
                    // 根据缩进级别设置左内边距样式
                    const paddingLeftStyle = `padding-left: ${indentLevel * 10}px;`;

                    // 跳过特定类型的特定键，这些键可能冗余或已在其他地方处理
                    // 确保只跳过 tool_call_id 在特定的消息类型中
                    if ((type === 'plan_details' || type === 'tool_status_update') && key === 'tool_call_id') {
                         continue;
                    }

                    // 特殊处理 'uiHints' 键
                    if (key === 'uiHints' && typeof value === 'object' && value !== null) {
                        // 获取 displayNameForTool 和 estimatedDurationCategory，并进行HTML转义
                        const dn = String(value.displayNameForTool || 'N/A').replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        const ed = String(value.estimatedDurationCategory || 'N/A').replace(/</g, "&lt;").replace(/>/g, "&gt;");
                         // 检查 showProgressGranularly 是否存在并显示
                        const spg = value.showProgressGranularly !== undefined ? `, 细粒度进度: ${value.showProgressGranularly ? '是' : '否'}` : '';
                        // 构建 uiHints 的 HTML
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">UI投影:</strong> <span class="log-detail-value">显示: ${dn}, 时长: ${ed}${spg}</span></div>`;
                    } else if (key === 'result_data_preview' && typeof value === 'string') { // 特殊处理 'result_data_preview' 键
                        // 获取预览内容并进行HTML转义
                        let previewContent = String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        // 构建结果预览的 HTML，使用 <pre> and <code> 标签
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">结果预览:</strong> <pre class="log-detail-raw-json"><code>${previewContent}</code></pre></div>`; // Use log-detail-raw-json for pre formatting
                    } else if ((type === 'plan_details' || type === 'tool_status_update') && (key === 'arguments' || key === 'toolArguments') && typeof value === 'object' && value !== null) { // 特殊处理参数对象
                        let argItems = []; // 初始化参数项数组
                        // 遍历参数对象的每个参数
                        for (const argKey in value) {
                            // 格式化参数键名
                            const formattedArgKey = argKey.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                            // 将参数键值对添加到数组，并对值进行HTML转义
                             const argValue = value[argKey];
                             let formattedArgValue;
                             if (typeof argValue === 'object' && argValue !== null) {
                                 try { formattedArgValue = JSON.stringify(argValue).replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
                                 catch (e) { formattedArgValue = String(argValue).replace(/</g, "&lt;").replace(/>/g, "&gt;") + " (JSON error)"; }
                             } else {
                                 formattedArgValue = String(argValue).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                             }
                            argItems.push(`<em class="log-arg-key">${formattedArgKey}</em>: ${formattedArgValue}`);
                        }
                        // 构建参数的 HTML
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong> <span class="log-detail-value">${argItems.join('; ')}</span></div>`;
                    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) { // If the value is an object and not an array
                        // Build HTML for the object header
                        partHtml += `<div class="log-detail-item log-detail-object-header" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong></div>`;
                        // Recursively call formatRecursive to handle nested objects
                        partHtml += formatRecursive(value, currentType, currentStage, currentStatus, indentLevel + 1);
                    } else if (Array.isArray(value)) { // If the value is an array
                        // Format each element in the array
                        const arrayItems = value.map(item => {
                            if (typeof item === 'object' && item !== null) return JSON.stringify(item).replace(/</g, "&lt;").replace(/>/g, "&gt;"); // Object to JSON string and escape
                            return String(item).replace(/</g, "&lt;").replace(/>/g, "&gt;"); // Other types to string and escape
                        });
                        // Build HTML for the array
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong> <span class="log-detail-value log-detail-array">[${arrayItems.join(', ')}]</span></div>`;
                    } else { // If the value is another basic type
                        // Escape HTML special characters in the value
                        const sanitizedValue = String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        // Build HTML for the basic type key-value pair
                        partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong> <span class="log-detail-value">${sanitizedValue}</span></div>`;
                    }
                }
            }
            return partHtml; // Return the HTML for the current level
        };
        // Call the recursive function to start formatting
        html = formatRecursive(details, type, stage, status, 0);
        // If the HTML string is not empty, return it, otherwise return null
        return html || null;
    }

    /**
     * 向右侧日志侧边栏添加一个新的日志项。
     * 此函数处理不包含独立思考过程的日志条目。图标和主消息文本将并排显示。
     * @param {string} messageText - 日志消息文本 (将作为主文本)。
     * @param {string} iconClass - 用于日志项的FontAwesome图标类。
     * @param {string} [itemClasses=''] - 附加到日志项的CSS类字符串。
     * @param {object|null} [details=null] - 包含详细信息的对象，将格式化并显示在主文本下方。
     * @returns {HTMLElement|null} 创建的日志项DOM元素，如果失败则返回null。
     */
    function appendLogItem(messageText, iconClass, itemClasses = '', details = null) {
        // 检查日志侧边栏内容元素是否存在
        if (!dom.processLogSidebarContent) {
            console.error("日志侧栏内容元素 (processLogSidebarContent) 未找到。"); // 输出错误信息
            return null; // 返回 null
        }
        // 创建日志项的 div 元素
        const logItemDiv = document.createElement('div');
        // 设置基础类名和入场动画类名
        logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
        // 设置动画持续时间
        logItemDiv.style.setProperty('--animate-duration', '0.3s');
        // 如果有附加的 CSS 类，则添加它们
        if (itemClasses) {
            logItemDiv.classList.add(...itemClasses.split(' ').filter(cls => cls)); // 分割字符串并过滤空类名后添加
        }

        // 创建图标元素 (作为日志项的第一个子元素 - CSS将使其与第二个子元素并排)
        const iconEl = document.createElement('i');
        iconEl.className = iconClass; // 设置图标的 FontAwesome 类
        logItemDiv.appendChild(iconEl);

        // 创建主要内容区域的包装器 (垂直 flex 容器)，包含主文本和详细信息 (作为日志项的第二个子元素)
        const contentAreaWrapper = document.createElement('div');
        contentAreaWrapper.classList.add('log-item-content-area'); // 添加 CSS 类

        // 创建消息文本元素 (作为内容区域包装器的第一个子元素)
        const messageEl = document.createElement('span');
        messageEl.className = 'log-item-message';
        messageEl.textContent = messageText; // 设置消息文本内容
        contentAreaWrapper.appendChild(messageEl); // 将消息文本添加到内容区域包装器

        // 如果存在详细信息且不为空对象
        if (details && Object.keys(details).length > 0) {
            // 创建详细信息区域的 div 元素 (作为内容区域包装器的第二个子元素)
            const detailsEl = document.createElement('div');
            detailsEl.className = 'log-item-details'; // 使用通用详细信息类
            // 解析日志项的类名以获取类型、阶段和状态，用于格式化详细信息
            const { type: logType, stage: logStage, status: logStatus } = parseItemClasses(logItemDiv.className);
            // 格式化详细信息对象为 HTML 字符串
            const formattedDetailsHtml = formatLogDetails(details, logType, logStage, logStatus);

            // 如果格式化后的 HTML 不为空
            if (formattedDetailsHtml) {
                detailsEl.innerHTML = formattedDetailsHtml; // 设置详细信息区域的 HTML 内容
            } else { // 如果格式化失败或无内容
                 // 添加一个表示“无详细信息”的默认消息，或者尝试显示原始 details 对象
                 detailsEl.innerHTML = `<span class="log-detail-item"><strong class="log-detail-key">详细信息:</strong> <span class="log-detail-value">(无或格式化失败)</span></span>`;
                try {
                    // Fallback: Attempt to represent the details object as JSON or string if formatting failed
                    let rawDetailsStr = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details);
                    detailsEl.innerHTML += `<pre class="log-detail-raw-json error"><code>${rawDetailsStr.replace(/</g, "&lt;").replace(/>/g, "&gt;")}<br>(原始数据)</code></pre>`;
                } catch (e_raw) {
                     // If even the fallback fails
                     detailsEl.innerHTML += `<span class="log-detail-item error"><strong class="log-detail-key">原始数据错误:</strong> <span class="log-detail-value">${e_raw.message}</span></span>`;
                }
            }
            contentAreaWrapper.appendChild(detailsEl); // 将详细信息区域添加到内容区域包装器
        }

        // 将内容区域包装器添加到日志项 div (在图标之后)
        logItemDiv.appendChild(contentAreaWrapper);


        // 将日志项 div 添加到日志侧边栏内容区域
        dom.processLogSidebarContent.appendChild(logItemDiv);
        // 滚动日志侧边栏到底部
        scrollToProcessLogBottom();
        // 返回创建的日志项 DOM 元素
        return logItemDiv;
    }

    /**
     * 向右侧日志侧边栏添加一个包含思考过程的日志项。
     * 此函数处理包含独立思考过程的日志条目。图标和主消息文本将并排显示，思考过程在下方独立区域。
     * @param {string} headerText - 日志项的头部消息文本 (将作为主文本)。
     * @param {string} headerIconClass - 用于头部的FontAwesome图标类。
     * @param {string} itemClasses - 附加到日志项的CSS类字符串。
     * @param {string} thinkContent - 思考过程的文本内容 (将显示在主文本下方)。
     * @param {string} [thinkBubbleLabel="详细思考投影"] - 思考气泡的标签文本。
     * @returns {HTMLElement|null} 创建的日志项DOM元素，如果失败则返回null。
     */
    function appendLogItemWithThink(headerText, headerIconClass, itemClasses, thinkContent, thinkBubbleLabel = "详细思考投影") {
        // 检查日志侧边栏内容元素是否存在
        if (!dom.processLogSidebarContent) {
            console.error("日志侧栏内容元素 (processLogSidebarContent) 未找到。"); // 输出错误信息
            return null; // 返回 null
        }
        // 创建日志项的 div 元素
        const logItemDiv = document.createElement('div');
        // 设置基础类名和入场动画类名
        logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
        // 设置动画持续时间
        logItemDiv.style.setProperty('--animate-duration', '0.3s');
        // 如果有附加的 CSS 类，则添加它们
        if (itemClasses) logItemDiv.classList.add(...itemClasses.split(' '));

        // 创建图标元素 (作为日志项的第一个子元素 - CSS将使其与第二个子元素并排)
        const iconEl = document.createElement('i');
        iconEl.className = headerIconClass; // 设置图标的 FontAwesome 类
        logItemDiv.appendChild(iconEl);

        // 创建主要内容区域的包装器 (垂直 flex 容器)，包含主文本和思考内容 (作为日志项的第二个子元素)
        const contentAreaWrapper = document.createElement('div');
        contentAreaWrapper.classList.add('log-item-content-area'); // 添加 CSS 类

        // 创建主消息文本元素 (作为内容区域包装器的第一个子元素)
        const messageEl = document.createElement('span');
        messageEl.className = 'log-item-message';
        messageEl.textContent = headerText; // 设置主消息文本内容 (使用 headerText 作为主文本)
        contentAreaWrapper.appendChild(messageEl);


        // 如果存在思考内容
        if (thinkContent) {
            // 创建思考内容区域的 div 元素 (作为内容区域包装器的第二个子元素 - 将显示在主文本下方)
            const thinkDiv = document.createElement('div');
            thinkDiv.classList.add('log-think-content'); // 添加特定类名

            // 格式化思考内容：替换换行符为 <br>
            let formattedThink = String(thinkContent).replace(/\n/g, '<br>');
            // 定义用于匹配 JSON 代码块的正则表达式
            const jsonBlockRegex = /```json\s*([\s\S]*?)\s*```/gi; // Adjusted regex to handle potential surrounding whitespace
            // 替换思考内容中的 JSON 代码块为格式化后的 <pre><code> 块
            formattedThink = formattedThink.replace(jsonBlockRegex, (match, jsonContentStr) => {
                const trimmedJson = jsonContentStr.trim(); // Remove leading/trailing whitespace from JSON content
                try {
                    const parsedJson = JSON.parse(trimmedJson); // Parse the JSON
                    // Format the parsed JSON object into a string with indentation (2 spaces), and escape HTML special characters
                    const escapedJsonString = JSON.stringify(parsedJson, null, 2)
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    // Return the formatted HTML using <pre> and <code> tags with the embedded-json class
                    return `<pre class="log-detail-raw-json"><code>${escapedJsonString}</code></pre>`;
                } catch (jsonErr) {
                    // If JSON parsing fails, log a warning to the console
                    console.warn("Log item with think: JSON parsing for pretty print failed within thought:", jsonErr);
                    // Escape HTML special characters from the original JSON content
                    const escapedOriginalJson = trimmedJson
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    // Return HTML containing the original content and an error message, styled as an error embedded JSON block
                    return `<pre class="log-detail-raw-json error"><code>${escapedOriginalJson}<br>(无效JSON投影)</code></pre>`;
                }
            });
            // Set the HTML content of the thinking content area, including the label and formatted thinking text
            thinkDiv.innerHTML = `<strong><i class="fas fa-brain"></i> ${thinkBubbleLabel}:</strong><div class="think-bubble">${formattedThink}</div>`;
            // Append the thinking content area to the content area wrapper
            contentAreaWrapper.appendChild(thinkDiv);
        }

        // Append the content area wrapper to the log item div (after the icon)
        logItemDiv.appendChild(contentAreaWrapper);

        // Append the log item div to the process log sidebar content area
        dom.processLogSidebarContent.appendChild(logItemDiv);
        // Scroll the process log sidebar to the bottom
        scrollToProcessLogBottom();
        // Return the created log item DOM element
        return logItemDiv;
    }


    /**
     * 处理来自服务器的 'general_status' 类型消息。
     * @param {object} msg - 包含状态信息的服务器消息对象。
     * 此函数根据状态信息选择合适的图标和类，并调用 appendLogItem 添加到日志。
     */
    function handleGeneralStatus(msg) {
        // 从消息对象中解构出 stage, status, message (重命名为 msgText), 和 details
        const { stage, status, message: msgText, details } = msg;
        // 初始化日志图标类为信息图标和通用日志信息类
        let logIconClass = 'fas fa-info-circle log-info';
        // 构建日志项的 CSS 类字符串，包含类型、阶段和状态
        let logItemClasses = `type-general_status stage-${stage} status-${status}`;

        // 根据不同的状态 (status) 更新日志图标类
        if (status === 'started' || status === 'llm_retry_needed' || status === 'llm_error_retrying') logIconClass = 'fas fa-sync-alt fa-spin log-processing'; // 开始或重试中：旋转的同步图标
        else if (status === 'completed' || status === 'received' || status === 'completed_and_validated') logIconClass = 'fas fa-check-circle log-success'; // 完成或已接收：成功的勾选图标
        else if (status === 'error' || status === 'failed' || status === 'failed_after_llm_retries' || status === 'tool_failure_detected' || status === 'fatal_error_handler' || status === 'fatal_error_capture') { // 错误或失败：错误的感叹号三角图标
            logIconClass = 'fas fa-exclamation-triangle log-error';
        }
        else if (status === 'ignored') logIconClass = 'fas fa-eye-slash log-muted'; // 已忽略：静音的眼睛斜杠图标

        // 调用 appendLogItem 函数将日志项添加到日志侧边栏
        appendLogItem(msgText, logIconClass, logItemClasses, details);
        // 如果日志侧边栏当前不可见，则显示它（不强制展开）
        if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
    }

    /**
     * 处理来自服务器的 'llm_communication_status' 类型消息。
     * @param {object} msg - 包含LLM通信状态的服务器消息对象。
     * 此函数根据LLM通信状态选择图标和类，并添加到日志。
     */
    function handleLlmCommStatus(msg) {
        // 从消息对象中解构出 llm_phase, status, message (重命名为 msgText), 和 details
        const { llm_phase, status, message: msgText, details } = msg;
        // 初始化日志图标类为大脑图标和处理中样式
        let logIconClass = 'fas fa-brain log-processing';
        // 构建日志项的 CSS 类字符串，包含类型、LLM阶段和状态
        let logItemClasses = `type-llm_communication_status phase-${llm_phase} status-${status}`;

        // 根据不同的状态 (status) 更新日志图标类
        if (status === 'started') logIconClass = 'fas fa-brain fa-beat-fade log-processing'; // 开始：跳动的大脑图标
        else if (status === 'completed') logIconClass = 'fas fa-check log-success'; // 完成：成功的勾选图标
        else if (status === 'error') logIconClass = 'fas fa-bolt log-error'; // 错误：闪电图标 (表示错误)

        // 调用 appendLogItem 函数将日志项添加到日志侧边栏
        appendLogItem(msgText, logIconClass, logItemClasses, details);
        // 如果日志侧边栏当前不可见，则显示它（不强制展开）
        if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
    }

    /**
     * 处理来自服务器的 'thinking_log' 类型消息。
     * @param {object} msg - 包含思考日志内容的服务器消息对象。
     * 如果设置允许，则以带思考气泡的方式添加到日志，否则添加简略日志。
     */
    function handleThinkingLog(msg) {
        // 从消息对象中解构出 stage, content, 和 llm_interaction_id
        const { stage, content, llm_interaction_id } = msg;
        // 如果消息中包含 content，则更新状态中的 lastResponseThinking
        if (content) {
            state.lastResponseThinking = content;
        }

        // 检查用户设置是否允许在日志中显示思考气泡
        if (state.showLogBubblesThink) {
            // 格式化思考标签文本，将下划线替换为空格并转为大写
            const thinkLabel = `AI思维墨迹 (${stage.replace(/_/g, ' ').toUpperCase()})`;
            // 调用 appendLogItemWithThink 函数添加带思考气泡的日志项
            appendLogItemWithThink(thinkLabel, 'fas fa-lightbulb log-think', `type-thinking_log stage-${stage} llm-id-${llm_interaction_id}`, content, "详细思考投影:");
        } else {
            // 如果不允许显示思考气泡，则添加简略的日志项
            // 日志内容为 "思维墨迹收到 (阶段, LLM_ID: ID) - 内容前80字符..."
            appendLogItem(`思维墨迹收到 (${stage}, LLM_ID: ${llm_interaction_id}) - ${content.substring(0, 80)}...`, 'fas fa-comment-dots log-muted', `type-thinking_log stage-${stage} muted`);
        }
        // 如果日志侧边栏当前不可见，则显示它（不强制展开）
        if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
    }

    /**
     * 处理来自服务器的 'plan_details' 类型消息，展示Agent的行动计划。
     * @param {object} msg - 包含行动计划详情的服务器消息对象。
     * 此函数会遍历计划中的每个工具调用，并将其添加到日志中。
     */
    function handlePlanDetails(msg) {
        // 从消息对象中解构出 plan (行动计划数组)
        const { plan } = msg;
        // 清空应用状态中待处理的工具调用记录
        state.pendingToolCalls = {};
        // 遍历计划中的每一个工具调用 (toolCall)
        if (Array.isArray(plan)) { // Ensure plan is an array before iterating
             plan.forEach(toolCall => {
                 // 从 toolCall 对象中解构出相关属性
                 const { toolCallId, toolName, toolArguments, uiHints = {}, order } = toolCall;
                 // Check if essential properties exist
                 if (!toolCallId || !toolName) {
                      console.warn("Plan details missing essential fields (toolCallId or toolName), skipping:", toolCall);
                      appendLogItem(
                          `收到无效计划项 (缺少ID或名称).`,
                          'fas fa-exclamation-circle log-warning',
                          'type-plan_details status-invalid',
                          toolCall
                      );
                      return; // Skip this invalid item
                 }
                 // 将当前工具调用信息记录到待处理列表中
                 state.pendingToolCalls[toolCallId] = {
                     name: toolName, // 工具名称
                     args_summary: summarizeArguments(toolArguments), // 参数的简短总结
                     ui_hints: uiHints, // UI 提示信息
                     order: order // 执行顺序
                 };
                 // Get the display name for the tool, prioritizing displayNameForTool from uiHints, otherwise generating from toolName
                 const displayName = uiHints.displayNameForTool || toolName.replace(/_tool$/, "").replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
                 // Construct the log message text
                 const logMessageText = `执行节点 #${order}: ${displayName} (ID: ${toolCallId}) - 状态: QUEUED`;
                 // Call the appendLogItem function to add the planned tool call to the log sidebar
                 // Details include arguments and UI hints for display
                 appendLogItem(
                     logMessageText, // Log message text (主文本)
                     'fas fa-tasks log-info', // Log icon (任务列表 icon)
                     `type-plan_details tool-${toolName} status-pending`, // Log item CSS classes
                     { arguments: toolArguments, tool_call_id: toolCallId, ui_hints: uiHints } // Detailed information for display below the main text
                 );
             });
        } else {
            console.warn("Received plan_details message with non-array plan property:", plan);
             appendLogItem(
                `收到无效计划详情 (Plan不是数组).`,
                'fas fa-exclamation-circle log-error',
                'type-plan_details status-invalid',
                { raw_plan_data: plan } // Include raw data in details
            );
        }
        // Show and ensure the log sidebar is expanded so the user can see the plan details
        showProcessLogSidebar(true);
    }

    /**
     * 处理来自服务器的 'tool_status_update' 类型消息，更新工具执行状态。
     * @param {object} msg - 包含工具执行状态更新的服务器消息对象。
     * 此函数会查找现有的日志项并更新它，或者添加一个新的日志项来反映工具状态。
     */
    function handleToolStatusUpdate(msg) {
        // 从消息对象中解构出工具调用ID、工具名称、状态、消息文本和详细信息
        const { tool_call_id, tool_name, status, message: msgText, details } = msg;
         // Validate essential fields
        if (!tool_call_id || !tool_name || status === undefined || msgText === undefined) {
             console.warn("Received invalid tool_status_update message (missing essential fields):", msg);
              appendLogItem(
                 `收到无效工具状态更新 (缺少ID,名称,状态或消息).`,
                 'fas fa-exclamation-circle log-error',
                 'type-tool_status_update status-invalid',
                 msg // Include the full invalid message in details
             );
            return;
        }
        // Initialize log icon class and generic info class
        let logIconClass = 'fas fa-cog log-info';
        // Set specific status CSS class
        let itemStatusClass = `status-${status}`;

        // Update log icon class based on different tool execution statuses
        if (status === 'running') logIconClass = 'fas fa-cogs fa-spin log-processing'; // Running: Spinning cogs icon
        else if (status === 'retrying') logIconClass = 'fas fa-history fa-spin log-processing'; // Retrying: Spinning history icon
        else if (status === 'succeeded') logIconClass = 'fas fa-check-double log-success'; // Succeeded: Double checkmark icon
        else if (status === 'failed') logIconClass = 'fas fa-times-circle log-error'; // Failed: Error cross icon
        else if (status === 'aborted_due_to_previous_failure') { // Aborted due to previous failure
            logIconClass = 'fas fa-ban log-warning'; // Aborted: Ban icon (warning)
            itemStatusClass = 'status-aborted'; // Explicitly set status class to 'aborted'
        }

        // Get tool information from the pending tool calls list
        const pendingToolInfo = state.pendingToolCalls[tool_call_id];
        // Get the display name for the tool, prioritizing displayNameForTool from pending info's uiHints, otherwise generating from tool_name
        const displayName = pendingToolInfo?.ui_hints?.displayNameForTool || tool_name.replace(/_tool$/, "").replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
        // Construct the full log message text (this will be the main text next to the icon)
        let fullLogMessage = `工具模块: ${displayName} (ID: ${tool_call_id}) - ${status.replace(/_/g, ' ').toUpperCase()}: ${msgText}`;

        // Attempt to find an existing log item for this tool call in the sidebar content area
        // Added data-tool-call-id attribute in appendLogItem to make lookup reliable
        let existingLogItem = dom.processLogSidebarContent.querySelector(`.log-item[data-tool-call-id="${tool_call_id}"]`);

        // If found an existing log item for this tool call
        if (existingLogItem) {
            // Update the existing log item's classes, icon, message, and details
            existingLogItem.className = `log-item animate__animated type-tool_status_update tool-${tool_name} ${itemStatusClass}`; // Update classes
            existingLogItem.style.setProperty('--animate-duration', '0.5s'); // Keep animation duration

            const iconEl = existingLogItem.querySelector('i:first-child');
            if (iconEl) iconEl.className = logIconClass; // Update icon class

            const messageEl = existingLogItem.querySelector('.log-item-message');
            if (messageEl) messageEl.textContent = fullLogMessage; // Update message text

            // Find or create the details element within the content area wrapper
            const contentAreaWrapper = existingLogItem.querySelector('.log-item-content-area');
            if (contentAreaWrapper) {
                 let detailsEl = contentAreaWrapper.querySelector('.log-item-details') || contentAreaWrapper.querySelector('.log-think-content'); // Could be either class for details

                 if (details && Object.keys(details).length > 0) { // If there are new details
                     if (!detailsEl) { // If original item didn't have details, create a new one
                          detailsEl = document.createElement('div');
                          detailsEl.className = 'log-item-details'; // Assume it's a standard details block
                          contentAreaWrapper.appendChild(detailsEl);
                     }
                      // Ensure the correct class is applied for standard details
                     detailsEl.classList.remove('log-think-content'); // Remove if it was a think block previously
                     detailsEl.classList.add('log-item-details'); // Add standard details class

                     const { type, stage, status: parsedStatus } = parseItemClasses(existingLogItem.className);
                     const formattedDetailsHtml = formatLogDetails(details, type, stage, parsedStatus);
                     detailsEl.innerHTML = formattedDetailsHtml || '';
                      if (!formattedDetailsHtml) { // If formatting failed, provide fallback
                          detailsEl.innerHTML = `<span class="log-detail-item"><strong class="log-detail-key">详细信息:</strong> <span class="log-detail-value">(无或格式化失败)</span></span>`;
                          try {
                              let rawDetailsStr = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details);
                              detailsEl.innerHTML += `<pre class="log-detail-raw-json error"><code>${rawDetailsStr.replace(/</g, "&lt;").replace(/>/g, "&gt;")}<br>(原始数据)</code></pre>`;
                          } catch (e_raw) { /* Ignore further errors */ }
                      }
                 } else if (detailsEl) { // If there are no new details, but an element for details existed, remove it
                     detailsEl.remove(); // Remove the details element entirely
                 }
            } else {
                 console.error("Tool status update: Cannot find content area wrapper for details update.");
            }


             // Add animation feedback
            existingLogItem.classList.remove('animate__flash', 'animate__headShake', 'animate__pulse');
            if (status === 'failed') existingLogItem.classList.add('animate__headShake'); // Shake on failure
            else if (status === 'succeeded') existingLogItem.classList.add('animate__pulse'); // Pulse on success
            else existingLogItem.classList.add('animate__flash'); // Flash on other updates

        } else { // If no existing log item found, create a new one
             // Create a new log item for this tool status update
             const logItemDiv = appendLogItem(fullLogMessage, logIconClass, `type-tool_status_update tool-${tool_name} ${itemStatusClass}`, details);
            // Add the toolCallId as a data attribute for future lookups
             if (logItemDiv) logItemDiv.dataset.toolCallId = tool_call_id;

            // Add animation feedback to the newly created item
            if (logItemDiv) {
                 logItemDiv.classList.remove('animate__fadeInUp'); // Remove initial fade-in
                 logItemDiv.classList.add('animate__animated'); // Ensure animated class is present for potential future animations
                 if (status === 'failed') logItemDiv.classList.add('animate__headShake');
                 else if (status === 'succeeded') logItemDiv.classList.add('animate__pulse');
                 else logItemDiv.classList.add('animate__flash');
                logItemDiv.style.setProperty('--animate-duration', '0.5s');
            }
        }

        // If the process log sidebar is currently not visible, show it (without forcing expansion)
        if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);

        // If tool execution status is success, failed, or aborted
        if (status === 'succeeded' || status === 'failed' || status === 'aborted_due_to_previous_failure') {
            // Remove this tool call from the pending list
            if (state.pendingToolCalls[tool_call_id]) {
                delete state.pendingToolCalls[tool_call_id];
            }
        }
    }

    /**
     * 处理来自服务器的 'interim_response' 类型消息，通常是Agent在执行工具前的过渡性回复。
     * @param {object} msg - 包含过渡性回复内容的服务器消息对象。
     */
    function handleInterimResponse(msg) {
        // 从消息对象中解构出 content (回复内容) 和 llm_interaction_id
        const { content, llm_interaction_id } = msg;
        // Call the appendLogItem function to add the interim response to the log sidebar
        // The main text will be a preview of the intention message
        appendLogItem(
            // Log message text, showing the first 180 characters of the content, with ellipsis if longer
            `AI意图墨迹: "${content.substring(0, 180)}${content.length > 180 ? '...' : ''}"`,
            'fas fa-feather-alt log-info', // Log icon (feather pen icon, indicating intention)
            'type-agent_intention', // Log item CSS classes
            // Detailed information, including LLM interaction ID and the full content
            { llm_interaction_id: llm_interaction_id, full_content: content }
        );
        // If the process log sidebar is currently not visible, show it (without forcing expansion)
        if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false);
    }

    /**
     * 处理来自服务器的 'final_response' 类型消息，这是Agent对用户请求的最终答复。
     * @param {object} msg - 包含最终答复内容的服务器消息对象。
     * 此函数会解析最终响应，将其添加到聊天区域，并更新会话状态。
     */
    function handleFinalResponse(msg) {
        // Hide the typing indicator
        hideTypingIndicator();
        // Set the application's loading state to false (not loading)
        setLoadingState(false);
        // Clear the current client request ID, indicating this request is complete
        state.currentClientRequestId = null;
        // Clear the list of pending tool calls
        state.pendingToolCalls = {};

        // Destructure content (main response content) and llm_interaction_id from the message object
        const { content, llm_interaction_id } = msg;
        // Get the camelCase JSON object for the specific version (v1.3.2) from the message, if successful
        const finalCamelCaseJson = msg.final_v1_3_2_camelcase_json_if_success; // Ensure version number syncs with backend

        // Initialize thinking content and actual response content for the chat bubble
        let thinkingForBubble = null;
        let actualContentForBubble = content; // Default to raw content

        // Check if finalCamelCaseJson exists, is an object, and its status is 'success'
        if (finalCamelCaseJson && typeof finalCamelCaseJson === 'object' && finalCamelCaseJson.status === 'success') {
            // If the JSON contains thoughtProcess, use it as thinking content
            if (finalCamelCaseJson.thoughtProcess) {
                thinkingForBubble = finalCamelCaseJson.thoughtProcess;
            }
            // Check if the JSON structure conforms to the expected decision and user response content
            if (finalCamelCaseJson.decision && typeof finalCamelCaseJson.decision === 'object' &&
                finalCamelCaseJson.decision.responseToUser && typeof finalCamelCaseJson.decision.responseToUser === 'object' &&
                finalCamelCaseJson.decision.responseToUser.content !== undefined // Check if content exists even if it's null/empty
            ) {
                 // Use the content from the JSON, defaulting to an empty string if it's null or undefined
                actualContentForBubble = finalCamelCaseJson.decision.responseToUser.content || "";


                // Get suggestions for next steps
                const suggestions = finalCamelCaseJson.decision.responseToUser.suggestionsForNextSteps;
                // If suggestions exist, are an array, and have a length greater than 0
                if (suggestions && Array.isArray(suggestions) && suggestions.length > 0) {
                    // Build the HTML string for suggestions
                    let suggestionsText = "\n\n<div class=\"final-response-suggestions\"><strong>下一步行动投影:</strong><ul>";
                    suggestions.forEach(sugg => {
                        if (sugg.textForUser) { // Ensure suggestion text exists
                            // Create a list item and a quick action button for each suggestion
                            // Escape quotes in data-message attribute
                            const escapedMessage = String(sugg.textForUser).replace(/"/g, '&quot;');
                             // Escape HTML special characters in the displayed text
                            const escapedTextForUser = String(sugg.textForUser).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                            suggestionsText += `<li><a href="#" class="quick-action-btn lumina-button" data-message="${escapedMessage}"><i class="fas fa-arrow-right"></i> ${escapedTextForUser}</a></li>`;
                        }
                    });
                    suggestionsText += "</ul></div>";
                    // Append the suggestions HTML to the actual response content
                    actualContentForBubble += suggestionsText;
                    // Append the response with suggestions to the chat box, marked as HTML content
                    appendMessage(actualContentForBubble, 'agent', true, thinkingForBubble, false, [], null);
                } else {
                    // If no suggestions, just append the response content to the chat box
                     // If actualContentForBubble is empty from JSON and there are no suggestions, provide a default message
                    if (!actualContentForBubble.trim()) {
                         actualContentForBubble = "(Agent返回的回复内容为空)"; // Fallback message
                         console.warn("Final response JSON has empty content and no suggestions. Using fallback message.");
                    }
                    appendMessage(actualContentForBubble, 'agent', false, thinkingForBubble, false, [], null); // Use false for isHTML if no suggestions added HTML
                }
            } else {
                // If the JSON structure is not as expected, use the raw content as a fallback, and log a warning
                console.warn("Final response JSON structure missing decision.responseToUser.content or nested objects are invalid. Using fallback content.", finalCamelCaseJson);
                 // Use the raw content as the final message, add an error type for potential styling
                appendMessage(content || "(Agent返回的原始内容为空)", 'agent', false, thinkingForBubble, false, [], "ContentMissingIn_V1_PCP_JSON_Or_Structure_Invalid");
                actualContentForBubble = content || "(Agent返回的原始内容为空)"; // Update for session history
            }
        } else {
            // If no valid finalCamelCaseJson or its status is not success
            // Use the previously cached thinking process
            thinkingForBubble = state.lastResponseThinking;
            // Determine the reason for fallback
            const reasonForFallback = finalCamelCaseJson
                ? `JSON status is not 'success' (is '${finalCamelCaseJson.status}') or JSON is not an object (is '${typeof finalCamelCaseJson}').`
                : "final_v1_3_2_camelcase_json_if_success is missing.";
            // Log a warning indicating fallback and cached thinking
            console.warn(`Final response: ${reasonForFallback} Using fallback content and cached thinking. Raw message content: "${content}"`, finalCamelCaseJson);
            // Append the raw content as the final message, add an error type including the reason for fallback
            appendMessage(content || "(Agent返回的原始内容为空)", 'agent', false, thinkingForBubble, false, [], `ErrorResponseOrNo_V1_PCP_JSON_Reason:_${reasonForFallback.replace(/\s/g, '_').substring(0, 50)}`);
            actualContentForBubble = content || "(Agent返回的原始内容为空)"; // Update for session history
        }

        // Add the final Agent response to the current session's message history
        addMessageToCurrentSession({
            content: actualContentForBubble, // Actual response content (potentially including suggestions HTML)
            sender: 'agent', // Sender is agent
            timestamp: Date.now(), // Current timestamp
            isHTML: (actualContentForBubble.includes('<div class="final-response-suggestions">')), // Mark as HTML if suggestions were added
            rawResponseV1_3_2_CamelCase: finalCamelCaseJson, // Raw camelCase JSON response (ensure version sync)
            thinking: thinkingForBubble, // Thinking process
        });
        // Clear the cached thinking process as it has been used for the current response
        state.lastResponseThinking = null;

        // Update the current session's last activity timestamp
        if (state.sessions[state.currentSessionId]) {
            state.sessions[state.currentSessionId].lastActivity = Date.now();
        }
        // Save all session data to localStorage
        saveSessions();
        // Re-render the session list to reflect the change in activity time
        renderSessionList();

        // Get LLM interaction ID for logging
        const llmIdForLog = (finalCamelCaseJson && finalCamelCaseJson.llmInteractionId) ? finalCamelCaseJson.llmInteractionId : (llm_interaction_id || 'N/A_Final');
        // Add a log item to the process log sidebar indicating the final response has been rendered
        appendLogItem(`AI最终回复已渲染 (LLM_ID: ${llmIdForLog})`, 'fas fa-flag-checkered log-success', 'type-final_response',
            // Detailed information: if finalCamelCaseJson exists, include content summary and raw response; otherwise include error details
            finalCamelCaseJson ? { summary: (actualContentForBubble.includes('<div class="final-response-suggestions">') ? actualContentForBubble.substring(0, 120).split('<br>')[0] : actualContentForBubble.substring(0, 120)) + "...", raw_response_v1_3_2: finalCamelCaseJson } : { error_details: "响应生成指示失败或缺少有效JSON.", fallback_content_preview: (content || "(空)").substring(0,120) + "..."}
        );
        // Based on the current state of the process log sidebar, decide whether to force expansion or maintain state
        if (!state.isProcessLogSidebarVisible) showProcessLogSidebar(false); // If not visible, show but don't force expand
        else if (state.isProcessLogSidebarCollapsed) showProcessLogSidebar(false); // If already collapsed, maintain collapsed state
        else showProcessLogSidebar(true); // If already expanded, maintain expanded state (or force expand to ensure new log is seen)
    }


    // ======== 初始化应用 ========
    /**
     * 初始化整个前端应用。
     * 包括加载设置、主题、字体、会话，设置事件监听器，连接WebSocket等。
     */
    function initializeApp() {
        // 在控制台输出初始化信息，包含版本号
        console.log("CircuitManus Pro - 光绘墨迹终端 (V1.0.0 Lumina) 初始化..."); // 版本号同步

        // 加载用户设置 (如主题、字体大小等)
        loadSettings();
        // 应用当前主题
        applyCurrentTheme();
        // 应用保存的字体大小，如果未保存则使用默认 '16'
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
        // 应用动画级别
        applyAnimationLevel(state.animationLevel);
        // 加载会话数据
        loadSessions();
        // 设置所有DOM元素的事件监听器
        setupEventListeners();
        // 调整用户输入文本框的初始高度
        adjustTextareaHeight();
        // 更新字符计数器的显示
        updateCharCounter();
        // 根据保存的状态更新左侧边栏的展开/收起状态 (true 表示立即更新，无动画)
        updateSidebarState(state.isSidebarExpanded, true);
        // 根据保存的状态更新会话管理器的折叠/展开状态 (true 表示立即更新)
        updateSessionManagerState(state.isSessionManagerCollapsed, true);
        // 应用右侧固定日志侧边栏的布局
        applyFixedLogSidebarLayout();
        // 根据保存的状态更新右侧日志侧边栏的折叠状态 (true 表示立即更新)
        updateProcessLogSidebarCollapseState(state.isProcessLogSidebarCollapsed, true);
        // 根据保存的状态决定是否显示右侧日志侧边栏
        if (state.isProcessLogSidebarVisible) {
            showProcessLogSidebar(false); // 显示，但不强制展开
        } else {
            hideProcessLogSidebar(); // 隐藏
        }
        // 根据保存的状态切换3D黑洞特效的可见性
        toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);
        // 设置3D组件切换按钮的 title 属性
        dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
        // 获取并设置3D组件切换按钮的图标
        const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
        if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';

        // 连接 WebSocket 服务器
        connectWebSocket();
        // 初始化当前会话的UI (true 表示是初始加载或连接)
        initializeCurrentSessionUI(true);
        // 为聊天框中的快捷操作按钮附加事件监听器
        attachQuickActionButtonListeners(dom.chatBox);
        // Update the CSS variable for input area height
        updateInputAreaHeightVar();

        // Log that the system is ready
        console.log("光绘墨迹终端 系统就绪. 等待数据流.");
    }

    // ======== 事件监听器设置 ========
    /**
     * 设置应用中所有主要的DOM事件监听器。
     */
    function setupEventListeners() {
        // 为发送按钮添加点击事件监听器，调用 handleSendMessage 函数
        dom.sendButton.addEventListener('click', handleSendMessage);
        // 为用户输入框添加键盘按下事件监听器，调用 handleUserInputKeypress 函数
        dom.userInput.addEventListener('keypress', handleUserInputKeypress);
        // 为用户输入框添加输入事件监听器
        dom.userInput.addEventListener('input', () => {
            adjustTextareaHeight(); // 调整文本框高度
            updateCharCounter(); // 更新字符计数器
            updateInputAreaHeightVar(); // 更新输入区域高度的CSS变量
        });

        // 为主题切换按钮添加点击事件监听器
        dom.themeToggleButton.addEventListener('click', () => {
            const themes = ['auto-crystal', 'light-crystal', 'dark-crystal']; // 定义可用主题数组
            const currentIndex = themes.indexOf(state.currentTheme); // 获取当前主题在数组中的索引
            const nextTheme = themes[(currentIndex + 1) % themes.length]; // 计算下一个主题 (循环切换)
            applyTheme(nextTheme); // 应用下一个主题
            showToast(`显示模式已切换至: ${getThemeDisplayName(state.currentTheme)}`, 'info'); // 显示主题切换的 Toast 通知
        });

        // 为清除聊天按钮添加点击事件监听器，调用 handleClearCurrentChat 函数
        dom.clearChatButton.addEventListener('click', handleClearCurrentChat);
        // 如果左侧边栏切换按钮存在
        if (dom.leftSidebarToggle) {
            // 为其添加点击事件监听器，调用 updateSidebarState 函数切换侧边栏状态
            dom.leftSidebarToggle.addEventListener('click', () => updateSidebarState(!state.isSidebarExpanded));
        }

        // 为切换右侧日志侧边栏可见性按钮添加点击事件监听器
        dom.toggleProcessLogVisibilityButton.addEventListener('click', () => {
            if (state.isProcessLogSidebarVisible) hideProcessLogSidebar(); // 如果可见则隐藏
            else showProcessLogSidebar(false); // 如果隐藏则显示 (不强制展开)
        });

        // 遍历所有侧边栏按钮 (模式切换按钮等)
        dom.sidebarButtons.forEach(button => {
            // 为每个按钮添加点击事件监听器
            button.addEventListener('click', () => {
                const mode = button.dataset.mode; // 获取按钮的 data-mode 属性值
                if (mode === 'settings') openSettingsModal(); // 如果模式是 'settings'，则打开设置模态框
                else handleModeChange(mode); // 否则，调用 handleModeChange 函数切换应用模式
            });
        });

        // 为会话管理器切换按钮添加点击事件监听器，调用 updateSessionManagerState 函数切换会话列表的折叠/展开状态
        dom.sessionManagerToggle.addEventListener('click', () => updateSessionManagerState(!state.isSessionManagerCollapsed));
        // 为创建新会话按钮添加点击事件监听器，调用 createNewSession 函数
        dom.createNewSessionButton.addEventListener('click', () => createNewSession());
        // 为编辑会话名称按钮添加点击事件监听器，调用 handleEditSessionName 函数
        dom.editSessionNameButton.addEventListener('click', handleEditSessionName);

        // 为附加文件按钮添加点击事件监听器，触发文件输入框的点击事件
        dom.attachButton.addEventListener('click', () => dom.fileInput.click());
        // 为文件输入框添加 change 事件监听器，调用 handleFileSelection 函数处理文件选择
        dom.fileInput.addEventListener('change', handleFileSelection);
        // 为关闭文件预览按钮添加点击事件监听器，调用 closeFilePreview 函数
        dom.closeFilePreviewButton.addEventListener('click', closeFilePreview);
        // 为麦克风按钮添加点击事件监听器，显示一个提示信息 (当前功能可能未完全实现)
        dom.micButton.addEventListener('click', () => showToast('语音墨迹: 校准中...', 'info'));

        // 如果关闭设置按钮存在，为其添加点击事件监听器，调用 closeSettingsModal 函数 (true 表示恢复更改)
        if (dom.closeSettingsButton) dom.closeSettingsButton.addEventListener('click', () => closeSettingsModal(true));
        // 如果保存设置按钮存在，为其添加点击事件监听器
        if (dom.saveSettingsButton) dom.saveSettingsButton.addEventListener('click', () => {
            collectAndSaveSettings(); // 收集并保存设置
            closeSettingsModal(false); // 关闭设置模态框 (false 表示不恢复更改)
            showToast('系统参数已同步!', 'success'); // 显示保存成功的 Toast 通知
        });
        // 如果重置设置按钮存在，为其添加点击事件监听器，调用 resetToDefaultSettings 函数
        if (dom.resetSettingsButton) dom.resetSettingsButton.addEventListener('click', resetToDefaultSettings);

        // 如果字体大小输入框 (range slider) 存在
        if (dom.fontSizeInput) {
            // 为其添加 input 事件监听器
            dom.fontSizeInput.addEventListener('input', () => {
                const newSize = dom.fontSizeInput.value; // 获取新的字体大小值
                // 如果字体大小值显示元素存在，则更新其文本内容
                if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${newSize}px`;
                // 设置 CSS 变量 '--base-font-size' 以实时应用字体大小
                document.documentElement.style.setProperty('--base-font-size', `${newSize}px`);
            });
        }
        // 如果动画级别选择框存在，为其添加 change 事件监听器，调用 applyAnimationLevel 函数应用新级别
        if (dom.animationLevelSelect) dom.animationLevelSelect.addEventListener('change', (e) => applyAnimationLevel(e.target.value));
        // 如果自动滚动切换开关存在，为其添加 change 事件监听器，更新 state.autoScroll 的值
        if (dom.autoScrollToggle) dom.autoScrollToggle.addEventListener('change', (e) => { state.autoScroll = e.target.checked; });
        // 如果启用声音切换开关存在，为其添加 change 事件监听器，更新 state.soundEnabled 的值
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.addEventListener('change', (e) => { state.soundEnabled = e.target.checked; });
        // 如果显示聊天气泡思考切换开关存在，为其添加 change 事件监听器，更新 state.showChatBubblesThink 的值
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.addEventListener('change', (e) => { state.showChatBubblesThink = e.target.checked; });
        // 如果显示日志气泡思考切换开关存在，为其添加 change 事件监听器，更新 state.showLogBubblesThink 的值
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.addEventListener('change', (e) => { state.showLogBubblesThink = e.target.checked; });
        // 如果自动提交快捷操作切换开关存在，为其添加 change 事件监听器，更新 state.autoSubmitQuickActions 的值
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.addEventListener('change', (e) => { state.autoSubmitQuickActions = e.target.checked; });

        // 如果3D组件可见性切换开关存在
        if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.addEventListener('change', (e) => {
            state.isIdtComponentVisible = e.target.checked; // 更新状态
            toggleThreeBlackHoleVisibility(state.isIdtComponentVisible); // 切换3D组件的可见性
            // Update the title and icon of the 3D component toggle button
            dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
            const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
            if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';
            // If the visibility toggle switch in settings exists, sync its state
            if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;
            // Save the visibility state to localStorage
            localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', state.isIdtComponentVisible.toString());
        });

        // If the settings modal exists, add a click event listener to it (to close the modal when clicking outside its content)
        if (dom.settingsModal) dom.settingsModal.addEventListener('click', (e) => {
            if (e.target === dom.settingsModal) closeSettingsModal(true); // If the clicked target is the modal itself (background), close it
        });

        // Listen for system color scheme changes (for 'auto-crystal' theme)
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (state.currentTheme === 'auto-crystal') applyCurrentTheme(); // If the current theme is auto, reapply the theme
        });

        // If the process log sidebar collapse/expand button exists, add a click event listener
        if (dom.toggleProcessLogSidebarCollapseButton) dom.toggleProcessLogSidebarCollapseButton.addEventListener('click', () => toggleProcessLogSidebarCollapse());
        // If the process log sidebar close button exists, add a click event listener
        if (dom.closeProcessLogSidebarButton) dom.closeProcessLogSidebarButton.addEventListener('click', () => hideProcessLogSidebar());

        // If the 3D component toggle button and its wrapper both exist
        if (dom.idtComponentToggleBtn && dom.idtComponentWrapper) {
            // Add a click event listener to the toggle button
            dom.idtComponentToggleBtn.addEventListener('click', () => {
                // Toggle the visibility state of the 3D component (based on whether it currently has the 'is-visible' class)
                state.isIdtComponentVisible = !dom.idtComponentWrapper.classList.contains('is-visible');
                toggleThreeBlackHoleVisibility(state.isIdtComponentVisible); // Apply the new visibility
                // Update the title and icon of the button
                dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
                const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
                if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';
                // If the visibility toggle switch in settings exists, sync its state
                if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;
                // Save the visibility state to localStorage
                localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', state.isIdtComponentVisible.toString());
            });
        }

        // If the 3D component wrapper exists, add a mousedown event listener to it (for dragging)
        if (dom.idtComponentWrapper) {
            dom.idtComponentWrapper.addEventListener('mousedown', handleComponentMouseDown);
        }
        // Add a resize event listener to the window
        window.addEventListener('resize', () => {
            updateInputAreaHeightVar(); // Update the CSS variable for input area height
            applyFixedLogSidebarLayout(); // Apply the layout for the right process log sidebar
            // If Three.js is initialized and camera, renderer, and wrapper exist (for responsive canvas resizing)
            if (state.threeJsInitialized && state.threeJsCamera && state.threeJsRenderer && dom.idtComponentWrapper) {
                const Rcontainer = dom.idtComponentWrapper; // Get the 3D component container
                state.threeJsCamera.aspect = Rcontainer.clientWidth / Rcontainer.clientHeight; // Update camera aspect ratio
                state.threeJsCamera.updateProjectionMatrix(); // Update camera projection matrix
                state.threeJsRenderer.setSize(Rcontainer.clientWidth, Rcontainer.clientHeight); // Update renderer size
            }
        });

        // Add mouseover event listener to the chat box for showing the copy button
        dom.chatBox.addEventListener('mouseover', handleChatBoxMouseOver);
        // Add mouseout event listener to the chat box for hiding the copy button
        dom.chatBox.addEventListener('mouseout', handleChatBoxMouseOut);
    }

    /**
     * Initializes the Three.js black hole effect.
     * @param {HTMLElement} container - The DOM element to which the Three.js Canvas will be mounted.
     * This function is responsible for creating the Three.js scene, camera, renderer, lighting, and 3D objects.
     */
    function initThreeBlackHole(container) {
        // If Three.js is already initialized
        if (state.threeJsInitialized) {
            // And there is no current animation ID, but the component should be visible
            if (!state.threeJsAnimationId && state.isIdtComponentVisible) {
                animateThreeBlackHole(); // Restart the animation
            }
            return; // Return without re-initializing
        }
        // If the container element is not found
        if (!container) {
            console.error("Three.js: Container element not found for black hole."); // Log error message
            return; // Exit function
        }
        // If the THREE object is not defined (Three.js library is not loaded)
        if (typeof THREE === 'undefined') {
            console.error("Three.js library is not loaded."); // Log error message
            showToast("错误: 3D核心组件库未能加载。", "error", 5000); // Show error Toast
            return; // Exit function
        }

        // Create a Three.js scene
        state.threeJsScene = new THREE.Scene();
        // Create a perspective camera (field of view, aspect ratio, near clipping plane, far clipping plane)
        state.threeJsCamera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 2000);
        // Set the camera's position (move back along the Z axis to make objects visible)
        state.threeJsCamera.position.z = 60;
        // Create a WebGL renderer, enabling anti-aliasing and transparent background
        state.threeJsRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        // Set the renderer size to match the container's width and height
        state.threeJsRenderer.setSize(container.clientWidth, container.clientHeight);
        // Set the device pixel ratio for sharper rendering
        state.threeJsRenderer.setPixelRatio(window.devicePixelRatio);
        // Clear any existing canvas elements from previous initializations
        container.querySelectorAll('canvas').forEach(canvas => canvas.remove());
        // Append the renderer's DOM element (canvas) to the container
        container.appendChild(state.threeJsRenderer.domElement);

        // Create an ambient light (color, intensity)
        const ambientLight = new THREE.AmbientLight(0xaaaaaa, 0.5);
        state.threeJsScene.add(ambientLight); // Add ambient light to the scene
        // Create a point light (color, intensity, distance)
        const pointLight = new THREE.PointLight(0xffffff, 1, 500);
        pointLight.position.set(0, 20, 30); // Set the point light's position
        state.threeJsScene.add(pointLight); // Add point light to the scene

        // Create a group to hold the black hole and accretion disks, for easier manipulation
        state.threeBlackHoleGroup = new THREE.Group();
        const sphereRadius = 12; // Define the radius of the black hole sphere (event horizon)
        // Create sphere geometry (radius, width segments, height segments)
        const sphereGeometry = new THREE.SphereGeometry(sphereRadius, 48, 48);
        // Create standard mesh material (color, roughness, metalness)
        const sphereMaterial = new THREE.MeshStandardMaterial({
            color: 0x000000, roughness: 0.8, metalness: 0.1
        });
        // Create the event horizon mesh object
        const eventHorizon = new THREE.Mesh(sphereGeometry, sphereMaterial);
        state.threeBlackHoleGroup.add(eventHorizon); // Add the event horizon to the group

        // Define colors, opacity, radii, tube radii, and rotation speeds for the accretion disks
        const diskColors = [0xff6600, 0xff9933, 0xffcc66]; // Orange/Yellow shades
        const diskOpacities = [0.6, 0.7, 0.8]; // Opacity
        const diskRadii = [sphereRadius + 7, sphereRadius + 14, sphereRadius + 21]; // Torus radii
        const diskTubeRadii = [2.5, 3.5, 4.5]; // Torus tube radii
        const diskRotationSpeeds = [0.01, -0.008, 0.012]; // Rotation speeds (positive/negative indicates direction)

        // Create three accretion disks (outer, middle, inner)
        // Store references in state for animation
        state.threeAccretionDiskOuter = new THREE.Mesh(); // Initialize with dummy objects
        state.threeAccretionDiskMiddle = new THREE.Mesh();
        state.threeAccretionDiskInner = new THREE.Mesh();

        [state.threeAccretionDiskOuter, state.threeAccretionDiskMiddle, state.threeAccretionDiskInner] = diskRadii.map((radius, i) => {
            // Create Phong mesh material (suitable for highlights)
            const diskMaterial = new THREE.MeshPhongMaterial({
                color: diskColors[i], // Color
                emissive: new THREE.Color(diskColors[i]).multiplyScalar(0.5), // Emissive color (makes it look brighter)
                specular: 0x333333, // Specular color
                shininess: 20, // Shininess
                side: THREE.DoubleSide, // Render both sides
                transparent: true, // Enable transparency
                opacity: diskOpacities[i], // Opacity
                blending: THREE.AdditiveBlending // Blending mode (Additive, makes overlapping parts brighter)
            });
            // Create torus geometry (radius, tube radius, radial segments, tubular segments)
            const disk = new THREE.Mesh(new THREE.TorusGeometry(radius, diskTubeRadii[i], 16, 60), diskMaterial);
            disk.rotation.x = Math.PI / 1.8; // Adjust the tilt angle of the accretion disks (X-axis rotation)
            disk.userData.rotationSpeed = diskRotationSpeeds[i]; // Store rotation speed in userData
            state.threeBlackHoleGroup.add(disk); // Add the disk to the group
            return disk; // Return the created disk object
        });


        // Create star field background
        const starGeometry = new THREE.BufferGeometry(); // Create buffer geometry
        // Create points material (color, size, transparent, opacity, size attenuation, blending mode)
        const starMaterial = new THREE.PointsMaterial({
            color: 0xffffff, size: 0.25, transparent: true, opacity: 0.7,
            sizeAttenuation: true, blending: THREE.AdditiveBlending
        });
        const starVertices = []; // Array to store star vertex coordinates
        // Generate random coordinates for 3000 stars
        for (let i = 0; i < 3000; i++) {
            const x = THREE.MathUtils.randFloatSpread(500); // X coordinate in [-250, 250] range
            const y = THREE.MathUtils.randFloatSpread(500); // Y coordinate in [-250, 250] range
            const z = THREE.MathUtils.randFloatSpread(500); // Z coordinate in [-250, 250] range
            starVertices.push(x, y, z); // Add coordinates to the array
        }
        // Set the 'position' attribute of the geometry (vertex coordinates)
        starGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starVertices, 3));
        // Create the star points object
        state.threeStarField = new THREE.Points(starGeometry, starMaterial);
        state.threeJsScene.add(state.threeStarField); // Add the star field to the scene

        // Add the entire black hole group (containing event horizon and accretion disks) to the scene
        state.threeJsScene.add(state.threeBlackHoleGroup);
        // Mark Three.js as initialized
        state.threeJsInitialized = true;
        // Start the animation loop
        animateThreeBlackHole();
        // Log successful initialization
        console.log("Three.js black hole initialized successfully.");
    }

    /**
     * Three.js黑洞动画循环。
     * 此函数使用 requestAnimationFrame 来持续渲染和更新3D场景中的对象动画。
     */
    function animateThreeBlackHole() {
        // If Three.js is not initialized or component is not visible, stop animation
        if (!state.threeJsInitialized || !state.isIdtComponentVisible) {
            // If animation ID exists, cancel the animation frame request
            if (state.threeJsAnimationId) cancelAnimationFrame(state.threeJsAnimationId);
            state.threeJsAnimationId = null; // Set animation ID to null
            return; // Exit function
        }
        // Request the next animation frame and store the returned ID for potential cancellation
        state.threeJsAnimationId = requestAnimationFrame(animateThreeBlackHole);

        // If the black hole group exists, make it rotate slowly
        if (state.threeBlackHoleGroup) {
            state.threeBlackHoleGroup.rotation.y += 0.0015; // Rotate around Y axis
            state.threeBlackHoleGroup.rotation.x += 0.0007; // Rotate around X axis (slight wobble)
        }
        // If the outer accretion disk exists, rotate it around Z axis based on its stored speed
        if (state.threeAccretionDiskOuter) state.threeAccretionDiskOuter.rotation.z += state.threeAccretionDiskOuter.userData.rotationSpeed;
        // If the middle accretion disk exists, rotate it around Z axis based on its stored speed
        if (state.threeAccretionDiskMiddle) state.threeAccretionDiskMiddle.rotation.z += state.threeAccretionDiskMiddle.userData.rotationSpeed;
        // If the inner accretion disk exists, rotate it around Z axis based on its stored speed
        if (state.threeAccretionDiskInner) state.threeAccretionDiskInner.rotation.z += state.threeAccretionDiskInner.userData.rotationSpeed;
        // If the star field background exists, make it rotate slowly
        if (state.threeStarField) {
            state.threeStarField.rotation.x += 0.0001; // Rotate around X axis
            state.threeStarField.rotation.y += 0.00015; // Rotate around Y axis
        }
        // If renderer, scene, and camera exist, perform the rendering operation
        if (state.threeJsRenderer && state.threeJsScene && state.threeJsCamera) {
            state.threeJsRenderer.render(state.threeJsScene, state.threeJsCamera);
        }
    }

    /**
     * 控制Three.js场景的显隐和动画启停。
     * @param {boolean} isVisible - 是否显示3D组件。
     */
    function toggleThreeBlackHoleVisibility(isVisible) {
        // If the 3D component wrapper element does not exist, return
        if (!dom.idtComponentWrapper) return;
        // Toggle the 'is-visible' CSS class on the wrapper element based on the isVisible parameter
        dom.idtComponentWrapper.classList.toggle('is-visible', isVisible);
        // Update the isIdtComponentVisible flag in the state
        state.isIdtComponentVisible = isVisible;
        // If the component should be visible
        if (isVisible) {
            // If Three.js is not yet initialized
            if (!state.threeJsInitialized) {
                initThreeBlackHole(dom.idtComponentWrapper); // Initialize the Three.js effect
            } else if (!state.threeJsAnimationId) { // If already initialized but animation is not running
                animateThreeBlackHole(); // Start the animation
            }
        } else { // If the component should be hidden
            // If the animation ID exists (i.e., animation is running)
            if (state.threeJsAnimationId) {
                cancelAnimationFrame(state.threeJsAnimationId); // Cancel the animation frame request, stop the animation
                state.threeJsAnimationId = null; // Set animation ID to null
            }
        }
        // Save the component's visibility state to localStorage
        localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', isVisible.toString());
    }

    /**
     * 处理鼠标悬停在聊天框消息气泡上以显示复制按钮的事件。
     * @param {MouseEvent} event - 鼠标事件对象。
     */
    function handleChatBoxMouseOver(event) {
        // Find the target element of the mouseover event or its nearest '.message-agent .message-bubble' parent element
        const targetMessageBubble = event.target.closest('.message-agent .message-bubble');
        // If a target message bubble is found (i.e., mouse is hovering over an Agent message bubble)
        if (targetMessageBubble) {
            // Try to get an existing copy button within the bubble
            let copyButton = targetMessageBubble.querySelector('.copy-llm-response-btn');
            // If the copy button does not exist
            if (!copyButton) {
                // Create a new copy button element
                copyButton = document.createElement('button');
                copyButton.className = 'copy-llm-response-btn icon-btn'; // Set the button's class name
                copyButton.innerHTML = '<i class="fas fa-copy"></i>'; // Set the button's icon
                copyButton.title = '复制回复内容'; // Set the button's tooltip
                // Add a click event listener to the copy button, calling handleCopyLlmResponse
                copyButton.addEventListener('click', handleCopyLlmResponse);
                // Append the copy button to the message bubble
                targetMessageBubble.appendChild(copyButton);
            }
            // Set the opacity and visibility of the copy button to make it visible
            copyButton.style.opacity = '1';
            copyButton.style.visibility = 'visible';
        }
    }

    /**
     * 处理鼠标移出聊天框消息气泡以隐藏复制按钮的事件。
     * @param {MouseEvent} event - 鼠标事件对象。
     */
    function handleChatBoxMouseOut(event) {
        // Find the target element of the mouseout event or its nearest '.message-agent .message-bubble' parent element
        const targetMessageBubble = event.target.closest('.message-agent .message-bubble');
        // If a target message bubble is found
        if (targetMessageBubble) {
            // Get the copy button within the bubble
            const copyButton = targetMessageBubble.querySelector('.copy-llm-response-btn');
            // Check if the copy button exists, and the related target (element mouse is moving to) is not the bubble itself or the button itself or a child of the button
            // This prevents the button from being hidden incorrectly when moving from the bubble to the button
            if (copyButton && !targetMessageBubble.contains(event.relatedTarget) && event.relatedTarget !== copyButton && !copyButton.contains(event.relatedTarget)) {
                // Set the opacity and visibility of the copy button to hide it
                copyButton.style.opacity = '0';
                copyButton.style.visibility = 'hidden';
            }
        } else {
            // If the mouse moved out of the entire chat box (targetMessageBubble is null), hide copy buttons in all Agent message bubbles
            dom.chatBox.querySelectorAll('.message-agent .message-bubble .copy-llm-response-btn').forEach(btn => {
                btn.style.opacity = '0';
                btn.style.visibility = 'hidden';
            });
        }
    }

    /**
     * 处理点击LLM回复消息气泡中的复制按钮的事件。
     * @param {MouseEvent} event - 点击事件对象。
     * 此函数将消息内容复制到用户剪贴板。
     */
    function handleCopyLlmResponse(event) {
        // Prevent event propagation to higher elements (e.g., the message bubble's parent)
        event.stopPropagation();
        // Get the clicked button element
        const button = event.currentTarget;
        // Find the nearest message bubble element containing the button
        const messageBubble = button.closest('.message-bubble');
        // Find the element containing the text content within the message bubble
        const textContentDiv = messageBubble.querySelector('.message-text-content');

        // If the text content element is found
        if (textContentDiv) {
            // Extract plain text from the HTML content, first replacing <br> tags with newline characters \n
            let textToCopy = textContentDiv.innerHTML.replace(/<br\s*\/?>/gi, '\n');
            // Create a temporary div element for further cleaning of HTML tags to get pure text
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = textToCopy; // Put the text containing newlines (potentially still with other HTML) into the temporary div
            textToCopy = tempDiv.textContent || tempDiv.innerText || ""; // Get the pure text content

            // Remove the "下一步行动投影:" section and its content from the text if it exists
            const suggestionIndex = textToCopy.indexOf("下一步行动投影:");
            if (suggestionIndex !== -1) {
                textToCopy = textToCopy.substring(0, suggestionIndex).trim(); // Truncate and remove trailing whitespace
            }

            // Use the browser's Clipboard API to copy the processed plain text to the clipboard
            navigator.clipboard.writeText(textToCopy.trim())
                .then(() => {
                    // Callback on successful copy
                    showToast('回复已复制到剪贴板!', 'success', 2000); // Show success Toast notification
                    button.innerHTML = '<i class="fas fa-check"></i>'; // Change button icon to checkmark
                    // Restore button icon to copy icon after 1.5 seconds
                    setTimeout(() => { button.innerHTML = '<i class="fas fa-copy"></i>'; }, 1500);
                })
                .catch(err => {
                    // Callback on copy failure
                    console.error('无法复制文本: ', err); // Log error to console
                    showToast('复制失败!', 'error'); // Show failure Toast notification
                });
        }
    }

    /**
     * 处理3D组件容器的鼠标按下事件，用于开始拖动。
     * @param {MouseEvent} e - 鼠标按下事件对象。
     */
    function handleComponentMouseDown(e) {
        // If the 3D component is not visible, or if the clicked button is not the left mouse button (button !== 0), do not start dragging
        if (!dom.idtComponentWrapper.classList.contains('is-visible') || e.button !== 0) { return; }
        // Set dragging state to true
        state.isDraggingComponent = true;
        // Change the mouse cursor style for the 3D component container to 'grabbing'
        dom.idtComponentWrapper.style.cursor = 'grabbing';
        // Disable page text selection to prevent selecting text while dragging
        document.body.style.userSelect = 'none';
        // Get the computed styles of the document root element
        const styles = getComputedStyle(document.documentElement);
        // Get the current top and left offset percentages stored in CSS variables, default to 0 if not found
        const currentTopPercent = parseFloat(styles.getPropertyValue('--idt-offset-top-percentage').replace('%', '')) || 0;
        const currentLeftPercent = parseFloat(styles.getPropertyValue('--idt-offset-left-percentage').replace('%', '')) || 0;
        // Calculate the initial top position (in pixels) at the start of dragging
        // Prioritize any existing inline pixel value, otherwise calculate from percentage and window height
        state.componentInitialTopPx = (dom.idtComponentWrapper.style.top && dom.idtComponentWrapper.style.top.endsWith('px'))
            ? parseFloat(dom.idtComponentWrapper.style.top) // Use the inline px value if present
            : (currentTopPercent / 100) * window.innerHeight; // Otherwise calculate from percentage
        // Calculate the initial left position (in pixels) at the start of dragging
        // Logic is the same as above
        state.componentInitialLeftPx = (dom.idtComponentWrapper.style.left && dom.idtComponentWrapper.style.left.endsWith('px'))
            ? parseFloat(dom.idtComponentWrapper.style.left)
            : (currentLeftPercent / 100) * window.innerWidth;
        // Record the mouse's X coordinate at the moment of pressing
        state.componentDragStartX = e.clientX;
        // Record the mouse's Y coordinate at the moment of pressing
        state.componentDragStartY = e.clientY;
        // Add a mousemove event listener to the document
        document.addEventListener('mousemove', handleComponentMouseMove);
        // Add a mouseup event listener to the document
        document.addEventListener('mouseup', handleComponentMouseUp);
        // Add a mouseleave event listener to the document (handles case where mouse leaves browser window while dragging)
        document.addEventListener('mouseleave', handleComponentMouseUp);
        // Prevent the default mouse down behavior (e.g., image dragging)
        e.preventDefault();
    }
    /**
     * Handles the mousemove event during 3D component dragging.
     * @param {MouseEvent} e - The mousemove event object.
     */
    function handleComponentMouseMove(e) {
        // If not currently dragging, do nothing
        if (!state.isDraggingComponent) return;
        // Calculate the distance the mouse moved in the X direction
        const deltaX = e.clientX - state.componentDragStartX;
        // Calculate the distance the mouse moved in the Y direction
        const deltaY = e.clientY - state.componentDragStartY;
        // Calculate the new top position (in pixels)
        let newTopPx = state.componentInitialTopPx + deltaY;
        // Calculate the new left position (in pixels)
        let newLeftPx = state.componentInitialLeftPx + deltaX;
        // Get the bounding box information of the 3D component container (primarily for width and height)
        const componentRect = dom.idtComponentWrapper.getBoundingClientRect();
        // Get the viewport width and height
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        // Clamp the new top position within the viewport (from 0 to viewport height - component height)
        newTopPx = Math.max(0, Math.min(newTopPx, viewportHeight - componentRect.height));
        // Clamp the new left position within the viewport (from 0 to viewport width - component width)
        newLeftPx = Math.max(0, Math.min(newLeftPx, viewportWidth - componentRect.width));
        // Apply the new top position (via inline style)
        dom.idtComponentWrapper.style.top = `${newTopPx}px`;
        // Apply the new left position (via inline style)
        dom.idtComponentWrapper.style.left = `${newLeftPx}px`;
    }
    /**
     * Handles the mouseup event when dragging of the 3D component ends.
     */
    function handleComponentMouseUp() {
        // If not currently dragging, do nothing
        if (!state.isDraggingComponent) return;
        // Set dragging state to false
        state.isDraggingComponent = false;
        // Restore the mouse cursor style for the 3D component container to 'grab'
        dom.idtComponentWrapper.style.cursor = 'grab';
        // Restore page text selection ability
        document.body.style.userSelect = '';
        // Remove the mousemove event listener from the document
        document.removeEventListener('mousemove', handleComponentMouseMove);
        // Remove the mouseup event listener from the document
        document.removeEventListener('mouseup', handleComponentMouseUp);
        // Remove the mouseleave event listener from the document
        document.removeEventListener('mouseleave', handleComponentMouseUp);
        // Convert the final pixel position to percentage and store it
        // Get the final top position (in pixels), default to 0 if not present in inline style
        const finalTopPx = parseFloat(dom.idtComponentWrapper.style.top) || 0;
        // Get the final left position (in pixels), default to 0 if not present in inline style
        const finalLeftPx = parseFloat(dom.idtComponentWrapper.style.left) || 0;
        // Get the viewport width and height
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        // Calculate the component width as a percentage of the viewport width
        const componentWidthPercent = (dom.idtComponentWrapper.offsetWidth / viewportWidth) * 100;
        // Calculate the component height as a percentage of the viewport height
        const componentHeightPercent = (dom.idtComponentWrapper.offsetHeight / viewportHeight) * 100;
        // Calculate the new top position percentage
        let newTopPercent = (finalTopPx / viewportHeight) * 100;
        // Calculate the new left position percentage
        let newLeftPercent = (finalLeftPx / viewportWidth) * 100;
        // Re-clamp the percentages within a reasonable range to prevent the component from partially moving out of the viewport
        newTopPercent = Math.max(0, Math.min(newTopPercent, 100 - componentHeightPercent));
        newLeftPercent = Math.max(0, Math.min(newLeftPercent, 100 - componentWidthPercent));
        // Update CSS variables to store the new percentage position
        document.documentElement.style.setProperty('--idt-offset-top-percentage', `${newTopPercent.toFixed(2)}%`);
        document.documentElement.style.setProperty('--idt-offset-left-percentage', `${newLeftPercent.toFixed(2)}%`);
        // Clear the inline top and left styles, allowing CSS variables to take effect and avoiding using old px values on the next drag
        dom.idtComponentWrapper.style.top = '';
        dom.idtComponentWrapper.style.left = '';
        // Save the new percentage position to localStorage for persistence
        localStorage.setItem(APP_PREFIX + 'idtComponentTopPercent', `${newTopPercent.toFixed(2)}%`);
        localStorage.setItem(APP_PREFIX + 'idtComponentLeftPercent', `${newLeftPercent.toFixed(2)}%`);
    }

    /**
     * 更新用户输入框下方的字符计数器。
     */
    function updateCharCounter() {
        // 获取用户输入框当前内容的长度
        const currentLength = dom.userInput.value.length;
        // 更新字符计数器元素的文本内容，格式为 "当前长度/最大长度"
        dom.charCounter.textContent = `${currentLength}/${state.maxInputChars}`;
        // 移除字符计数器上可能存在的 'warn' 和 'error' CSS 类
        dom.charCounter.classList.remove('warn', 'error');
        // 如果当前长度超过最大限制
        if (currentLength > state.maxInputChars) {
            // 添加 'error' CSS 类，通常会显示为红色
            dom.charCounter.classList.add('error');
        } else if (currentLength > state.maxInputChars * 0.9) { // 如果当前长度超过最大限制的90%
            // 添加 'warn' CSS 类，通常会显示为黄色或橙色
            dom.charCounter.classList.add('warn');
        }
    }

    /**
     * 生成唯一的会话ID。
     * @returns {string} 生成的会话ID。
     * 格式为 "session_lumina_" + 当前时间戳(36进制) + "_" + 随机字符串(36进制，10位)
     */
    function generateSessionId() {
        return `session_lumina_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 12)}`;
    }
    /**
     * 生成唯一的客户端请求ID。
     * @returns {string} 生成的请求ID。
     * 格式为 "creq_lumina_proc_" + 当前时间戳(36进制) + "_" + 随机字符串(36进制，8位)
     */
    function generateClientRequestId() {
        return `creq_lumina_proc_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 10)}`;
    }

    /**
     * 初始化当前会话的用户界面。
     * 如果存在上次会话ID且有效，则加载该会话；否则加载最近活动的会话或创建新会话。
     * @param {boolean} [isInitialLoadOrConnect=false] - 是否是应用初始加载或WebSocket重连。
     */
    function initializeCurrentSessionUI(isInitialLoadOrConnect = false) {
        // 从 localStorage 获取上次使用的会话 ID
        const lastSessionId = localStorage.getItem(APP_PREFIX + 'lastSessionId');
        // 优先使用当前 state 中的 currentSessionId (可能由 WebSocket 的 init_success 消息设置)
        let targetSessionId = state.currentSessionId;
        // 如果 state 中没有 currentSessionId
        if (!targetSessionId) {
            // 尝试从 localStorage 恢复，并检查该会话是否存在于当前加载的会话数据中
            if (lastSessionId && state.sessions[lastSessionId]) {
                targetSessionId = lastSessionId; // 使用 localStorage 中的会话 ID
            } else if (Object.keys(state.sessions).length > 0) { // 如果 localStorage 中的无效，则尝试使用最近活动的会话
                // 将所有会话按最后活动时间降序排列
                const sortedSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
                targetSessionId = sortedSessions[0].id; // 选择最近活动的会话
            }
        }
        // 如果经过以上步骤仍然没有找到有效的会话 ID，或者找到的 ID 在当前会话数据中不存在
        if (!targetSessionId || !state.sessions[targetSessionId]) {
            // 创建一个新的会话，isInitialCreation = true 表示这是初始化时创建，避免不必要的立即UI切换
            targetSessionId = createNewSession(true);
        }
        // 切换到目标会话，并传递 isInitialLoadOrConnect 标志
        switchSession(targetSessionId, isInitialLoadOrConnect);
    }

    /**
     * 创建一个新的会话。
     * @param {boolean} [isInitialCreation=false] - 是否是在应用初始化时创建（避免不必要的UI切换）。
     * @returns {string} 新创建的会话ID。
     */
    function createNewSession(isInitialCreation = false) {
        // 生成一个新的唯一会话 ID
        const newId = generateSessionId();
        // 获取当前时间戳
        const now = Date.now();
        // 计算新会话的序号 (基于当前已有的会话数量)
        const sessionCount = Object.keys(state.sessions).length + 1;
        // 在 state.sessions 中创建新的会话对象
        state.sessions[newId] = {
            id: newId, // 会话 ID
            name: `光绘墨迹项目 ${sessionCount}`, // 默认会话名称，包含序号
            messages: [], // 消息列表，初始为空
            createdAt: now, // 创建时间
            lastActivity: now, // 最后活动时间
        };
        saveSessions(); // 将更新后的会话数据保存到 localStorage
        // 如果不是在应用初始化时创建 (即用户主动创建)
        if (!isInitialCreation) {
            // 立即切换到这个新创建的会话
            switchSession(newId, false); // false 表示不是初始加载
            showToast('新光绘墨迹项目已创建!', 'success'); // 显示创建成功的 Toast 通知
            // 如果左侧边栏未展开，则展开它
            if (!state.isSidebarExpanded) updateSidebarState(true);
            // 如果会话管理器是折叠的，则展开它
            if (state.isSessionManagerCollapsed) updateSessionManagerState(false);
        }
        // 返回新创建的会话 ID
        return newId;
    }

    /**
     * 切换到指定的会话。
     * @param {string} sessionId - 要切换到的会话ID。
     * @param {boolean} [isInitialLoadOrConnect=false] - 是否是应用初始加载或WebSocket重连。
     * 此函数负责更新UI以显示选定会话的内容。
     */
    function switchSession(sessionId, isInitialLoadOrConnect = false) {
        // 安全检查：如果目标会话 ID 在 state.sessions 中不存在
        if (!state.sessions[sessionId]) {
            console.error(`尝试切换到不存在的会话: ${sessionId}. 创建一个 fallback 会话.`); // 打印错误信息
            // 创建一个新的会话作为后备 (isInitialCreation = true 避免递归调用 switchSession)
            const fallbackId = createNewSession(true);
            state.currentSessionId = fallbackId; // 更新当前会话 ID 为后备会话的 ID
        } else {
            // 如果目标会话存在，则更新当前会话 ID
            state.currentSessionId = sessionId;
        }

        // 如果不是初始加载/连接，并且 WebSocket 已连接并处于打开状态
        if (!isInitialLoadOrConnect && websocket && websocket.readyState === WebSocket.OPEN) {
            // 向后端发送 'init' 消息，通知后端当前会话已更改
            sendWebSocketMessage({ type: 'init', session_id: state.currentSessionId });
        }

        // 将当前会话 ID 保存到 localStorage，作为“最后活动会话”
        localStorage.setItem(APP_PREFIX + 'lastSessionId', state.currentSessionId);
        // 如果当前会话对象存在于 state.sessions 中
        if (state.sessions[state.currentSessionId]) {
            // Update the last activity timestamp for this session to the current time
            state.sessions[state.currentSessionId].lastActivity = Date.now();
        }
        // Save all session data to localStorage
        saveSessions();

        // Update UI elements to reflect the current session:
        // Set the text content of the current session name display area, default to "初始化墨迹..." if session does not exist
        dom.currentSessionNameDisplay.textContent = state.sessions[state.currentSessionId]?.name || "初始化墨迹...";
        // Clear the existing content of the chat box
        dom.chatBox.innerHTML = '';

        // Render messages or welcome message for the current session:
        // If the message list of the current session is empty
        if (state.sessions[state.currentSessionId]?.messages.length === 0) {
            appendWelcomeMessage(); // Display the welcome message
        } else {
            // If there are messages, iterate through them and append to the chat box
            state.sessions[state.currentSessionId]?.messages.forEach(msg => {
                // Use the message object's properties when appending
                appendMessage(msg.content, msg.sender, msg.isHTML, msg.thinking, true, msg.attachments, msg.errorType); // true indicates switching session, loading history
            });
        }
        scrollToBottom(true); // Scroll the chat box to the bottom (true for instant scroll)
        renderSessionList(); // Re-render the session list (to update the active session's style etc.)
        dom.userInput.focus(); // Set focus to the input box

        // Clear and handle the right process log sidebar
        if (dom.processLogSidebarContent) dom.processLogSidebarContent.innerHTML = ''; // Clear log content
        // Depending on its current visibility state, decide whether to show or hide it
        if (state.isProcessLogSidebarVisible) {
            showProcessLogSidebar(false); // If visible, re-show (do not force expand)
        } else {
            hideProcessLogSidebar(); // If not visible, keep hidden
        }

        // Log the switched session information to the console
        console.log(`切换到光绘墨迹项目: ${state.sessions[state.currentSessionId]?.name} (ID: ${state.currentSessionId})`);
        // Update the placeholder text of the user input box, including current mode and current project name
        const currentSessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
        dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${currentSessionNameForPlaceholder})...`;
    }

    /**
     * 删除指定的会话。
     * @param {string} sessionId - 要删除的会话ID。
     * @param {Event} [event] - 可选的点击事件对象，用于阻止事件冒泡。
     */
    function deleteSession(sessionId, event) {
        // If an event object is provided (typically a click event), prevent event propagation
        // This prevents triggering the parent element's click event (which switches sessions) when clicking the delete button
        if (event) event.stopPropagation();
        // If the session ID to be deleted does not exist in state.sessions, return without doing anything
        if (!state.sessions[sessionId]) return;
        // Get the name of the session to be deleted for the confirmation prompt
        const sessionName = state.sessions[sessionId].name;
        // Show a confirmation dialog asking the user if they are sure they want to delete the current session's chat history
        if (!confirm(`归档光绘墨迹项目 "${sessionName}" (ID: ${sessionId})? 此操作不可逆转.`)) {
            return; // If the user cancels, return
        }
        // Find and get the corresponding session list item element from the DOM
        const listItem = dom.sessionList.querySelector(`li[data-session-id="${sessionId}"]`);
        // If the list item element is found
        if (listItem) {
            // If animations are enabled (state.animationLevel is not 'none')
            if (state.animationLevel !== 'none') {
                // Add Animate.css exit animation class
                listItem.classList.add('animate__animated', 'animate__zoomOutLeft');
                // Set the animation duration
                listItem.style.setProperty('--animate-duration', '0.4s');
                // Listen for the animation end event, remove the list item element after the animation finishes (once: true means the event triggers only once)
                listItem.addEventListener('animationend', () => listItem.remove(), { once: true });
            } else {
                // If animations are not enabled, remove the list item element directly
                listItem.remove();
            }
        }
        // Delete the session data from the state.sessions object
        delete state.sessions[sessionId];
        // Check if the deleted session was the currently active session
        if (state.currentSessionId === sessionId) {
            // If it was the current session, need to switch to another session or create a new one
            // Get the remaining sessions, sorted by last activity timestamp in descending order
            const remainingSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
            // If there are other sessions remaining
            if (remainingSessions.length > 0) {
                // Switch to the most recently active session
                switchSession(remainingSessions[0].id, false);
            } else {
                // If there are no other sessions remaining, create a new fallback session
                const newFallbackId = createNewSession(true); // true indicates not to immediately switch UI
                switchSession(newFallbackId, false); // Then switch to this new session
            }
        } else {
            // If the deleted session was not the current session, just save the updated session data and re-render the session list
            saveSessions();
            renderSessionList();
        }
        // Show a Toast notification informing the user that the session has been archived (deleted)
        showToast(`光绘墨迹项目 "${sessionName}" 已归档.`, 'info');
        // If all sessions have been deleted, ensure the session list displays the empty state (done by re-rendering)
        if (Object.keys(state.sessions).length === 0 && dom.sessionList) renderSessionList();
    }

    /**
     * 处理编辑当前会话名称的逻辑。
     * 弹出提示框让用户输入新名称，并更新状态和UI。
     */
    function handleEditSessionName() {
        // Get the current active session object
        const currentSession = state.sessions[state.currentSessionId];
        // If there is no current active session, do nothing
        if (!currentSession) return;
        // Use the prompt dialog to ask the user to enter a new session name, with the current name as default value
        const newName = prompt(`重命名光绘墨迹项目 "${currentSession.name}":`, currentSession.name);
        // If the user entered a new name (newName is not null), and the new name after trimming whitespace is not empty, and it is different from the original name
        if (newName && newName.trim() !== "" && newName.trim() !== currentSession.name) {
            // Update the current session's name, limiting the length to 70 characters
            currentSession.name = newName.trim().substring(0, 70);
            // Update the current session's last activity timestamp
            currentSession.lastActivity = Date.now();
            // Update the UI element displaying the current session name
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            // Save all session data (because the name has changed)
            saveSessions();
            // Re-render the session list to reflect the name change
            renderSessionList();
            // Show a Toast notification informing the user that the name has been updated
            showToast("光绘墨迹项目名称已更新.", "success");
            // Update the placeholder text of the user input box to reflect the new session name
            const currentSessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
            dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${currentSessionNameForPlaceholder})...`;
        }
    }

    /**
     * Renders the session list to the UI.
     * Dynamically creates list items based on the data in `state.sessions`.
     */
    function renderSessionList() {
        // If the session list container element (ul) does not exist, do nothing
        if (!dom.sessionList) return;
        // Clear the existing content of the session list container
        dom.sessionList.innerHTML = '';
        // Get all session data and sort it by last activity timestamp in descending order
        const sortedSessions = Object.values(state.sessions)
            .sort((a, b) => b.lastActivity - a.lastActivity);

        // If the sorted session list has a length of 0 (i.e., no sessions)
        if (sortedSessions.length === 0) {
            // Create a list item representing "no sessions"
            const emptyItem = document.createElement('li');
            emptyItem.classList.add('session-list-empty'); // Add specific CSS class
            // Set its content, including an icon and text
            emptyItem.innerHTML = '<i class="fas fa-folder-open"></i> 无光绘项目';
            dom.sessionList.appendChild(emptyItem); // Add this item to the session list container
            return; // End function execution
        }

        // Iterate through each session data in the sorted list
        sortedSessions.forEach(session => {
            // Create a list item (li) element for each session
            const listItem = document.createElement('li');
            listItem.classList.add('session-list-item'); // Add base CSS class
            // If the current session being iterated is the active session, add the 'active-session' CSS class for highlighting
            if (session.id === state.currentSessionId) {
                listItem.classList.add('active-session');
            }
            // Store the session ID in the data-session-id attribute of the list item for easy access later
            listItem.dataset.sessionId = session.id;

            // Format the session's last activity time and creation time
            const lastActivityDate = new Date(session.lastActivity);
            const createdDate = new Date(session.createdAt);
            // Format the last activity timestamp into a user-friendly relative time string (e.g., "just now", "5 min ago")
            const timeSinceLastActivity = formatTimeSince(session.lastActivity);

            // Set the title attribute (tooltip) of the list item, showing detailed last modified time and creation time
            listItem.title = `最后修改: ${timeSinceLastActivity} (${lastActivityDate.toLocaleString()})\n创建于: ${createdDate.toLocaleDateString()}`;

            // Create a div to wrap the session name and time information for layout purposes
            const contentWrapper = document.createElement('div');
            contentWrapper.classList.add('session-item-content');

            // Create a span to display the session name
            const nameSpan = document.createElement('span');
            nameSpan.classList.add('session-name');
            nameSpan.textContent = session.name; // Set the session name

            // Create a span to display the relative activity time
            const timeSpan = document.createElement('span');
            timeSpan.classList.add('session-time');
            timeSpan.textContent = timeSinceLastActivity; // Set the time text

            // Append the name and time spans to the content wrapper
            contentWrapper.appendChild(nameSpan);
            contentWrapper.appendChild(timeSpan);

            // Create a delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.classList.add('session-delete-btn', 'icon-btn'); // Add CSS classes
            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>'; // Set the button icon
            deleteBtn.title = "归档此光绘项目"; // Set the tooltip
            // Add a click event listener to the delete button, calling the deleteSession function, passing the session ID and event object
            deleteBtn.addEventListener('click', (e) => deleteSession(session.id, e));

            // Append the content wrapper and delete button to the list item
            listItem.appendChild(contentWrapper);
            listItem.appendChild(deleteBtn);

            // Add a click event listener to the entire list item
            listItem.addEventListener('click', () => {
                // If the clicked session is not the currently active session, switch to it
                if (state.currentSessionId !== session.id) switchSession(session.id, false);
            });
            // Append the created list item to the session list container (ul)
            dom.sessionList.appendChild(listItem);
        });
    }

    /**
     * Formats a timestamp into a user-friendly relative time string.
     * @param {number} dateTimestamp - The timestamp.
     * @returns {string} The formatted time string (e.g., "just now", "5 min ago", "yesterday", "10/26/2023").
     */
    function formatTimeSince(dateTimestamp) {
        const now = new Date(); // Get current time
        // Calculate the number of seconds passed since the given timestamp
        const secondsPast = (now.getTime() - dateTimestamp) / 1000;

        // Return different time formats based on the number of seconds passed
        if (secondsPast < 60) return '刚刚'; // Within 1 minute
        if (secondsPast < 3600) return `${Math.round(secondsPast / 60)}分前`; // Within 1 hour, show minutes
        if (secondsPast <= 86400) return `${Math.round(secondsPast / 3600)}时前`; // Within 24 hours, show hours

        // Calculate the number of days passed
        const daysPast = Math.round(secondsPast / 86400);
        if (daysPast === 1) return '昨天'; // 1 day ago
        if (daysPast < 7) return `${daysPast}天前`; // Within 7 days, show days

        // If more than 7 days ago
        const date = new Date(dateTimestamp); // Convert timestamp to Date object
        // If it's the same year, show month and day (e.g., "Oct 26")
        if (now.getFullYear() === date.getFullYear()) {
            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        }
        // If it's a different year, show year, month, day (e.g., "23/Oct/26")
        return date.toLocaleDateString(undefined, { year: '2-digit', month: 'short', day: 'numeric' });
    }

    /**
     * Saves all current session data to localStorage.
     */
    function saveSessions() {
        try {
            // Convert the state.sessions object to a JSON string and store it in localStorage
            // Use APP_PREFIX as the key name to avoid conflicts with other applications or older versions
            localStorage.setItem(APP_PREFIX + 'sessions', JSON.stringify(state.sessions));
        } catch (e) {
            // If an error occurs during storage (e.g., localStorage is full)
            console.error("Error saving session data (墨迹归档不稳定):", e); // Log the error to the console
            showToast("未能持久化会话数据. 归档异常.", "error"); // Show a Toast notification informing the user
        }
    }

    /**
     * Loads session data from localStorage.
     */
    function loadSessions() {
        // Get the stored session data string from localStorage
        const storedSessions = localStorage.getItem(APP_PREFIX + 'sessions');
        // Initialize state.sessions to an empty object in case loading fails or there is no data
        state.sessions = {};
        // If session data exists in localStorage
        if (storedSessions) {
            try {
                // Parse the JSON string into an object
                const parsedSessions = JSON.parse(storedSessions);
                // Iterate through each key (session ID) of the parsed sessions object
                Object.keys(parsedSessions).forEach(id => {
                    const s = parsedSessions[id]; // Get the individual session object
                    // Validate the basic structure of the session object
                    if (s && typeof s.id === 'string' && typeof s.name === 'string' && Array.isArray(s.messages)) {
                        // If the structure is valid, add it to state.sessions
                        state.sessions[id] = {
                            id: s.id, // Session ID
                            name: s.name || "已归档项目", // Session name, use fallback name if empty
                            // Map and validate each message object in the messages array
                            messages: s.messages.map(m => ({
                                content: m.content || "", // Message content, empty string if null/undefined
                                sender: m.sender || "system", // Sender, defaults to "system" if null/undefined
                                timestamp: m.timestamp || Date.now(), // Timestamp, defaults to current time if null/undefined
                                isHTML: m.isHTML || false, // Is HTML content, defaults to false if null/undefined
                                attachments: m.attachments || [], // List of attachments, empty array if null/undefined
                                thinking: m.thinking || null, // Thinking process, null if null/undefined
                                rawResponseV1_3_2_CamelCase: m.rawResponseV1_3_2_CamelCase, // Raw camelCase JSON response (ensure version sync)
                                errorType: m.errorType, // Error type (may be undefined)
                            })),
                            createdAt: s.createdAt || Date.now(), // Creation timestamp, defaults to current time if null/undefined
                            lastActivity: s.lastActivity || Date.now(), // Last activity timestamp, defaults to current time if null/undefined
                        };
                    } else {
                        // If the session object structure is corrupted, log a warning
                        console.warn("发现损坏的光绘墨迹归档数据, 已跳过:", id, s);
                    }
                });
            } catch (e) {
                // If an error occurs while parsing the JSON string
                console.error("加载或解析会话数据失败 (归档损坏):", e); // Log the error to the console
                state.sessions = {}; // Reset state.sessions to an empty object
                localStorage.removeItem(APP_PREFIX + 'sessions'); // Remove the corrupted data from localStorage
                showToast("加载归档数据失败. 数据可能已损坏.", "error"); // Show a Toast notification
            }
        }
    }

    /**
     * Updates the expanded/collapsed state of the left sidebar.
     * @param {boolean} expand - Whether to expand or collapse.
     * @param {boolean} [instant=false] - Whether to update instantly without animation.
     */
    function updateSidebarState(expand, instant = false) {
        // Update the sidebar expanded state in the state
        state.isSidebarExpanded = expand;
        // Toggle the 'expanded' CSS class on the sidebar DOM element based on the expanded state
        dom.sidebar.classList.toggle('expanded', state.isSidebarExpanded);
        // If the left sidebar toggle button exists
        if (dom.leftSidebarToggle) {
            // Update its 'aria-expanded' attribute for accessibility
            dom.leftSidebarToggle.setAttribute('aria-expanded', state.isSidebarExpanded.toString());
            // Get the icon element within the toggle button
            const toggleIcon = dom.leftSidebarToggle.querySelector('i');
            // If the icon exists, update its CSS class based on the expanded state (toggle icon style like 'x' and 'bars')
            if (toggleIcon) {
                toggleIcon.className = state.isSidebarExpanded ? 'fas fa-times' : 'fas fa-bars';
            }
        }
        // Logic: If the sidebar is collapsed (isSidebarExpanded is false)
        // And the session manager is currently expanded (!state.isSessionManagerCollapsed is true)
        if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
            // Automatically collapse the session manager
            updateSessionManagerState(true, instant); // true means collapse, instant indicates whether to update immediately
        }
    }

    /**
     * Updates the collapsed/expanded state of the session manager.
     * @param {boolean} collapse - Whether to collapse or expand.
     * @param {boolean} [instant=false] - Whether to update instantly without animation.
     */
    function updateSessionManagerState(collapse, instant = false) {
        // Update the session manager collapsed state in the state
        state.isSessionManagerCollapsed = collapse;
        // Toggle the 'collapsed' CSS class on the session manager DOM element based on the collapsed state
        dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
        // Update the 'aria-expanded' attribute of the session manager toggle button (note: aria-expanded indicates if it is "expanded", so the value is opposite to collapse)
        dom.sessionManagerToggle.setAttribute('aria-expanded', (!state.isSessionManagerCollapsed).toString());
        // Get the icon element within the toggle button (usually a small arrow)
        const sessionToggleIcon = dom.sessionManagerToggle.querySelector('.toggle-icon');
        // If the icon exists, update its CSS class based on the collapsed state (toggle arrow direction)
        if (sessionToggleIcon) {
            sessionToggleIcon.className = state.isSessionManagerCollapsed ? 'fas fa-caret-right' : 'fas fa-caret-down';
        }
    }

    /**
     * Handles sending a message.
     * Constructs the message object, adds it to the current session, updates the UI, and sends it via WebSocket to the backend.
     */
    async function handleSendMessage() {
        // If the application is currently in a loading state (e.g., waiting for a reply from the previous request)
        if (state.isLoading) {
            showToast("Lumina核心正在处理上一指令. 请稍候...", "warning"); // Show a warning message
            return; // Prevent sending a new message
        }
        // Get the text content from the user input box and remove leading/trailing whitespace
        const messageText = dom.userInput.value.trim();
        // Copy the list of currently selected files to upload (using spread operator to create a shallow copy)
        const filesToSend = [...state.uploadedFiles];
        // If the message text is empty and no files have been selected
        if (messageText === '' && filesToSend.length === 0) {
            showToast("需要指令. 请输入指令或附加数据模块.", "warning"); // Show a warning message
            return; // Prevent sending an empty message
        }
        // If the number of characters in the user input exceeds the maximum limit
        if (dom.userInput.value.length > state.maxInputChars) {
            showToast(`指令缓冲区溢出. 最大 ${state.maxInputChars} 字符.`, "error"); // Show an error message
            return; // Prevent sending an over-limit message
        }
        // If the WebSocket is not connected or the connection state is not OPEN
        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
            showToast("光绘链接离线. 尝试重新同步...", "warning"); // Show a warning message
            connectWebSocket(); // Attempt to reconnect the WebSocket
            return; // Prevent sending the message
        }
        // Set the application to a loading state (disables input etc.)
        setLoadingState(true);
        // Generate a new client request ID to track the response for this message
        state.currentClientRequestId = generateClientRequestId();
        // Clear any cached thinking process from the last response
        state.lastResponseThinking = null;

        // Construct the user message object for storage and display
        const currentUserMessage = {
            content: messageText, // Message text
            sender: 'user', // Sender is user
            timestamp: Date.now(), // Current timestamp
            isHTML: false, // Content is not HTML
            attachments: filesToSend.map(f => ({ name: f.name, size: f.size, type: f.type })) // Attachment information (name, size, type)
        };
        // Add this user message to the current session's message history (state and localStorage)
        addMessageToCurrentSession(currentUserMessage);
        // Append this user message to the chat interface for display
        appendMessage(messageText, 'user', false, null, false, currentUserMessage.attachments);

        // Auto-naming logic: If the current session object exists, the session name starts with "光绘墨迹项目 " (default name),
        // and this is the user's first message in this session (count of user messages is 1 after adding this one)
        const currentSession = state.sessions[state.currentSessionId];
        if (currentSession && currentSession.name.startsWith("光绘墨迹项目 ") && currentSession.messages.filter(m => m.sender === 'user').length === 1) {
            // Use the first 40 characters of the message text as the auto-generated name (default to "新墨迹" if empty)
            const autoName = messageText.substring(0, 40).trim() || "新墨迹";
            // Update the session name, add "..." if the message was longer than 40 characters
            currentSession.name = autoName + (messageText.length > 40 ? "..." : "");
            // Update the UI element displaying the session name
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            // Re-render the session list to reflect the name change
            renderSessionList();
        }

        // Clear the input area:
        dom.userInput.value = ''; // Clear the user input box
        adjustTextareaHeight(); // Adjust the input box height
        updateCharCounter(); // Update the character counter
        closeFilePreview(); // Close the file preview area
        state.uploadedFiles = []; // Clear the list of selected files

        // Prepare and display the right process log sidebar:
        if (dom.processLogSidebarContent) dom.processLogSidebarContent.innerHTML = ''; // Clear log content
        showProcessLogSidebar(true); // Show and ensure the log sidebar is expanded

        // Construct the message content to send to the backend:
        let backendMessageContent = messageText; // Start with the user's input text
        // If there are attachments
        if (filesToSend.length > 0) {
            // Append file information to the message text, informing the backend about the attached files
            backendMessageContent += `\n[用户已附加数据模块: ${filesToSend.map(f => f.name).join(', ')}. 请基于这些模块名称处理指令.]`;
        }

        // Send the message to the backend via WebSocket
        sendWebSocketMessage({
            type: 'message', // Message type
            session_id: state.currentSessionId, // Current session ID
            request_id: state.currentClientRequestId, // Client request ID
            content: backendMessageContent, // Message content including file information
            mode: state.currentMode // Current application mode
        });
    }
    /**
     * Adds a message object to the current session's `messages` array and saves the sessions.
     * @param {object} messageObject - The message object to add.
     */
    function addMessageToCurrentSession(messageObject) {
        // Check if the current session exists in state.sessions
        if (state.sessions[state.currentSessionId]) {
            // If the message sender is not 'agent' (i.e., it's a user message or system message)
            // Delete fields specific to Agent responses to avoid unnecessarily storing them in non-Agent messages
            if (messageObject.sender !== 'agent') {
                delete messageObject.rawResponseV1_3_2_CamelCase; // Delete raw JSON response field
                delete messageObject.thinking; // Delete thinking process field
            }
            // If the message object does not have an errorType property (or it's null/undefined)
            // Delete the property from the object for data cleanliness
            if (messageObject.errorType === undefined || messageObject.errorType === null) {
                delete messageObject.errorType;
            }
            // Push the message object to the end of the current session's messages array
            state.sessions[state.currentSessionId].messages.push(messageObject);
            // Save all session data to localStorage to persist the changes
            saveSessions();
        } else {
            // If attempting to add a message to a non-existent session, log an error
            console.error("尝试向不存在的会话添加消息:", state.currentSessionId);
        }
    }
    /**
     * Handles the keypress event in the user input box.
     * If Enter is pressed (and Shift is not held), sends the message.
     * @param {KeyboardEvent} event - The keypress event object.
     */
    function handleUserInputKeypress(event) {
        // Check if the pressed key is 'Enter' and the Shift key is NOT simultaneously pressed
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevent the default behavior (e.g., inserting a newline in the textarea)
            handleSendMessage(); // Call the function to send the message
        }
    }

    /**
     * Appends a new message to the chat box.
     * @param {string} content - The message content.
     * @param {string} sender - The sender ('user', 'agent', 'system-info', 'error-system').
     * @param {boolean} [isHTML=false] - Is the content HTML?
     * @param {string|null} [thinkContent=null] - The agent's thinking process text (if applicable).
     * @param {boolean} [isSwitchingSession=false] - Is this being called while switching sessions (loading history)?
     * @param {Array} [attachments=[]] - List of attachments for the message.
     * @param {string|null} [errorType=null] - The error type of the message (if applicable).
     */
    function appendMessage(content, sender, isHTML = false, thinkContent = null, isSwitchingSession = false, attachments = [], errorType = null) {
        // Create the top-level div element for the message
        const messageDiv = document.createElement('div');
        // Determine the CSS class for the message based on the sender (e.g., 'message-user', 'message-agent')
        const messageSenderClass = `message-${sender}`;
        messageDiv.classList.add('message', messageSenderClass); // Add the generic 'message' class and the specific sender class
        // If an error type exists, add a CSS class based on the error type for potential specific styling
        if (errorType) {
            const errorClassSuffix = errorType.toLowerCase().replace(/\s+/g, '-'); // Convert error type to CSS class name (lowercase, spaces to hyphens)
            messageDiv.classList.add(`message-error-type-${errorClassSuffix}`);
        }
        // If it's a system info or system error message
        if (sender === 'system-info' || sender === 'error-system') {
            messageDiv.classList.add('system-message'); // Add the 'system-message' class
            if (sender === 'error-system') messageDiv.classList.add('error-message'); // If it's a system error, add the 'error-message' class as well
        }
        // Apply entry animation (if not loading history while switching sessions, and animation level is not 'none')
        if (!isSwitchingSession && state.animationLevel !== 'none') {
            // Choose different Animate.css classes based on the animation level
            const animationClass = state.animationLevel === 'full' ? 'animate__fadeInUp' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
            if (animationClass) { // If an animation class was chosen
                messageDiv.classList.add('animate__animated', animationClass); // Add animation classes
                // Set the animation duration
                messageDiv.style.setProperty('--animate-duration', state.animationLevel === 'full' ? '0.45s' : '0.35s');
            }
        }
        // Create the avatar div element
        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('message-avatar'); // Add the 'message-avatar' class
        // Choose different FontAwesome icons for the avatar based on the sender
        let avatarIcon = 'fas fa-question-circle'; // Default icon
        if (sender === 'user') avatarIcon = 'fas fa-user-pen'; // User icon
        else if (sender === 'agent') avatarIcon = 'fas fa-lightbulb'; // Agent icon
        else if (sender === 'system-info') avatarIcon = 'fas fa-info-circle'; // System info icon
        else if (sender === 'error-system') avatarIcon = 'fas fa-exclamation-triangle'; // System error icon
        avatarDiv.innerHTML = `<i class="${avatarIcon}"></i>`; // Set the HTML content for the avatar icon

        // Determine the order of avatar and message bubble based on the sender (Agent-like messages have avatar first, user messages have avatar last)
        if (sender === 'agent' || sender === 'system-info' || sender === 'error-system') {
            messageDiv.appendChild(avatarDiv); // Append the avatar to the beginning of the message div
        }

        // Create the message bubble div element
        const messageBubbleDiv = document.createElement('div');
        messageBubbleDiv.classList.add('message-bubble'); // Add the 'message-bubble' class
        // Create the message content wrapper div element (to contain thinking process and main content)
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.classList.add('message-content-wrapper');

        // If it's an Agent message, and there is thinking content (thinkContent), AND the user setting allows showing thinking process in chat bubbles
        if (sender === 'agent' && thinkContent && state.showChatBubblesThink) {
            // Create the div element to display the thinking process prefix and content
            const thinkPrefixDiv = document.createElement('div');
            thinkPrefixDiv.classList.add('message-thought-prefix'); // Add specific class name
            // Format the thinking content: replace newline characters with <br>
            let formattedThink = String(thinkContent).replace(/\n/g, '<br>');
            // Define a regular expression to match JSON code blocks (case-insensitive, dotall for newlines)
            const jsonBlockRegex = /```json\s*([\s\S]*?)\s*```/gi;
            // Replace JSON code blocks within the thinking content with formatted <pre><code> blocks
            formattedThink = formattedThink.replace(jsonBlockRegex, (match, jsonContentStr) => {
                const trimmedJson = jsonContentStr.trim(); // Trim leading/trailing whitespace from JSON content
                try {
                    const parsedJson = JSON.parse(trimmedJson); // Parse the JSON
                    // Format the parsed JSON object into a string with indentation (2 spaces), and escape HTML special characters
                    const escapedJsonString = JSON.stringify(parsedJson, null, 2)
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    // Return the formatted HTML using <pre> and <code> tags with the embedded-json class
                    return `<pre class="embedded-json"><code>${escapedJsonString}</code></pre>`;
                } catch (e) {
                    // If JSON parsing fails, log a warning to the console
                    console.warn("Chat bubble: JSON parsing for pretty print failed within thought:", e);
                    // Escape HTML special characters from the original JSON content
                    const escapedOriginalJson = trimmedJson.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    // Return HTML containing the original content and an error message, styled as an error embedded JSON block
                    return `<pre class="embedded-json error"><code>${escapedOriginalJson}<br>(无效JSON投影)</code></pre>`;
                }
            });
            // Set the HTML content of the thinking process prefix div, including the label and formatted thinking text
            thinkPrefixDiv.innerHTML = `<strong><i class="fas fa-brain"></i> AI思维墨迹:</strong><div class="think-bubble-content">${formattedThink}</div>`;
            // Append the thinking process prefix div to the message content wrapper
            messageContentWrapper.appendChild(thinkPrefixDiv);
        }

        // Create the div element to display the main message text content
        const textContentDiv = document.createElement('div');
        textContentDiv.classList.add('message-text-content'); // Add specific class name
        // If the content is HTML (isHTML is true)
        if (isHTML) {
            textContentDiv.innerHTML = content; // Directly insert the HTML content
        } else { // If the content is plain text
            // Define a regular expression to match URLs
            const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
            // Process the plain text: escape HTML special characters, replace newlines with <br>, and convert URLs to clickable links
            const linkedContent = String(content)
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") // Escape &, <, >
                .replace(/"/g, "&quot;").replace(/'/g, "&#39;") // Escape ", '
                .replace(/\n/g, '<br>') // Replace newline characters with <br> tags
                .replace(urlRegex, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer" class="external-link"><i class="fas fa-external-link-alt"></i> ${url}</a>`); // Convert URLs to links
            textContentDiv.innerHTML = linkedContent; // Set the processed text content
        }
        // Append the main text content div to the message content wrapper
        messageContentWrapper.appendChild(textContentDiv);

        // If the message includes attachments (attachments array is not empty)
        if (attachments && attachments.length > 0) {
            // Create the div element to display the attachment summary
            const attachmentsDiv = document.createElement('div');
            attachmentsDiv.classList.add('message-attachments-summary'); // Add specific class name
            // Set the initial HTML content for the attachment summary, including an icon and attachment count
            attachmentsDiv.innerHTML = `<i class="fas fa-paperclip"></i> 数据模块已附加 (${attachments.length}): `;
            // Iterate through each attachment
            attachments.forEach(file => {
                // Create a span element to act as a "chip" or "tag" for the filename
                const fileChip = document.createElement('span');
                fileChip.classList.add('filename-chip'); // Add specific class name
                fileChip.textContent = file.name; // Set the chip text to the filename
                // Set the title attribute (tooltip) of the chip, showing detailed file information (name, size, type)
                fileChip.title = `${file.name} (${(file.size / 1024).toFixed(1)}KB, 类型: ${file.type || '未知'})`;
                // Append the filename chip to the attachment summary div
                attachmentsDiv.appendChild(fileChip);
            });
            // Append the attachment summary div to the message content wrapper
            messageContentWrapper.appendChild(attachmentsDiv);
        }
        // Append the content wrapper to the message bubble
        messageBubbleDiv.appendChild(messageContentWrapper);
        // Append the message bubble to the message div (after the avatar for Agent-like messages)
        messageDiv.appendChild(messageBubbleDiv);

        // If it's a user message
        if (sender === 'user') {
            messageDiv.appendChild(avatarDiv); // Append the avatar to the end of the message div
        }

        // Append the entire message div (including avatar and bubble) to the chat box (dom.chatBox)
        dom.chatBox.appendChild(messageDiv);
        // Attach event listeners for any quick action buttons within the newly appended message
        attachQuickActionButtonListeners(messageDiv);
        // If it's not loading history while switching sessions (i.e., it's a newly sent or received message)
        if (!isSwitchingSession) { scrollToBottom(); } // Scroll the chat box to the bottom
    }

    /**
     * Appends the initial welcome message to the chat box.
     * Only called if the chat box is empty.
     */
    function appendWelcomeMessage() {
        // Get the last child element in the chat box (i.e., the last message)
        const lastMessage = dom.chatBox.lastElementChild;
        // If the last message exists and it is already the initial welcome message (checked by class name), do not add it again
        if (lastMessage && lastMessage.classList.contains('system-message-initial')) { return; }

        // Define the HTML content string for the welcome message
        const welcomeHTML = `
            <div class="message-content">
                <div class="welcome-header">
                    <!-- Robot icon with animation -->
                    <i class="fas fa-dna robot-icon animate__animated animate__pulse animate__infinite" style="--animate-duration: 3.5s;"></i>
                    <!-- App title and version -->
                    <h2>CircuitManus <span class="version-pro">Lumina <span class="version-number">v1.0.0</span></span></h2> <!-- Version sync -->
                </div>
                <!-- Subtitle -->
                <p class="welcome-subtitle">您的光绘墨迹交互界面，赋能创意与构想。Lumina核心已激活，请挥洒您的灵感。</p>
                <!-- Capabilities display -->
                <div class="capabilities">
                    <div class="capability"><i class="fas fa-lightbulb"></i><span>灵感激发</span></div>
                    <div class="capability"><i class="fas fa-drafting-compass"></i><span>草图勾勒</span></div>
                    <div class="capability"><i class="fas fa-palette"></i><span>色彩构想</span></div>
                    <div class="capability"><i class="fas fa-code"></i><span>代码生成</span></div>
                    <div class="capability"><i class="fas fa-microchip"></i><span>电路设计</span></div>
                    <div class="capability"><i class="fas fa-project-diagram"></i><span>流程规划</span></div>
                    <div class="capability"><i class="fas fa-feather-alt"></i><span>文本创作</span></div>
                    <div class="capability"><i class="fas fa-search"></i><span>信息检索</span></div>
                </div>
                 <!-- Quick actions area -->
                 <div class="quick-actions">
                    <p>开始您的创作或选择预设指令:</p>
                    <ul>
                        <!-- Various quick action buttons -->
                        <li><a href="#" class="quick-action-btn lumina-button" data-message="设计一个简约的LOGO"><i class="fas fa-signature"></i> 设计LOGO</a></li>
                        <li><a href="#" class="quick-action-btn lumina-button" data-message="写一首关于星空的短诗"><i class="fas fa-moon"></i> 星空诗篇</a></li>
                        <li><a href="#" class="quick-action-btn lumina-button" data-message="帮我规划一个旅行日程"><i class="fas fa-map-signs"></i> 旅行规划</a></li>
                        <li><a href="#" class="quick-action-btn lumina-button" data-message="描述当前的电路状态"><i class="fas fa-eye"></i> 查看电路</a></li>
                        <li><a href="#" class="quick-action-btn lumina-button" data-message="清空所有元件和连接"><i class="fas fa-eraser"></i> 清空画布</a></li>
                        <li><a href="#" class="quick-action-btn lumina-button" data-message="解释什么是人工智能"><i class="fas fa-brain"></i> AI释义</a></li>
                        <li><a href="#" class="quick-action-btn lumina-button" data-message="新建一个光绘项目"><i class="fas fa-plus-square"></i> 新建项目</a></li>
                        <li><a href="#" class="quick-action-btn lumina-button" data-message="切换到代码绘卷模式"><i class="fas fa-laptop-code"></i> 代码模式</a></li>
                    </ul>
                 </div>
            </div>
        `;
        // Create the top-level div element for the welcome message
        const welcomeDiv = document.createElement('div');
        // Choose the entry animation class based on the animation level
        const animClass = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInUp' : 'animate__fadeIn') : '';
        // Set the CSS classes for the welcome message div, including base classes, system message class, initial message class, panel class, and animation class
        welcomeDiv.className = `message system-message system-message-initial lumina-panel ${animClass ? 'animate__animated ' + animClass : ''}`;
        // If an animation class was applied, set the animation duration
        if (animClass) welcomeDiv.style.setProperty('--animate-duration', '0.65s');
        // Set the HTML content of the welcome message div
        welcomeDiv.innerHTML = welcomeHTML;
        // Append the welcome message div to the chat box
        dom.chatBox.appendChild(welcomeDiv);
        // Attach event listeners for quick action buttons within the welcome message
        attachQuickActionButtonListeners(welcomeDiv);
    }

    /**
     * Scrolls the chat box to the bottom.
     * @param {boolean} [instant=false] - Whether to scroll instantly without smooth effect.
     */
    function scrollToBottom(instant = false) {
        // Only execute if state.autoScroll (automatic scrolling) is true
        if (state.autoScroll) {
            // Determine the scroll behavior ('auto' for instant scroll, 'smooth' for smooth scroll) based on the instant parameter and the application's animation level
            const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth';
            // Call the scrollTo method on the chat box (dom.chatBox), scrolling it to the very bottom of its content
            dom.chatBox.scrollTo({ top: dom.chatBox.scrollHeight, behavior: behavior });
        }
    }

    /**
     * Displays the typing indicator for the Agent.
     */
    function showTypingIndicator() {
        // If the Agent is already in typing state (state.isAgentTyping is true), do not add the indicator again
        if (state.isAgentTyping) return;
        // Set the Agent to typing state
        state.isAgentTyping = true;
        // Create the top-level div element for the typing indicator
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator'; // Set an ID for easy lookup and removal later
        // Choose the entry animation class based on the animation level
        const animationClass = state.animationLevel !== 'none' ? 'animate__fadeInUp' : '';
        // Add base CSS classes ('message', 'message-agent', 'typing-indicator')
        typingDiv.classList.add('message', 'message-agent', 'typing-indicator');
        // If an animation class was chosen
        if (animationClass) {
            typingDiv.classList.add('animate__animated', animationClass); // Add animation class
            typingDiv.style.setProperty('--animate-duration', '0.4s'); // Set animation duration
        }
        // Create the avatar div element
        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('message-avatar'); // Add the 'message-avatar' class
        // Set the Agent avatar icon (lightbulb, with pulsing effect)
        avatarDiv.innerHTML = '<i class="fas fa-lightbulb fa-beat"></i>';
        // Create the message bubble div element
        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('message-bubble'); // Add the 'message-bubble' class
        // Create the message content wrapper div element
        const contentWrapper = document.createElement('div');
        contentWrapper.classList.add('message-content-wrapper');
        // Create the div element to display the text content
        const textContent = document.createElement('div');
        textContent.classList.add('message-text-content');
        // Create the HTML for three dynamic dots (...)
        let dotsHTML = Array(3).fill('<span class="typing-dot"></span>').join('');
        // Set the text content of the typing indicator, including "Lumina核心构思中" and the dynamic dots
        textContent.innerHTML = `Lumina核心构思中<span class="typing-dots">${dotsHTML}</span>`;
        // Assemble elements: text content -> content wrapper -> bubble
        contentWrapper.appendChild(textContent);
        bubbleDiv.appendChild(contentWrapper);
        // Assemble the message: avatar -> bubble -> typing indicator top-level div
        typingDiv.appendChild(avatarDiv);
        typingDiv.appendChild(bubbleDiv);
        // Append the typing indicator to the chat box
        dom.chatBox.appendChild(typingDiv);
        // Scroll the chat box to the bottom to ensure the typing indicator is visible
        scrollToBottom();
    }
    /**
     * Hides the typing indicator for the Agent.
     */
    function hideTypingIndicator() {
        // If the Agent is not currently in typing state (state.isAgentTyping is false), do nothing
        if (!state.isAgentTyping) return;
        // Set the Agent to not typing state
        state.isAgentTyping = false;
        // Find the typing indicator element by its ID
        const typingElement = document.getElementById('typing-indicator');
        // If the typing indicator element is found
        if (typingElement) {
            // If animations are enabled (state.animationLevel is not 'none')
            if (state.animationLevel !== 'none') {
                // Choose the exit animation class based on the animation level
                const animationOutClass = state.animationLevel === 'full' ? 'animate__fadeOutDown' : 'animate__fadeOut';
                // Remove any potential entry animation classes
                typingElement.classList.remove('animate__fadeInUp', 'animate__fadeIn');
                // Add the Animate.css exit animation class
                typingElement.classList.add('animate__animated', animationOutClass);
                // Set the duration of the exit animation
                typingElement.style.setProperty('--animate-duration', '0.3s');
                // Listen for the animation end event, remove the element after the animation finishes (once: true means the event triggers only once)
                typingElement.addEventListener('animationend', () => typingElement.remove(), { once: true });
            } else {
                // If animations are not enabled, remove the typing indicator element directly
                typingElement.remove();
            }
        }
    }
    /**
     * Adjusts the height of the user input textarea based on its content.
     */
    function adjustTextareaHeight() {
        // First, set the textarea's height to 'auto' so that scrollHeight reflects the actual content height needed
        dom.userInput.style.height = 'auto';
        // Get the actual scroll height of the textarea's content
        let scrollHeight = dom.userInput.scrollHeight;
        // Get the max height limit for the textarea from CSS, default to 200px if not defined
        const maxHeight = parseInt(getComputedStyle(dom.userInput).maxHeight, 10) || 200;
        // Get the min height limit for the textarea from CSS, default to 52px (ensure a default value)
        const minHeight = parseInt(getComputedStyle(dom.userInput).minHeight, 10) || 52;

        // Define extra space to simulate vertical padding for single-line text, improving visual appearance
        const singleLinePadding = 5;
        // Check if it's a single line of text (by checking for newline characters) AND the actual content height is less than the minimum height plus the simulated vertical padding
         // This condition aims to avoid adding extra height unnecessarily when the minHeight is already sufficient for single-line text plus its actual CSS padding
        if (dom.userInput.value.split('\n').length <= 1 && scrollHeight < minHeight + singleLinePadding * 2) {
            // If this is the case, add the simulated padding to the scrollHeight
            scrollHeight += singleLinePadding;
        }


        // If the calculated content height exceeds the maximum height limit
        if (scrollHeight > maxHeight) {
            // Set the textarea's height to the maximum height
            dom.userInput.style.height = maxHeight + 'px';
            // Show the vertical scrollbar
            dom.userInput.style.overflowY = 'auto';
        } else { // If the content height is within the limits
            // Set the textarea's height to the greater of scrollHeight and minHeight (ensuring it's not less than the minimum height)
            dom.userInput.style.height = Math.max(scrollHeight, minHeight) + 'px';
            // Hide the vertical scrollbar
            dom.userInput.style.overflowY = 'hidden';
        }
    }

    /**
     * Handles clearing the current chat history.
     */
    function handleClearCurrentChat() {
        // If there is no current active session ID, or the session does not exist in state.sessions, do nothing
        if (!state.currentSessionId || !state.sessions[state.currentSessionId]) return;
        // Show a confirmation dialog asking the user if they are sure they want to clear the current session's chat history
        // The prompt message includes the name of the current session
        if (!confirm(`清空当前光绘墨迹项目 "${state.sessions[state.currentSessionId].name}"? 这将清除所有消息记录.`)) {
            return; // If the user cancels, return
        }
        // Clear the message array of the current session
        state.sessions[state.currentSessionId].messages = [];
        // Update the last activity timestamp for the current session to the current time
        state.sessions[state.currentSessionId].lastActivity = Date.now();
        // Save all session data (because messages have been cleared)
        saveSessions();
        // Clear the UI display of the chat box
        dom.chatBox.innerHTML = '';
        // Display the welcome message in the empty chat box
        appendWelcomeMessage();
        // Clear and hide the right process log sidebar
        if (dom.processLogSidebarContent) dom.processLogSidebarContent.innerHTML = ''; // Clear log content
        // Depending on its current visibility state, decide whether to show or hide it
        if (state.isProcessLogSidebarVisible) {
            showProcessLogSidebar(false); // If visible, show (do not force expand)
        } else {
            hideProcessLogSidebar(); // If not visible, hide
        }
        // Show a Toast notification informing the user that the current session has been cleared
        showToast('当前光绘墨迹项目已清空!', 'info');
        // Re-render the session list (might affect the display order based on "last activity time")
        renderSessionList();
    }

    /**
     * Handles switching between application modes (e.g., chat, code, circuit).
     * @param {string} newMode - The new mode to switch to.
     */
    function handleModeChange(newMode) {
        // If the new mode to switch to is the same as the current mode, do nothing
        if (state.currentMode === newMode) return;

        // Update the active state of the sidebar buttons:
        // Iterate through all sidebar buttons (dom.sidebarButtons)
        dom.sidebarButtons.forEach(button =>
            // Toggle the 'active' CSS class: add 'active' class if the button's data-mode attribute value matches newMode, otherwise remove it
            button.classList.toggle('active', button.dataset.mode === newMode)
        );
        // Update the current mode in the state
        state.currentMode = newMode;
        // Log that the mode has been switched
        console.log(`模式已切换至: ${newMode}`);
        // Show a Toast notification informing the user that they have switched to the new mode (using getModeDisplayName to get the display name of the mode)
        showToast(`已切换至 ${getModeDisplayName(newMode)} 领域`, 'info');

        // Update the placeholder text of the user input box to reflect the new mode and current session name
        const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
        dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${sessionNameForPlaceholder})...`;
    }

    /**
     * Handles the file selection event.
     * Validates the number and size of files and adds valid files to the upload list and preview area.
     * @param {Event} event - The change event object from the file input.
     */
    function handleFileSelection(event) {
        // Get the selected files from the event object's target.files and convert them to a real array
        const files = Array.from(event.target.files);
        // If no files were selected, do nothing
        if (files.length === 0) return;
        // Define limits for file upload: maximum 5 files, maximum 2MB per file
        const MAX_FILES = 5;
        const MAX_SIZE_MB = 2;
        // Iterate through each selected file
        files.forEach(file => {
            // Check if the number of currently selected files to upload has reached the limit
            if (state.uploadedFiles.length >= MAX_FILES) {
                // If the limit is reached, show a warning Toast notification and stop processing subsequent files
                showToast(`每次传输最多允许 ${MAX_FILES} 个数据卷轴.`, 'warning');
                return; // Note: this return statement only skips the current iteration of the forEach loop, it does not exit the entire function
            }
            // Check if the size of the current file exceeds the limit (MAX_SIZE_MB converted to bytes)
            if (file.size > MAX_SIZE_MB * 1024 * 1024) {
                // If the size limit is exceeded, show a warning Toast notification and skip this file
                showToast(`数据卷轴 "${file.name}" 大小超过 ${MAX_SIZE_MB}MB 限制.`, 'warning');
                return; // Skip processing of the current file
            }
            // Check if a file with the same name and size has already been added (simple deduplication logic)
            if (!state.uploadedFiles.find(f => f.name === file.name && f.size === file.size)) {
                // If the file has not been added before, add it to the state.uploadedFiles array
                state.uploadedFiles.push(file);
                // Add the file to the UI's file preview area
                addFileToPreview(file);
            } else {
                // If the file has already been added, show an info Toast notification
                showToast(`数据卷轴 "${file.name}" 已在队列中.`, 'info');
            }
        });
        // If the upload file list is not empty (i.e., at least one file was selected and passed validation)
        if (state.uploadedFiles.length > 0) {
            // Show the file preview area (by adding the 'active' CSS class)
            dom.filePreviewArea.classList.add('active');
        }
        // Clear the value of the file input, so the user can select the same file again next time (otherwise the change event might not trigger)
        dom.fileInput.value = '';
    }
    /**
     * Adds a selected file to the UI's file preview area.
     * @param {File} file - The file object to add to the preview.
     */
    function addFileToPreview(file) {
        // Create a new div element as a file preview item
        const fileItem = document.createElement('div');
        fileItem.classList.add('file-item'); // Add base CSS class
        // If animations are enabled (state.animationLevel is not 'none')
        if (state.animationLevel !== 'none') {
            // Add Animate.css entry animation class (bounce in)
            fileItem.classList.add('animate__animated', 'animate__bounceIn');
            // Set the animation duration
            fileItem.style.setProperty('--animate-duration', '0.4s');
        }
        // Store the filename and file size in data-* attributes of the element for easy lookup and removal later
        fileItem.dataset.fileName = file.name;
        fileItem.dataset.fileSize = file.size;
        // Get the corresponding FontAwesome icon class based on the file type and name
        const iconClass = getFileIconClass(file.type, file.name);
        // Set the HTML content of the file preview item, including icon, filename, and remove button
        // The title attribute of the filename span displays detailed file information (name, size, type)
        fileItem.innerHTML = `
            <i class="fas ${iconClass} file-icon"></i>
            <span class="file-name" title="${file.name} (${(file.size / 1024).toFixed(1)}KB, 类型: ${file.type || '未知'})">${file.name}</span>
            <button class="file-remove icon-btn" title="移除数据卷轴"><i class="fas fa-times-circle"></i></button>`;
        // Add a click event listener to the remove button within the preview item
        fileItem.querySelector('.file-remove').addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent event propagation to the parent element (the file item itself)
            // Call the removeFileFromPreview function, passing the filename and size to remove this file
            removeFileFromPreview(file.name, file.size);
        });
        // Append the created file preview item to the file preview content area (dom.filePreviewContent)
        dom.filePreviewContent.appendChild(fileItem);
    }
    /**
     * Gets the corresponding FontAwesome icon class based on the file type and name.
     * @param {string} fileType - The MIME type of the file.
     * @param {string} fileName - The name of the file.
     * @returns {string} The FontAwesome icon class name.
     */
    function getFileIconClass(fileType, fileName) {
        // Determine common file types based on MIME type
        if (fileType.startsWith('image/')) return 'fa-file-image'; // Image files
        if (fileType.startsWith('audio/')) return 'fa-file-audio'; // Audio files
        if (fileType.startsWith('video/')) return 'fa-file-video'; // Video files
        if (fileType === 'application/pdf') return 'fa-file-pdf'; // PDF files
        // Determine compressed files based on MIME type or file extension
        if (fileType === 'application/zip' || fileName.endsWith('.zip') || fileName.endsWith('.rar') || fileName.endsWith('.7z')) return 'fa-file-archive';

        // Get the file extension (converted to lowercase)
        const ext = fileName.slice(fileName.lastIndexOf(".")).toLowerCase();
        // Define arrays of common code and text file extensions
        const codeExtensions = ['.js', '.ts', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bat', '.v', '.sv', '.vhd', '.md', '.txt', '.log', '.sch', '.brd', '.cir', '.net', '.vhd'];
        // If the file extension is in the array, or the MIME type includes 'text', consider it a code/text file
        if (codeExtensions.includes(ext) || fileType.includes('text')) return 'fa-file-code';
        // Office document type determination
        if (['.doc', '.docx'].includes(ext)) return 'fa-file-word'; // Word documents
        if (['.xls', '.xlsx', '.csv'].includes(ext)) return 'fa-file-excel'; // Excel or CSV files
        if (['.ppt', '.pptx'].includes(ext)) return 'fa-file-powerpoint'; // PowerPoint files
        // CAD file type determination (example)
        if (['.dwg', '.dxf'].includes(ext)) return 'fa-drafting-compass'; // CAD files (using drafting compass icon)
        // If none of the above conditions are met, return the default file icon
        return 'fa-file-alt';
    }
    /**
     * Removes the specified file from the upload list and UI preview.
     * @param {string} fileName - The name of the file to remove.
     * @param {number} fileSize - The size of the file to remove (used to distinguish files with the same name).
     */
    function removeFileFromPreview(fileName, fileSize) {
        // Filter out files from the state.uploadedFiles array that match the given filename and size
        // Use filter to create a new array that does not include the file to be removed
        state.uploadedFiles = state.uploadedFiles.filter(f => !(f.name === fileName && f.size === fileSize));
        // Find the corresponding file preview item element from the DOM
        // Use CSS.escape(fileName) to correctly handle potential special CSS selector characters in the filename
        const fileItemElement = dom.filePreviewContent.querySelector(`.file-item[data-file-name="${CSS.escape(fileName)}"][data-file-size="${fileSize}"]`);

        // If the corresponding DOM element is found
        if (fileItemElement) {
            // If animations are enabled (state.animationLevel is not 'none')
            if (state.animationLevel !== 'none') {
                // Remove any potential entry animation classes (bounceIn)
                fileItemElement.classList.remove('animate__bounceIn');
                // Add Animate.css exit animation class (bounce out)
                fileItemElement.classList.add('animate__animated', 'animate__bounceOut');
                // Listen for the animation end event
                fileItemElement.addEventListener('animationend', () => {
                    // After the animation finishes, check again if the Toast is still in the DOM (in case it was removed by other means during the animation)
                    if (fileItemElement.parentElement) {
                         fileItemElement.remove(); // Remove the DOM element
                         // If the upload file list is empty after removal, close (hide) the file preview area
                         if (state.uploadedFiles.length === 0) closeFilePreview();
                    }
                }, { once: true }); // once: true means the event triggers only once
            } else {
                // If animations are not enabled, remove the DOM element directly
                fileItemElement.remove();
                // If the upload file list is empty after removal, close the file preview area
                if (state.uploadedFiles.length === 0) closeFilePreview();
            }
        }
    }
    /**
     * Closes the file preview area.
     * It is hidden by removing the 'active' CSS class.
     */
    function closeFilePreview() { dom.filePreviewArea.classList.remove('active'); }

    /**
     * Applies the currently selected theme (light, dark, or auto).
     * This function primarily switches the theme by setting the `data-theme` attribute on the `body` element and related active classes.
     * It's a simple wrapper around `applyTheme` used to apply the current theme in state when the specific theme name isn't known but the current state needs to be applied.
     */
    function applyCurrentTheme() { applyTheme(state.currentTheme, true); } // true indicates initial load

    /**
     * Applies the specified theme.
     * @param {string} themeName - The name of the theme to apply ('light-crystal', 'dark-crystal', 'auto-crystal').
     * @param {boolean} [initialLoad=false] - Whether this is the initial load.
     */
    function applyTheme(themeName, initialLoad = false) {
        // Get the body element
        const body = document.body;
        // Remove any previously added theme active classes ('light-crystal-active', 'dark-crystal-active')
        body.classList.remove('light-crystal-active', 'dark-crystal-active');
        // Get the icon element within the theme toggle button
        const themeIcon = dom.themeToggleButton.querySelector('i');
        // Check and handle based on the themeName
        if (themeName === 'auto-crystal') { // If in auto mode
            // Check if the system prefers dark mode
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                body.classList.add('dark-crystal-active'); // System prefers dark, apply dark theme active class
            } else {
                body.classList.add('light-crystal-active'); // System prefers light or is unknown, apply light theme active class
            }
            // If the theme icon exists, set its class name to magic wand icon (indicating auto)
            if (themeIcon) themeIcon.className = 'fas fa-magic';
        } else if (themeName === 'dark-crystal') { // If in dark mode
            body.classList.add('dark-crystal-active'); // Apply dark theme active class
            // If the theme icon exists, set its class name to sun icon (indicating toggle to light)
            if (themeIcon) themeIcon.className = 'fas fa-sun';
        } else { // Default to light mode (light-crystal)
            body.classList.add('light-crystal-active'); // Apply light theme active class
            // If the theme icon exists, set its class name to moon icon (indicating toggle to dark)
            if (themeIcon) themeIcon.className = 'fas fa-moon';
        }
        // Set the 'data-theme' attribute on the body element with the theme name
        // This attribute is primarily used for CSS variable switching, e.g.: :root[data-theme="dark-crystal"] { --primary-color: ...; }
        body.dataset.theme = themeName;
        // Update the current theme name in the state
        state.currentTheme = themeName;
        // If the theme select dropdown in the settings modal exists, sync its value
        if (dom.themeSelect) dom.themeSelect.value = themeName;
        // If it's not initial load (i.e., user manually switched theme)
        if (!initialLoad) saveSettings(); // Save settings to localStorage
        // Log the applied theme information to the console
        console.log(`显示模式已设定为: ${themeName} (实际生效类: ${body.className.match(/(light|dark)-crystal-active/)?.[0] || '无特定激活类'})`);
    }

    /**
     * Gets the user-friendly display name for a theme.
     * @param {string} theme - The internal identifier of the theme.
     * @returns {string} The display name of the theme.
     */
    function getThemeDisplayName(theme) {
        // Define an object storing theme identifiers and their corresponding user-friendly display names
        const names = {
            'light-crystal': '月白宣纸 (Light)', // Light theme
            'dark-crystal': '墨黑星空 (Dark)',   // Dark theme
            'auto-crystal': '随境而变 (Auto)'    // Auto theme
        };
        // Return the display name for the corresponding theme, default to '未知意境' if not found
        return names[theme] || '未知意境';
    }
    /**
     * Applies the specified font size.
     * @param {string|number} size - The font size value (typically in pixels).
     */
    function applyFontSize(size) {
        // Convert the size parameter to an integer
        const newSize = parseInt(size, 10);
        // Validate if the font size is within a reasonable range (12px to 20px)
        // If it's not a number, or less than 12, or greater than 20
        if (isNaN(newSize) || newSize < 12 || newSize > 20) {
            // Revert to default font size (16px)
            document.documentElement.style.setProperty('--base-font-size', '16px');
            // If the font size input (range slider) in the settings modal exists, set its value to '16'
            if (dom.fontSizeInput) dom.fontSizeInput.value = '16';
            // If the font size value display element exists, set its text content to '16px'
            if (dom.fontSizeValue) dom.fontSizeValue.textContent = '16px';
            return; // End function execution
        }
        // If the font size is valid, set the CSS variable '--base-font-size'
        document.documentElement.style.setProperty('--base-font-size', `${newSize}px`);
        // Update the UI controls in the settings modal (if they exist):
        // Set the value of the font size input (range slider)
        if (dom.fontSizeInput) dom.fontSizeInput.value = newSize;
        // Set the text content of the font size value display element
        if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${newSize.toFixed(0)}px`;
    }
    /**
     * Applies the specified animation level.
     * @param {string} level - The animation level ('full', 'basic', 'none').
     */
    function applyAnimationLevel(level) {
        // Set the 'data-animation-level' attribute on the body element with the specified level
        // CSS can use this attribute to control different levels of animation effects, e.g.:
        // body[data-animation-level="none"] .animate__animated { animation: none !important; }
        document.body.dataset.animationLevel = level;
        // Update the current animation level in the state
        state.animationLevel = level;
        // Update the value of the animation level select dropdown in the settings modal (if it exists and is different from the current level)
        if (dom.animationLevelSelect && dom.animationLevelSelect.value !== level) {
            dom.animationLevelSelect.value = level;
        }
        // Log the applied animation level
        console.log(`动态效果等级已设定为: ${level}`);
    }

    /**
     * Opens the settings modal and loads the current settings into the UI controls.
     */
    function openSettingsModal() {
        // Load the current settings from the application state into the various UI controls in the modal:
        // Set the value of the theme select dropdown
        if (dom.themeSelect) dom.themeSelect.value = state.currentTheme;
        // Get the currently effective font size (read from CSS variable to ensure accuracy)
        const currentFontSize = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--base-font-size').replace('px', '')) || 16;
        // Set the value of the font size input (range slider)
        if (dom.fontSizeInput) dom.fontSizeInput.value = currentFontSize;
        // Set the text content of the font size value display element
        if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${currentFontSize.toFixed(0)}px`;
        // Set the value of the animation level select dropdown
        if (dom.animationLevelSelect) dom.animationLevelSelect.value = state.animationLevel;
        // Set the checked state of the auto-scroll toggle (checkbox)
        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        // Set the checked state of the sound enabled toggle
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        // Set the checked state of the "show thinking process in chat bubbles" toggle
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
        // Set the checked state of the "show thinking bubble in log entries" toggle
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
        // Set the checked state of the "auto-submit quick actions" toggle
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;
        // Set the checked state of the "3D component visibility" toggle
        if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;

        // Set the display style of the settings modal to 'flex' to make it visible (modals are typically flex layout for centering)
        dom.settingsModal.style.display = 'flex';
        // Get the content area element of the modal
        const modalContent = dom.settingsModal.querySelector('.modal-content');
        // Remove any potential exit animation classes to prevent interference with entry animation
        modalContent.classList.remove('animate__fadeOutDown', 'animate__zoomOut', 'animate__fadeOut');
        // Apply entry animation (if animation level is not 'none')
        // Choose different Animate.css entry animation classes based on the animation level
        const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__zoomIn' : 'animate__fadeIn') : '';
        if (animIn) { // If an animation class was chosen
            modalContent.classList.add('animate__animated', animIn); // Add animation classes
            modalContent.style.setProperty('--animate-duration', '0.45s'); // Set animation duration
        }
    }
    /**
     * Closes the settings modal.
     * @param {boolean} [revertChanges=true] - If true, revert unsaved setting changes before closing.
     */
    function closeSettingsModal(revertChanges = true) {
        // If revertChanges is true (typically when clicking the "Close" button or outside the modal)
        if (revertChanges) {
            // Reload and apply settings from localStorage to revert to the saved state
            applyTheme(localStorage.getItem(APP_PREFIX + 'theme') || 'auto-crystal', true); // true indicates initial load, avoids saving again
            applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
            applyAnimationLevel(localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full');
            state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || 'true') === 'true';
            state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || 'false') === 'true';
            state.showChatBubblesThink = (localStorage.getItem(APP_PREFIX + 'showChatBubblesThink') || 'true') === 'true';
            state.showLogBubblesThink = (localStorage.getItem(APP_PREFIX + 'showLogBubblesThink') || 'true') === 'true';
            state.autoSubmitQuickActions = (localStorage.getItem(APP_PREFIX + 'autoSubmitQuickActions') || 'true') === 'true';
            state.isIdtComponentVisible = (localStorage.getItem(APP_PREFIX + 'isIdtComponentVisible') || 'true') === 'true';

            // Update the UI controls in the settings modal to reflect the reverted setting values
            if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
            if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
            if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
            if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
            if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;
            if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;
            // Apply the reverted 3D component visibility state
            toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);
            // Update the icon of the 3D component toggle button
            const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
            if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';
        }

        // Get the content area element of the modal
        const modalContent = dom.settingsModal.querySelector('.modal-content');
        // Remove any potential entry animation classes
        modalContent.classList.remove('animate__zoomIn', 'animate__fadeIn');
        // Choose the exit animation class based on the animation level
        const animOut = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__zoomOut' : 'animate__fadeOut') : '';

        // Define the handler function for animation end
        const animationEndHandler = () => {
            // Set the display style of the settings modal to 'none' to hide it
            dom.settingsModal.style.display = 'none';
            // If an exit animation class was applied, remove them after the animation ends so entry animation plays correctly next time
            if (animOut) modalContent.classList.remove('animate__animated', animOut);
        };

        // If animations are enabled (state.animationLevel is not 'none') and an exit animation class was chosen
        if (state.animationLevel !== 'none' && animOut) {
            modalContent.classList.add('animate__animated', animOut); // Add the exit animation class
            modalContent.style.setProperty('--animate-duration', '0.35s'); // Set the animation duration
            // Listen for the animation end event, call animationEndHandler after the animation finishes (once: true means only triggers once)
            modalContent.addEventListener('animationend', animationEndHandler, { once: true });
        } else {
            // If animations are not enabled, or no exit animation class was chosen, call animationEndHandler directly to hide the modal
            animationEndHandler();
        }
    }
    /**
     * Collects the current settings from the settings modal UI controls, applies and saves them.
     */
    function collectAndSaveSettings() {
        // Get the selected theme value from the theme select dropdown
        state.currentTheme = dom.themeSelect.value;
        applyTheme(state.currentTheme); // Apply the selected theme

        // Get the value from the font size input (range slider) and apply it
        applyFontSize(dom.fontSizeInput.value);

        // Get the value from the animation level select dropdown and apply it
        applyAnimationLevel(dom.animationLevelSelect.value);

        // Update boolean settings in state, getting the checked state from the corresponding toggle switches (checkboxes)
        state.autoScroll = dom.autoScrollToggle.checked;
        state.soundEnabled = dom.soundEnabledToggle.checked;
        state.showChatBubblesThink = dom.showChatBubblesThinkToggle.checked;
        state.showLogBubblesThink = dom.showLogBubblesThinkToggle.checked;
        state.autoSubmitQuickActions = dom.autoSubmitQuickActionsToggle.checked;
        state.isIdtComponentVisible = dom.componentVisibilityToggle.checked;
        // Apply the 3D component visibility setting
        toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);

        // Call the saveSettings function to save all updated settings to localStorage
        saveSettings();
    }
    /**
     * Saves all persistent application settings to localStorage.
     */
    function saveSettings() {
        // Save theme setting
        localStorage.setItem(APP_PREFIX + 'theme', state.currentTheme);
        // Save font size (get the actually effective value from the CSS variable, and remove 'px' suffix)
        localStorage.setItem(APP_PREFIX + 'fontSize', document.documentElement.style.getPropertyValue('--base-font-size').replace('px', ''));
        // Save animation level setting
        localStorage.setItem(APP_PREFIX + 'animationLevel', state.animationLevel);
        // Save auto-scroll setting (convert to string 'true' or 'false')
        localStorage.setItem(APP_PREFIX + 'autoScroll', state.autoScroll.toString());
        // Save sound enabled setting
        localStorage.setItem(APP_PREFIX + 'soundEnabled', state.soundEnabled.toString());
        // Save "show thinking process in chat bubbles" setting
        localStorage.setItem(APP_PREFIX + 'showChatBubblesThink', state.showChatBubblesThink.toString());
        // Save "show thinking bubble in log entries" setting
        localStorage.setItem(APP_PREFIX + 'showLogBubblesThink', state.showLogBubblesThink.toString());
        // Save sidebar expanded state
        localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());
        // Save session manager collapsed state
        localStorage.setItem(APP_PREFIX + 'sessionManagerCollapsed', state.isSessionManagerCollapsed.toString());
        // Save process log sidebar visibility state
        localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarVisible', state.isProcessLogSidebarVisible.toString());
        // Save process log sidebar collapsed state
        localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarCollapsed', state.isProcessLogSidebarCollapsed.toString());
        // Save "auto-submit quick actions" setting
        localStorage.setItem(APP_PREFIX + 'autoSubmitQuickActions', state.autoSubmitQuickActions.toString());
        // Save current application mode
        localStorage.setItem(APP_PREFIX + 'currentMode', state.currentMode);
        // Save 3D component visibility state
        localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', state.isIdtComponentVisible.toString());
        // Save 3D component position percentages
        localStorage.setItem(APP_PREFIX + 'idtComponentTopPercent', document.documentElement.style.getPropertyValue('--idt-offset-top-percentage'));
        localStorage.setItem(APP_PREFIX + 'idtComponentLeftPercent', document.documentElement.style.getPropertyValue('--idt-offset-left-percentage'));
        // Log that settings have been saved
        console.log("系统参数数据已保存到归档.");
    }
    /**
     * Loads application settings from localStorage and updates the application state.
     */
    function loadSettings() {
        // Load and apply the saved position of the 3D component (top and left offset percentages)
        const savedTopPercent = localStorage.getItem(APP_PREFIX + 'idtComponentTopPercent');
        const savedLeftPercent = localStorage.getItem(APP_PREFIX + 'idtComponentLeftPercent');
        // If the saved top offset percentage exists in localStorage, apply it to the CSS variable
        if (savedTopPercent !== null) document.documentElement.style.setProperty('--idt-offset-top-percentage', savedTopPercent);
        // If the saved left offset percentage exists in localStorage, apply it to the CSS variable
        if (savedLeftPercent !== null) document.documentElement.style.setProperty('--idt-offset-left-percentage', savedLeftPercent);

        // Load other application settings, use default values if no corresponding item exists in localStorage:
        // Theme setting, defaults to 'auto-crystal'
        state.currentTheme = localStorage.getItem(APP_PREFIX + 'theme') || 'auto-crystal';
        // Animation level, defaults to 'full'
        state.animationLevel = localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full';
        // Auto-scroll, defaults to 'true' (note: localStorage stores strings, need to convert to boolean)
        state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || 'true') === 'true';
        // Sound enabled, defaults to 'false'
        state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || 'false') === 'true';
        // Show thinking process in chat bubbles, defaults to 'true'
        state.showChatBubblesThink = (localStorage.getItem(APP_PREFIX + 'showChatBubblesThink') || 'true') === 'true';
        // Show thinking bubble in log entries, defaults to 'true'
        state.showLogBubblesThink = (localStorage.getItem(APP_PREFIX + 'showLogBubblesThink') || 'true') === 'true';
        // Sidebar expanded state, defaults to determined by window width (expanded if > 1024px)
        state.isSidebarExpanded = (localStorage.getItem(APP_PREFIX + 'sidebarExpanded') || (window.innerWidth > 1024).toString()) === 'true';
        // Session manager collapsed state, defaults to 'false' (not collapsed)
        state.isSessionManagerCollapsed = (localStorage.getItem(APP_PREFIX + 'sessionManagerCollapsed') || 'false') === 'true';
        // Process log sidebar visibility state, defaults to 'false' (not visible)
        state.isProcessLogSidebarVisible = (localStorage.getItem(APP_PREFIX + 'isProcessLogSidebarVisible') || 'false') === 'true';
        // Process log sidebar collapsed state, defaults to 'true' (collapsed)
        state.isProcessLogSidebarCollapsed = (localStorage.getItem(APP_PREFIX + 'isProcessLogSidebarCollapsed') || 'true') === 'true';
        // Auto-submit quick actions, defaults to 'true'
        state.autoSubmitQuickActions = (localStorage.getItem(APP_PREFIX + 'autoSubmitQuickActions') || 'true') === 'true';
        // Current application mode, defaults to 'chat'
        state.currentMode = localStorage.getItem(APP_PREFIX + 'currentMode') || 'chat';
        // 3D component visibility state, defaults to 'true' (visible)
        state.isIdtComponentVisible = (localStorage.getItem(APP_PREFIX + 'isIdtComponentVisible') || 'true') === 'true';

        // Update the state of UI elements to reflect the loaded settings:
        // Update the active state of the sidebar buttons to match the loaded currentMode
        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === state.currentMode));
        // Update the placeholder text of the user input box
        // Note: Session data (state.sessions) might not be fully loaded at this point, so currentSessionId might be null
        // Therefore, the session name part might temporarily show as "当前项目"
        const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
        dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${sessionNameForPlaceholder})...`;
    }
    /**
     * Resets all settings to their default values, applies and saves these default values.
     */
    function resetToDefaultSettings() {
        // Define an object containing all resettable settings and their default values
        const defaults = {
            theme: 'auto-crystal', // Default theme
            fontSize: '16', // Default font size (px)
            animationLevel: 'full', // Default animation level
            autoScroll: true, // Default auto-scroll
            soundEnabled: false, // Default sound disabled
            showChatBubblesThink: true, // Default show thinking process in chat bubbles
            showLogBubblesThink: true, // Default show thinking bubble in log entries
            sidebarExpanded: window.innerWidth > 1024, // Default sidebar expanded state (based on window width)
            sessionManagerCollapsed: false, // Default session manager not collapsed
            isProcessLogSidebarVisible: false, // Default process log sidebar not visible
            isProcessLogSidebarCollapsed: true, // Default process log sidebar collapsed
            autoSubmitQuickActions: true, // Default auto-submit quick actions
            currentMode: 'chat', // Default application mode
            isIdtComponentVisible: true, // Default 3D component visible
            idtComponentTopPercent: '2.5%', // Default 3D component top offset percentage
            idtComponentLeftPercent: '1.8%', // Default 3D component left offset percentage
        };
        // Apply default settings to application state and UI:
        applyTheme(defaults.theme); // Apply default theme
        applyFontSize(defaults.fontSize); // Apply default font size
        applyAnimationLevel(defaults.animationLevel); // Apply default animation level
        // Update various boolean and string settings in state
        state.autoScroll = defaults.autoScroll;
        state.soundEnabled = defaults.soundEnabled;
        state.showChatBubblesThink = defaults.showChatBubblesThink;
        state.showLogBubblesThink = defaults.showLogBubblesThink;
        state.autoSubmitQuickActions = defaults.autoSubmitQuickActions;
        state.currentMode = defaults.currentMode;
        state.isIdtComponentVisible = defaults.isIdtComponentVisible;
        toggleThreeBlackHoleVisibility(state.isIdtComponentVisible); // Apply default 3D component visibility

        // Update UI state to reflect default values:
        updateSidebarState(defaults.sidebarExpanded, true); // Update sidebar state (true for instant update)
        updateSessionManagerState(defaults.sessionManagerCollapsed, true); // Update session manager state (true for instant update)
        // Update process log sidebar state
        state.isProcessLogSidebarVisible = defaults.isProcessLogSidebarVisible;
        state.isProcessLogSidebarCollapsed = defaults.isProcessLogSidebarCollapsed;
        applyFixedLogSidebarLayout(); // Apply layout
        updateProcessLogSidebarCollapseState(state.isProcessLogSidebarCollapsed, true); // Update collapsed state (true for instant update)
        // Show or hide the log sidebar based on default visibility
        if (state.isProcessLogSidebarVisible) showProcessLogSidebar(false); else hideProcessLogSidebar();
        // Update the title and icon of the 3D component toggle button
        dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
        const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
        if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';
        // Reset 3D component position (via CSS variables)
        document.documentElement.style.setProperty('--idt-offset-top-percentage', defaults.idtComponentTopPercent);
        document.documentElement.style.setProperty('--idt-offset-left-percentage', defaults.idtComponentLeftPercent);

        // Update UI control values in the settings modal to reflect the restored default settings:
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

        // Update active state of sidebar buttons and placeholder text of user input box to reflect default mode
        dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === defaults.currentMode));
        const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
        dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${sessionNameForPlaceholder})...`;

        // Save the restored default settings to localStorage
        saveSettings();
        // Show a Toast notification informing the user that settings have been restored to default
        showToast('系统参数已恢复为默认光绘配置!', 'success');
    }

    /**
     * Displays a Toast notification.
     * @param {string} message - The notification message text.
     * @param {string} [type='info'] - The notification type ('info', 'success', 'warning', 'error').
     * @param {number} [duration=3500] - The duration (in milliseconds) the notification should be displayed, 0 for no auto-dismiss.
     */
    function showToast(message, type = 'info', duration = 3500) {
        // If the Toast container element does not exist, log an error and return
        if (!dom.toastContainer) {
            console.error("Toast container element not found."); return;
        }
        // Create a new div element as a Toast notification
        const toast = document.createElement('div');
        // Add base CSS classes ('toast', 'lumina-panel') and specific type class (e.g., 'toast-info')
        toast.classList.add('toast', 'lumina-panel', `toast-${type}`);

        // Choose entry and exit animation classes (Animate.css) based on the animation level
        const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInRight' : 'animate__fadeIn') : '';
        const animOut = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeOutRight' : 'animate__fadeOut') : '';

        // If animations are enabled and an entry animation class was chosen
        if (state.animationLevel !== 'none' && animIn) {
            toast.classList.add('animate__animated', animIn); // Add animation classes
            toast.style.setProperty('--animate-duration', '0.45s'); // Set animation duration
        }

        // Define an object storing notification types and their corresponding FontAwesome icon classes
        const icons = { 'info': 'fa-info-circle', 'success': 'fa-check-circle', 'warning': 'fa-exclamation-triangle', 'error': 'fa-times-circle' };
        // Get the icon class matching the current notification type, default to 'fa-info-circle' if not found
        const iconClass = icons[type] || 'fa-info-circle';

        // Create a span element to display the notification message text
        const messageSpan = document.createElement('span');
        messageSpan.className = 'toast-message'; // Add CSS class
        messageSpan.textContent = message; // Set text content

        // Set the HTML content of the Toast notification, including the icon
        toast.innerHTML = `<i class="fas ${iconClass} toast-icon"></i>`;
        // Append the message text span to the Toast notification
        toast.appendChild(messageSpan);
        // Create a close button
        const closeButton = document.createElement('button');
        closeButton.className = 'toast-close icon-btn'; // Add CSS classes (using generic icon button styles)
        closeButton.innerHTML = '<i class="fas fa-times"></i>'; // Set the button icon (X)
        closeButton.setAttribute('title', '关闭通知'); // Set the tooltip
        // Add a click event listener to the close button, calling the removeToast function
        // Note: pass the animOut parameter to ensure the correct exit animation is used even when manually closed
        closeButton.addEventListener('click', () => removeToast(toast, animOut, true)); // true indicates manual close
        // Append the close button to the Toast notification
        toast.appendChild(closeButton);

        // Append the created Toast notification to the Toast container
        dom.toastContainer.appendChild(toast);

        // If auto-dismiss duration is set (duration > 0)
        if (duration > 0) {
            // Use setTimeout to set a timer to remove the Toast notification after the specified duration
            const timeoutId = setTimeout(() => {
                removeToast(toast, animOut, false); // false indicates non-manual close
            }, duration);
            // Store the timeout ID in the Toast element's data-timeout-id attribute
            // This allows clearing the timer when manually closing, avoiding unnecessary removal operations
            toast.dataset.timeoutId = timeoutId.toString();
        }
    }

    /**
     * Removes a Toast notification.
     * @param {HTMLElement} toast - The Toast DOM element to remove.
     * @param {string} animOut - The animation class name to use for fading out.
     * @param {boolean} [isManualClose=false] - Whether the close was triggered manually by the user.
     */
    function removeToast(toast, animOut, isManualClose = false) {
        // Ensure the Toast element is still present in the DOM (i.e., has a parent element)
        if (toast.parentElement) {
            // If it's a manual close and the Toast element has an auto-close timeoutId stored
            if (isManualClose && toast.dataset.timeoutId) {
                // Clear that timeout to prevent it from attempting to remove the Toast after manual close
                clearTimeout(parseInt(toast.dataset.timeoutId, 10));
            }

            // Handle animation and removal logic:
            // If animations are enabled, an exit animation class was chosen, and the Toast element currently has the 'animate__animated' class
            if (state.animationLevel !== 'none' && animOut && toast.classList.contains('animate__animated')) {
                // Remove any potential entry animation classes (just in case)
                toast.classList.remove('animate__fadeInRight', 'animate__fadeIn');
                // Add the exit animation class
                toast.classList.add(animOut);
                toast.style.setProperty('--animate-duration', '0.3s'); // Set the duration of the exit animation
                // Listen for the animation end event
                toast.addEventListener('animationend', () => {
                    // After the animation finishes, check again if the Toast is still in the DOM (in case it was removed by other means during the animation)
                    if (toast.parentElement) {
                        toast.remove(); // Remove the Toast element from the DOM
                    }
                }, { once: true }); // once: true means the event triggers only once
            } else {
                // If animations are not enabled, or the animation class doesn't apply, remove the Toast element directly from the DOM
                toast.remove();
            }
        }
    }

    /**
     * Attaches click event listeners to all quick action buttons (.quick-action-btn) within the specified container.
     * @param {HTMLElement} container - The parent container element containing the quick action buttons.
     */
    function attachQuickActionButtonListeners(container) {
        // Find all elements with the 'quick-action-btn' CSS class within the container
        container.querySelectorAll('.quick-action-btn').forEach(button => {
            // First, remove any existing identical event listener (handleQuickActionButtonClick) on this button
            // This prevents duplicate listeners if this function is called multiple times
            button.removeEventListener('click', handleQuickActionButtonClick);
            // Then, add a new click event listener to the button, specifying handleQuickActionButtonClick as the callback function
            button.addEventListener('click', handleQuickActionButtonClick);
        });
    }
    /**
     * Handles the click event of a quick action button.
     * Fills the user input box with the text from the button's data-message attribute and sends the message automatically based on settings.
     * @param {MouseEvent} e - The click event object.
     */
    function handleQuickActionButtonClick(e) {
        // Prevent the default behavior of the link (<a> tag) (e.g., page navigation or scrolling to an anchor)
        e.preventDefault();
        // Get the clicked button (or its nearest parent element with the 'quick-action-btn' class, to handle clicking the icon)
        // Then get the message text to send from its 'data-message' attribute
        const messageToSend = e.target.closest('.quick-action-btn').dataset.message;
        // If message text was successfully retrieved
        if (messageToSend) {
            dom.userInput.value = messageToSend; // Fill the user input box with the message text
            adjustTextareaHeight(); // Adjust the input box height to fit the new content
            updateCharCounter(); // Update the character counter
            dom.userInput.focus(); // Set focus to the input box, making it easy for the user to continue editing or send directly
            // If the "auto-submit quick actions" setting is enabled in the application settings (state.autoSubmitQuickActions is true)
            if (state.autoSubmitQuickActions) {
                handleSendMessage(); // Call the function to send the message automatically
            }
        }
    }
    /**
     * Updates the CSS variable `--input-area-height` to reflect the actual height of the current input area.
     * This might be useful for absolutely positioned elements that depend on this height (like the bottom positioning of the right process log sidebar).
     */
    function updateInputAreaHeightVar() {
        // If the input area DOM element exists
        if (dom.inputArea) {
            // Get the actual height of the input area (offsetHeight includes padding and border)
            const heightPx = dom.inputArea.offsetHeight;
            // Set a CSS variable named '--input-area-height' on the document's root element (documentElement)
            // Its value is the actual height of the input area (in pixels)
            document.documentElement.style.setProperty('--input-area-height', `${heightPx}px`);
            // If the right process log sidebar container exists AND is currently visible
            if (dom.processLogSidebarContainer && state.isProcessLogSidebarVisible) {
                // Note: The CSS already uses var(--input-area-height) for positioning,
                // so there's no need to directly modify its bottom style here via JavaScript.
                // dom.processLogSidebarContainer.style.bottom = `calc(${heightPx}px + var(--spacing-unit) * 2)`;
            }
        }
    }


    // Initialize the application
    // Call the initializeApp function to begin the entire frontend application initialization process.
    initializeApp();

}); // End of DOMContentLoaded (Executes the callback function after the entire HTML document has been loaded and parsed)
