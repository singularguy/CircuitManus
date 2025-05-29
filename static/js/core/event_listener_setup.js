// ==========================================================================
// [ START OF FILE core/event_listener_setup.js ]
// Setup for all primary DOM event listeners.
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from './state.js';
import { sendWebSocketMessage } from './websocket_manager.js';
import { adjustTextareaHeight, updateCharCounter, showToast, setLoadingState, appendWelcomeMessage, appendMessage } from './ui_updater.js';
import { applyTheme, applyAnimationLevel, applyFontSize } from '../modules/theme_handler.js';
import { openSettingsModal, closeSettingsModal, collectAndSaveSettings, resetToDefaultSettings } from '../modules/settings_handler.js';
// 【老板，修改！】从 session_handler.js 导入的函数现在包含 showHistoricalLogsForRequest
import { createNewSession, handleEditSessionName, saveSessions, renderSessionList, addMessageToCurrentSession, showHistoricalLogsForRequest } from '../modules/session_handler.js';
import { updateSidebarState, updateSessionManagerState, updateInputAreaHeightVar, applyFixedLogSidebarLayout, toggleProcessLogSidebarCollapse, hideProcessLogSidebar, showProcessLogSidebar } from '../modules/layout_handler.js';
import { handleFileSelection, closeFilePreview } from '../modules/file_handler.js';
import { toggleThreeBlackHoleVisibility, handleComponentMouseDown } from '../modules/three_visuals.js';
import { handleChatBoxMouseOver, handleChatBoxMouseOut } from '../modules/copy_handler.js';
import { generateClientRequestId, getThemeDisplayName, getModeDisplayName, APP_PREFIX } from '../utils/helpers.js';


