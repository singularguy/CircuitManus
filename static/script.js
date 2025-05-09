// 严格模式，老板，精益求精！
"use strict";

document.addEventListener('DOMContentLoaded', () => {
    // ======== DOM 元素获取 (集中管理) ========
    const dom = {
        loader: document.getElementById('loader'),
        loaderProgress: document.querySelector('.loader-progress'),
        mainContainer: document.getElementById('main-container'),
        chatBox: document.getElementById('chat-box'),
        userInput: document.getElementById('user-input'),
        sendButton: document.getElementById('send-button'),
        sendIcon: document.querySelector('.send-icon'),
        sendLoadingIcon: document.querySelector('.send-loading-icon'),
        themeToggleButton: document.getElementById('theme-toggle'),
        themeToggleIcon: document.querySelector('#theme-toggle i'),
        clearChatButton: document.getElementById('clear-chat'),
        manageSessionsToggle: document.getElementById('manage-sessions-toggle'), // 头部会话管理按钮
        sidebar: document.getElementById('sidebar'),
        sidebarButtons: document.querySelectorAll('.sidebar-button'),
        sessionManager: document.getElementById('session-manager'),
        sessionManagerToggle: document.getElementById('session-manager-toggle'),
        sessionListContainer: document.getElementById('session-list-container'),
        sessionList: document.getElementById('session-list'),
        createNewSessionButton: document.getElementById('create-new-session'),
        chatHeader: document.getElementById('chat-header'),
        currentSessionNameDisplay: document.getElementById('current-session-name'),
        editSessionNameButton: document.getElementById('edit-session-name-btn'),
        attachButton: document.getElementById('attach-button'),
        micButton: document.getElementById('mic-button'),
        charCounter: document.getElementById('char-counter'),
        fileInput: document.getElementById('file-input'),
        filePreviewArea: document.getElementById('file-preview'),
        filePreviewContent: document.getElementById('file-preview-content'),
        closeFilePreviewButton: document.getElementById('close-preview'),
        toastContainer: document.getElementById('toast-container'),
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
    const APP_PREFIX = 'IDTAgentPro_v8_'; // localStorage 前缀
    let state = {
        sessions: {}, // { [sessionId]: { id, name, messages: [], createdAt, lastActivity } }
        currentSessionId: null,
        currentTheme: 'auto',
        autoScroll: true,
        soundEnabled: false,
        showThinkBubbles: true,
        animationLevel: 'full', // 'full', 'basic', 'none'
        currentMode: 'chat',
        uploadedFiles: [],
        isAgentTyping: false,
        isLoading: false,
        isSidebarExpanded: false, // 侧边栏展开状态
        isSessionManagerCollapsed: true, // 会话历史折叠状态
        maxInputChars: 2000,
    };

    // ======== 初始化函数 ========
    async function initializeApp() {
        console.log("IDT Agent Pro 初始化开始...");
        updateLoaderProgress(10);

        // 0. 加载设置和会话
        loadSettings();
        loadSessions(); // 加载会话数据
        updateLoaderProgress(30);

        // 1. 应用初始主题、字体、动画级别
        applyTheme(state.currentTheme);
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
        applyAnimationLevel(state.animationLevel);
        updateLoaderProgress(50);

        // 2. 设置事件监听器
        setupEventListeners();
        updateLoaderProgress(70);

        // 3. 调整输入框及显示初始会话
        adjustTextareaHeight();
        initializeCurrentSession(); // 决定并加载初始会话
        updateCharCounter();
        updateLoaderProgress(90);

        // 4. 隐藏加载动画，显示主内容
        setTimeout(() => {
            dom.loaderProgress.style.width = '100%'; // 确保进度条满
            setTimeout(() => {
                dom.loader.classList.add('hidden');
                dom.mainContainer.classList.add('loaded');
                showToast('欢迎回来，指挥官！系统已准备就绪。', 'info', 4000);
            }, 400); // 给进度条跑满一点时间
        }, 200); // 模拟一些加载时间

        console.log("IDT Agent Pro 初始化完成!");
    }

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
        dom.manageSessionsToggle.addEventListener('click', toggleSidebarExpansion); // 头部按钮控制侧边栏

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

        // 设置模态框事件
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
            if (state.animationLevel !== 'none') { // 仅在有动画时实时预览
                 document.body.style.transition = 'font-size 0.1s ease-out'; // 临时快速过渡
            }
            document.body.style.fontSize = `${newSize}px`;
            requestAnimationFrame(() => { // 清除临时过渡，避免影响全局设置
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
            // 此处不保存，由“保存设置”统一处理
        });
    }
    
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

    function initializeCurrentSession() {
        const lastSessionId = localStorage.getItem(APP_PREFIX + 'lastSessionId');
        if (lastSessionId && state.sessions[lastSessionId]) {
            switchSession(lastSessionId);
        } else if (Object.keys(state.sessions).length > 0) {
            // 如果没有lastSessionId记录，但存在会话，则加载最新的一个
            const sortedSessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
            switchSession(sortedSessions[0].id);
        } else {
            createNewSession(true); // 创建一个新会话作为初始会话, true表示不显示toast
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
        state.currentSessionId = newId;
        saveSessions();
        switchSession(newId); // 会自动渲染列表和聊天框
        if (!isInitial) {
            showToast('新的通讯链路已建立!', 'success');
            if (!state.isSidebarExpanded) toggleSidebarExpansion(); // 如果侧边栏收起则展开
            if (state.isSessionManagerCollapsed) toggleSessionManagerCollapse(); // 如果会话历史收起则展开
        }
        return newId;
    }

    function switchSession(sessionId) {
        if (!state.sessions[sessionId]) {
            console.error(`尝试切换到不存在的会话: ${sessionId}`);
            // 可以选择创建一个新会话或加载一个默认的
            if (Object.keys(state.sessions).length > 0) {
                switchSession(Object.keys(state.sessions)[0]); // 切换到第一个存在的会话
            } else {
                createNewSession(true);
            }
            return;
        }
        state.currentSessionId = sessionId;
        state.sessions[sessionId].lastActivity = Date.now(); // 更新活动时间
        localStorage.setItem(APP_PREFIX + 'lastSessionId', sessionId);
        saveSessions();
        
        dom.currentSessionNameDisplay.textContent = state.sessions[sessionId].name;
        dom.chatBox.innerHTML = ''; // 清空当前聊天框
        // 加载会话消息 (如果消息是HTML，要小心XSS，这里仅简单处理)
        state.sessions[sessionId].messages.forEach(msg => {
            // 后端返回的response可能包含<think>标签, 需要在渲染时重新解析
            if (msg.sender === 'agent' && msg.rawResponse) {
                 const { thinkContent, mainMessage } = parseAgentResponse(msg.rawResponse);
                 appendMessage(mainMessage, msg.sender, msg.isHTML, thinkContent && state.showThinkBubbles ? thinkContent : null, true);
            } else {
                 appendMessage(msg.content, msg.sender, msg.isHTML, null, true); // true for isSwitchingSession
            }
        });
        scrollToBottom(true); // 切换后立即滚动到底部
        renderSessionList(); // 更新列表高亮
        dom.userInput.focus();
        console.log(`已切换到会话: ${state.sessions[sessionId].name} (ID: ${sessionId})`);
    }

    function deleteSession(sessionId, event) {
        if (event) event.stopPropagation(); // 防止触发切换会话

        if (!state.sessions[sessionId]) return;

        const sessionName = state.sessions[sessionId].name;
        // 添加确认步骤
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
            // 如果删除的是当前会话，切换到最新或新建一个
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
        // renderSessionList(); // switchSession会调用它
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
            renderSessionList(); // 更新列表中的名称
            showToast("会话名称已更新。", "success");
        }
    }


    function renderSessionList() {
        dom.sessionList.innerHTML = ''; // 清空列表
        const sortedSessions = Object.values(state.sessions)
            .sort((a, b) => b.lastActivity - a.lastActivity); // 按最后活动时间降序

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
             if (state.animationLevel === 'full') { // 仅在full动画时添加进场
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
            state.sessions = JSON.parse(storedSessions);
        } else {
            state.sessions = {};
        }
    }

    function toggleSidebarExpansion() {
        state.isSidebarExpanded = !state.isSidebarExpanded;
        dom.sidebar.classList.toggle('expanded', state.isSidebarExpanded);
        // 如果展开侧边栏时会话历史是折叠的，也把它展开
        if (state.isSidebarExpanded && state.isSessionManagerCollapsed) {
            // toggleSessionManagerCollapse(); // 避免重复动画，仅当必要时
        } else if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
             // 如果收起侧边栏时会话历史是展开的，则收起会话历史
            toggleSessionManagerCollapse();
        }
    }
    function toggleSessionManagerCollapse() {
        // 只有在侧边栏展开时才能操作会话历史的折叠
        if (!state.isSidebarExpanded && state.isSessionManagerCollapsed) {
            // 如果侧边栏是收起的，且会话历史也是收起的，则先展开侧边栏
            toggleSidebarExpansion();
            // 然后确保会话历史是展开的
            if(state.isSessionManagerCollapsed) { // 再次检查，因为 toggleSidebarExpansion 可能改变它
                 state.isSessionManagerCollapsed = !state.isSessionManagerCollapsed;
                 dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
            }
            return;
        }
        if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
            // 如果侧边栏收起但历史展开 (理论上不应发生，除非手动改了状态)，先强制收起历史
            state.isSessionManagerCollapsed = true;
            dom.sessionManager.classList.add('collapsed');
            return;
        }


        state.isSessionManagerCollapsed = !state.isSessionManagerCollapsed;
        dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
    }


    // ======== 核心聊天功能 ========
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
        
        state.isLoading = true;
        dom.sendButton.disabled = true;
        dom.sendIcon.style.display = 'none';
        dom.sendLoadingIcon.style.display = 'inline-block';

        let userMessageDisplay = messageText;
        if (filesToSend.length > 0) {
            userMessageDisplay += `\n\n<div class="message-attachment-summary"><i class="fas fa-paperclip"></i> 附件 (${filesToSend.length}): ${filesToSend.map(f => `<span class="filename-chip">${f.name}</span>`).join(' ')}</div>`;
        }
        
        // 将消息保存到当前会话
        const currentUserMessage = {
            content: userMessageDisplay, // 保存展示用的HTML
            sender: 'user',
            timestamp: Date.now(),
            isHTML: true, // 因为可能包含附件信息
        };
        addMessageToCurrentSession(currentUserMessage);
        appendMessage(userMessageDisplay, 'user', true);

        // 自动命名会话 (如果当前会话名是默认的，并且这是第一条用户消息)
        const currentSession = state.sessions[state.currentSessionId];
        if (currentSession && currentSession.name.startsWith("会话 ") && currentSession.messages.filter(m => m.sender === 'user').length === 1) {
            const autoName = messageText.substring(0, 25).trim() || "新对话";
            currentSession.name = autoName + (messageText.length > 25 ? "..." : "");
            dom.currentSessionNameDisplay.textContent = currentSession.name;
            renderSessionList(); // 更新侧边栏列表
        }


        dom.userInput.value = '';
        adjustTextareaHeight();
        updateCharCounter();
        closeFilePreview();
        state.uploadedFiles = []; 

        showTypingIndicator();

        try {
            let backendMessage = messageText;
            if (filesToSend.length > 0) {
                backendMessage += `\n[用户上传了文件: ${filesToSend.map(f => f.name).join(', ')}]`;
            }

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: state.currentSessionId, message: backendMessage })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ response: `服务器通信异常 (状态 ${response.status})`, error: true }));
                throw new Error(errorData.response || `服务器发生错误 (状态 ${response.status})`);
            }

            const data = await response.json();
            hideTypingIndicator();

            const agentMessageData = {
                sender: data.error ? 'error' : 'agent',
                timestamp: Date.now(),
                isHTML: false, // 主内容通常是文本，除非后端显式指定
                rawResponse: data.response, // 保存原始响应，包含<think>
            };
             // 后端返回的response是字符串，解析后得到 thinkContent 和 mainMessage
            const { thinkContent, mainMessage } = parseAgentResponse(data.response);
            agentMessageData.content = mainMessage; // content存解析后的主消息

            addMessageToCurrentSession(agentMessageData);
            appendMessage(mainMessage, agentMessageData.sender, false, thinkContent && state.showThinkBubbles ? thinkContent : null);
            
            if (data.error) showToast("处理请求时发生错误。", "error");

        } catch (error) {
            console.error('发送消息时出错:', error);
            hideTypingIndicator();
            const errorMessage = { content: `抱歉，与服务器通信失败: ${error.message}`, sender: 'error', timestamp: Date.now(), isHTML: false };
            addMessageToCurrentSession(errorMessage);
            appendMessage(errorMessage.content, 'error');
            showToast(`请求失败: ${error.message}`, 'error');
        } finally {
            state.isLoading = false;
            dom.sendButton.disabled = false;
            dom.sendIcon.style.display = 'inline-block';
            dom.sendLoadingIcon.style.display = 'none';
            dom.userInput.focus();
            state.sessions[state.currentSessionId].lastActivity = Date.now(); // 更新活动时间
            saveSessions();
            renderSessionList(); // 可能因为活动时间变化需要重排
        }
    }
    
    function addMessageToCurrentSession(messageObject) {
        if (state.sessions[state.currentSessionId]) {
            state.sessions[state.currentSessionId].messages.push(messageObject);
            saveSessions();
        }
    }

    function parseAgentResponse(responseText = "") { // 添加默认值防止 undefined
        const thinkTagStart = "<think>";
        const thinkTagEnd = "</think>";
        let thinkContent = null;
        let mainMessage = responseText;

        if (typeof responseText !== 'string') { // 健壮性处理
            console.warn("parseAgentResponse 收到非字符串响应:", responseText);
            return { thinkContent: null, mainMessage: String(responseText) };
        }

        const thinkStartIndex = responseText.indexOf(thinkTagStart);
        const thinkEndIndex = responseText.indexOf(thinkTagEnd, thinkStartIndex);

        if (thinkStartIndex !== -1 && thinkEndIndex !== -1 && thinkEndIndex > thinkStartIndex) {
            thinkContent = responseText.substring(thinkStartIndex + thinkTagStart.length, thinkEndIndex).trim();
            let messageStartIndex = thinkEndIndex + thinkTagEnd.length;
            while (responseText[messageStartIndex] === '\n' || responseText[messageStartIndex] === '\r') {
                messageStartIndex++;
            }
            mainMessage = responseText.substring(messageStartIndex).trim();
        }
        return { thinkContent, mainMessage };
    }

    function handleUserInputKeypress(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleSendMessage();
        }
    }

    function appendMessage(content, sender, isHTML = false, thinkContent = null, isSwitchingSession = false) {
        const messageDiv = document.createElement('div');
        const animationClass = state.animationLevel === 'full' ? 'animate__fadeInUp' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
        messageDiv.classList.add('message', `${sender}-message`, 'animate__animated', animationClass);
        if (state.animationLevel !== 'none' && !isSwitchingSession) {
            messageDiv.style.setProperty('--animate-duration', state.animationLevel === 'full' ? '0.5s' : '0.3s');
        } else if (isSwitchingSession) { // 切换会话时，消息不应该有入场动画
             messageDiv.classList.remove('animate__animated', animationClass);
        }
        
        const messageContentDiv = document.createElement('div');
        messageContentDiv.classList.add('message-content');

        if (thinkContent && sender === 'agent') {
            const thinkBubble = document.createElement('div');
            thinkBubble.classList.add('think-bubble');
            thinkBubble.innerHTML = `<i class="fas fa-lightbulb fa-beat" style="--fa-animation-duration: 1.5s;"></i> <span>${thinkContent.replace(/\n/g, '<br>')}</span>`;
            messageContentDiv.appendChild(thinkBubble);
        }

        if (isHTML) {
            messageContentDiv.insertAdjacentHTML('beforeend', content);
        } else {
            const textNodeContainer = document.createElement('div');
            // 将纯文本中的URL转为可点击链接 (简单版本)
            const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
            const linkedContent = content.replace(/\n/g, '<br>').replace(urlRegex, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
            textNodeContainer.innerHTML = linkedContent;
            messageContentDiv.appendChild(textNodeContainer);
        }
        
        messageDiv.appendChild(messageContentDiv);
        dom.chatBox.appendChild(messageDiv);
        
        if (!isSwitchingSession) { // 只有新消息才滚动
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
        if (state.isAgentTyping) return; state.isAgentTyping = true;
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        const animationClass = state.animationLevel !== 'none' ? 'animate__fadeInUp' : '';
        typingDiv.classList.add('message', 'agent-message', 'typing-indicator', 'animate__animated', animationClass);
        if (state.animationLevel !== 'none') typingDiv.style.setProperty('--animate-duration', '0.3s');
        
        let dotsHTML = Array(3).fill('<span class="typing-dot"></span>').join('');
        typingDiv.innerHTML = `IDT Agent Pro 正在分析<span class="typing-dots">${dotsHTML}</span>`;
        dom.chatBox.appendChild(typingDiv); scrollToBottom();
    }

    function hideTypingIndicator() {
        if (!state.isAgentTyping) return; state.isAgentTyping = false;
        const typingElement = document.getElementById('typing-indicator');
        if (typingElement) {
            if (state.animationLevel !== 'none') {
                typingElement.classList.replace('animate__fadeInUp', 'animate__fadeOutDown') || typingElement.classList.add('animate__fadeOutDown');
                typingElement.addEventListener('animationend', () => typingElement.remove(), { once: true });
            } else {
                typingElement.remove();
            }
        }
    }
    
    function adjustTextareaHeight() {
        dom.userInput.style.height = 'auto';
        let scrollHeight = dom.userInput.scrollHeight;
        const maxHeight = parseInt(getComputedStyle(dom.userInput).maxHeight, 10) || 150;
        
        if (scrollHeight > maxHeight) {
            dom.userInput.style.height = maxHeight + 'px';
            dom.userInput.style.overflowY = 'auto';
        } else {
            const minHeight = parseInt(getComputedStyle(dom.userInput).minHeight, 10) || 50;
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

        state.sessions[state.currentSessionId].messages = []; // 清空消息数组
        saveSessions(); // 保存更改
        dom.chatBox.innerHTML = ''; // 清空显示
        // 可以选择添加一条系统提示
        const welcomeMsg = dom.chatBox.querySelector('.system-message.animate__animated.animate__fadeInUp'); // Assume it's always there
        if (welcomeMsg) { // Re-add it if it was removed
            dom.chatBox.appendChild(welcomeMsg.cloneNode(true));
        } else { // Or add a generic one
             appendMessage("当前会话已清空。", "system");
        }
        showToast('当前会话消息已清空!', 'info');
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

    // ======== 文件上传与预览 (与之前版本类似，仅作微调) ========
    function handleFileSelection(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        const MAX_FILES = 5, MAX_SIZE_MB = 5; // 略微放宽
        
        files.forEach(file => {
            if (state.uploadedFiles.length >= MAX_FILES) { showToast(`最多只能上传 ${MAX_FILES} 个文件。`, 'warning'); return; }
            if (file.size > MAX_SIZE_MB * 1024 * 1024) { showToast(`文件 "${file.name}" 过大 (>${MAX_SIZE_MB}MB)。`, 'warning'); return; }
            if (!state.uploadedFiles.find(f => f.name === file.name && f.size === file.size)) {
                 state.uploadedFiles.push(file); addFileToPreview(file);
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
        fileItem.innerHTML = `<i class="fas ${getFileIconClass(file.type, file.name)} file-icon"></i><span class="file-name" title="${file.name}">${file.name}</span><button class="file-remove icon-btn" title="移除"><i class="fas fa-times-circle"></i></button>`;
        fileItem.querySelector('.file-remove').addEventListener('click', (e) => { e.stopPropagation(); removeFileFromPreview(file.name); });
        dom.filePreviewContent.appendChild(fileItem);
    }
    function getFileIconClass(fileType, fileName) { /* 同前 */ 
        if (fileType.startsWith('image/')) return 'fa-file-image';
        if (fileType.startsWith('audio/')) return 'fa-file-audio';
        if (fileType.startsWith('video/')) return 'fa-file-video';
        if (fileType === 'application/pdf') return 'fa-file-pdf';
        if (fileType === 'application/zip' || fileName.endsWith('.zip') || fileName.endsWith('.rar')) return 'fa-file-archive';
        if (fileType.includes('text') || fileName.endsWith('.txt') || fileName.endsWith('.md')) return 'fa-file-alt';
        if (fileName.endsWith('.doc') || fileName.endsWith('.docx')) return 'fa-file-word';
        if (fileName.endsWith('.xls') || fileName.endsWith('.xlsx')) return 'fa-file-excel';
        if (fileName.endsWith('.ppt') || fileName.endsWith('.pptx')) return 'fa-file-powerpoint';
        if (fileName.endsWith('.js') || fileName.endsWith('.py') || fileName.endsWith('.java') || fileName.endsWith('.cs') || fileName.endsWith('.html') || fileName.endsWith('.css')) return 'fa-file-code';
        return 'fa-file';
    }
    function removeFileFromPreview(fileName) {
        state.uploadedFiles = state.uploadedFiles.filter(f => f.name !== fileName);
        const fileItemElement = dom.filePreviewContent.querySelector(`.file-item[data-file-name="${CSS.escape(fileName)}"]`);
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
        } else {
            document.body.classList.add('light-theme');
            if (themeName !== 'auto') dom.themeToggleIcon.classList.add('fa-moon');
        }
        state.currentTheme = themeName;
        if (dom.themeSelect.value !== themeName) dom.themeSelect.value = themeName;
        console.log(`主题已应用: ${themeName} (生效: ${newTheme})`);
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
        document.body.dataset.animationLevel = level; // 用data属性控制CSS中的动画启用
        state.animationLevel = level;
        if (dom.animationLevelSelect.value !== level) dom.animationLevelSelect.value = level;
        console.log(`动画级别已设置为: ${level}`);
        // 更新animate.css的全局速度 (如果需要更细致的控制)
        // document.documentElement.style.setProperty('--animate-duration', level === 'full' ? '1s' : (level === 'basic' ? '0.5s' : '0s'));
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
        modalContent.classList.remove('animate__fadeOutDown', 'animate__zoomOut');
        modalContent.classList.add(state.animationLevel !== 'none' ? 'animate__fadeInUp' : 'animate__fadeIn'); // 或 'animate__zoomIn'
        if (state.animationLevel !== 'none') modalContent.style.setProperty('--animate-duration', '0.4s');
    }

    function closeSettingsModal() {
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16'); // 恢复未保存的字体更改
        applyAnimationLevel(localStorage.getItem(APP_PREFIX + 'animationLevel') || 'full'); // 恢复未保存的动画级别

        const modalContent = dom.settingsModal.querySelector('.modal-content');
        modalContent.classList.remove('animate__fadeInUp', 'animate__zoomIn', 'animate__fadeIn');
        modalContent.classList.add(state.animationLevel !== 'none' ? 'animate__fadeOutDown' : 'animate__fadeOut'); // 或 'animate__zoomOut'
        
        const animationEndHandler = () => {
            dom.settingsModal.style.display = 'none';
            modalContent.removeEventListener('animationend', animationEndHandler);
        };
        if (state.animationLevel !== 'none') {
             modalContent.addEventListener('animationend', animationEndHandler, { once: true });
        } else {
            dom.settingsModal.style.display = 'none'; // 无动画则直接隐藏
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

    // ======== Toast 通知 (与之前版本类似，仅作微调) ========
    function showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.classList.add('toast', type);
        const animIn = state.animationLevel === 'full' ? 'animate__fadeInRight' : (state.animationLevel === 'basic' ? 'animate__fadeIn' : '');
        const animOut = state.animationLevel === 'full' ? 'animate__fadeOutRight' : (state.animationLevel === 'basic' ? 'animate__fadeOut' : '');
        if (state.animationLevel !== 'none') toast.classList.add('animate__animated', animIn);
        
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

    // ======== 启动应用 ========
    initializeApp();
});