export function setupEventListeners() {
    dom.sendButton.addEventListener('click', handleSendMessage);
    dom.userInput.addEventListener('keypress', handleUserInputKeypress);
    dom.userInput.addEventListener('input', () => {
        adjustTextareaHeight();
        updateCharCounter();
        updateInputAreaHeightVar();
    });

    dom.themeToggleButton.addEventListener('click', () => {
        const themes = ['auto-crystal', 'light-crystal', 'dark-crystal'];
        const currentIndex = themes.indexOf(state.currentTheme);
        const nextTheme = themes[(currentIndex + 1) % themes.length];
        applyTheme(nextTheme);
        showToast(`显示模式已切换至: ${getThemeDisplayName(state.currentTheme)}`, 'info');
    });

    dom.clearChatButton.addEventListener('click', handleClearCurrentChat);
    if (dom.leftSidebarToggle) {
        dom.leftSidebarToggle.addEventListener('click', () => updateSidebarState(!state.isSidebarExpanded));
    }
    dom.toggleProcessLogVisibilityButton.addEventListener('click', () => {
        if (state.isProcessLogSidebarVisible) hideProcessLogSidebar();
        else showProcessLogSidebar(false);
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
    dom.micButton.addEventListener('click', () => showToast('语音墨迹: 校准中...', 'info'));

    if (dom.closeSettingsButton) dom.closeSettingsButton.addEventListener('click', () => closeSettingsModal(true));
    if (dom.saveSettingsButton) dom.saveSettingsButton.addEventListener('click', () => {
        collectAndSaveSettings();
        closeSettingsModal(false);
        showToast('系统参数已同步!', 'success');
    });
    if (dom.resetSettingsButton) dom.resetSettingsButton.addEventListener('click', resetToDefaultSettings);

    if (dom.fontSizeInput) {
        dom.fontSizeInput.addEventListener('input', () => {
            const newSize = dom.fontSizeInput.value;
            if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${newSize}px`;
            applyFontSize(newSize);
        });
    }
    if (dom.animationLevelSelect) dom.animationLevelSelect.addEventListener('change', (e) => applyAnimationLevel(e.target.value));
    if (dom.autoScrollToggle) dom.autoScrollToggle.addEventListener('change', (e) => { state.autoScroll = e.target.checked; });
    if (dom.soundEnabledToggle) dom.soundEnabledToggle.addEventListener('change', (e) => { state.soundEnabled = e.target.checked; });
    if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.addEventListener('change', (e) => { state.showChatBubblesThink = e.target.checked; });
    if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.addEventListener('change', (e) => { state.showLogBubblesThink = e.target.checked; });
    if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.addEventListener('change', (e) => { state.autoSubmitQuickActions = e.target.checked; });

    if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.addEventListener('change', (e) => {
        state.isIdtComponentVisible = e.target.checked;
        toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);
        dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
        const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
        if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';
        localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', state.isIdtComponentVisible.toString());
    });

    if (dom.settingsModal) dom.settingsModal.addEventListener('click', (e) => {
        if (e.target === dom.settingsModal) closeSettingsModal(true);
    });

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (state.currentTheme === 'auto-crystal') applyTheme(state.currentTheme, true);
    });

    if (dom.toggleProcessLogSidebarCollapseButton) dom.toggleProcessLogSidebarCollapseButton.addEventListener('click', () => toggleProcessLogSidebarCollapse());
    if (dom.closeProcessLogSidebarButton) dom.closeProcessLogSidebarButton.addEventListener('click', () => hideProcessLogSidebar());

    if (dom.idtComponentToggleBtn && dom.idtComponentWrapper) {
        dom.idtComponentToggleBtn.addEventListener('click', () => {
            state.isIdtComponentVisible = !dom.idtComponentWrapper.classList.contains('is-visible');
            toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);
            dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
            const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
            if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';
            if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;
            localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', state.isIdtComponentVisible.toString());
        });
    }
    if (dom.idtComponentWrapper) {
        dom.idtComponentWrapper.addEventListener('mousedown', handleComponentMouseDown);
    }

    window.addEventListener('resize', () => {
        updateInputAreaHeightVar();
        applyFixedLogSidebarLayout();
        if (state.threeJsInitialized && state.threeJsCamera && state.threeJsRenderer && dom.idtComponentWrapper) {
            const Rcontainer = dom.idtComponentWrapper;
            state.threeJsCamera.aspect = Rcontainer.clientWidth / Rcontainer.clientHeight;
            state.threeJsCamera.updateProjectionMatrix();
            state.threeJsRenderer.setSize(Rcontainer.clientWidth, Rcontainer.clientHeight);
        }
    });

    dom.chatBox.addEventListener('mouseover', handleChatBoxMouseOver);
    dom.chatBox.addEventListener('mouseout', handleChatBoxMouseOut);

    // 【老板，新增事件委托！】为聊天框添加事件委托，用于处理动态添加的“查看执行日志”按钮
    dom.chatBox.addEventListener('click', function(event) {
        const target = event.target.closest('.view-execution-logs-btn');
        if (target) {
            event.stopPropagation(); // 阻止事件冒泡到其他消息气泡的监听器（如果存在）
            const clientReqId = target.dataset.clientRequestId;
            const agentReqId = target.dataset.agentRequestId;
            if (clientReqId || agentReqId) { // 确保至少有一个ID
                showHistoricalLogsForRequest(state.currentSessionId, clientReqId, agentReqId);
            } else {
                console.warn("查看历史日志按钮被点击，但未能获取到有效的请求ID。");
                showToast("无法加载历史日志：缺少请求标识。", "warning");
            }
        }
    });
}

function handleSendMessage() {
    if (state.isLoading) {
        showToast("Lumina核心正在处理上一指令. 请稍候...", "warning");
        return;
    }
    const messageText = dom.userInput.value.trim();
    const filesToSend = [...state.uploadedFiles];

    if (messageText === '' && filesToSend.length === 0) {
        showToast("需要指令. 请输入指令或附加数据模块.", "warning");
        return;
    }
    if (dom.userInput.value.length > state.maxInputChars) {
        showToast(`指令缓冲区溢出. 最大 ${state.maxInputChars} 字符.`, "error");
        return;
    }
    
    // WebSocket 检查移到 sendWebSocketMessage 内部

    setLoadingState(true);
    state.currentClientRequestId = generateClientRequestId(); // 【老板，关键！】生成并存储当前请求的客户端ID
    state.lastResponseThinking = null;

    // 【老板，关键！】为当前请求初始化一个日志集合
    if (state.sessions[state.currentSessionId] && state.sessions[state.currentSessionId].executionLogs) {
        state.currentRequestLogCollection = {
            userRequestContent: messageText, // 存储用户原始请求文本
            clientRequestId: state.currentClientRequestId,
            agentRequestId: null, // Agent的ID将在稍后从服务器响应中获取
            timestamp: Date.now(),
            logItems: [], // 用于收集此请求的所有日志条目
            finalStatus: "pending"
        };
        // 不立即推入 session.executionLogs，在请求结束时再推
    } else {
        console.error("当前会话或其 executionLogs 未初始化，无法记录请求日志。");
        state.currentRequestLogCollection = null; //确保它为空
    }


    const currentUserMessage = {
        content: messageText,
        sender: 'user',
        timestamp: Date.now(),
        isHTML: false,
        attachments: filesToSend.map(f => ({ name: f.name, size: f.size, type: f.type })),
        clientRequestId: state.currentClientRequestId // 【老板，新增！】将客户端请求ID与用户消息关联
    };
    addMessageToCurrentSession(currentUserMessage);
    appendMessage(
        messageText, 
        'user', 
        false, // isHTML
        null,  // thinkContent
        false, // isSwitchingSession
        currentUserMessage.attachments,
        null, // errorType
        state.currentClientRequestId // 【老板，新增！】传递 clientRequestId
    );

    const currentSession = state.sessions[state.currentSessionId];
    if (currentSession && currentSession.name.startsWith("光绘墨迹项目 ") && currentSession.messages.filter(m => m.sender === 'user').length === 1) {
        const autoName = messageText.substring(0, 40).trim() || "新墨迹";
        currentSession.name = autoName + (messageText.length > 40 ? "..." : "");
        dom.currentSessionNameDisplay.textContent = currentSession.name;
        renderSessionList();
    }

    dom.userInput.value = '';
    adjustTextareaHeight();
    updateCharCounter();
    closeFilePreview();
    state.uploadedFiles = [];

    if (dom.processLogSidebarContent) dom.processLogSidebarContent.innerHTML = ''; // 清空实时日志显示区域
    showProcessLogSidebar(true); // 显示并展开实时日志

    let backendMessageContent = messageText;
    if (filesToSend.length > 0) {
        backendMessageContent += `\n[用户已附加数据模块: ${filesToSend.map(f => f.name).join(', ')}. 请基于这些模块名称处理指令.]`;
    }

    sendWebSocketMessage({
        type: 'message',
        session_id: state.currentSessionId,
        request_id: state.currentClientRequestId, // 【老板，修改！】发送前端生成的请求ID
        content: backendMessageContent,
        mode: state.currentMode
    });
}

function handleUserInputKeypress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleSendMessage();
    }
}

function handleClearCurrentChat() {
    if (!state.currentSessionId || !state.sessions[state.currentSessionId]) return;
    if (!confirm(`清空当前光绘墨迹项目 "${state.sessions[state.currentSessionId].name}"? 这将清除所有消息和执行日志记录.`)) {
        return;
    }
    state.sessions[state.currentSessionId].messages = [];
    state.sessions[state.currentSessionId].executionLogs = []; // 【老板，新增！】同时清空执行日志
    state.sessions[state.currentSessionId].lastActivity = Date.now();
    saveSessions(); 
    dom.chatBox.innerHTML = '';
    appendWelcomeMessage(); 
    if (dom.processLogSidebarContent) dom.processLogSidebarContent.innerHTML = '';
    if (state.isProcessLogSidebarVisible) {
        showProcessLogSidebar(false);
    } else {
        hideProcessLogSidebar();
    }
    showToast('当前光绘墨迹项目已清空!', 'info');
    renderSessionList(); 
}

function handleModeChange(newMode) {
    if (state.currentMode === newMode) return;

    dom.sidebarButtons.forEach(button =>
        button.classList.toggle('active', button.dataset.mode === newMode)
    );
    state.currentMode = newMode;
    console.log(`模式已切换至: ${newMode}`);
    showToast(`已切换至 ${getModeDisplayName(newMode)} 领域`, 'info');
    const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
    dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${sessionNameForPlaceholder})...`;
}
// ==========================================================================
// [ END OF FILE core/event_listener_setup.js ]
// ==========================================================================