// ==========================================================================
// [ START OF FILE modules/session_handler.js ]
// Session Management - Create, Switch, Delete, Load, Save, Render List
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from '../core/state.js';
import { sendWebSocketMessage } from '../core/websocket_manager.js';
// 【老板，修改！】从 ui_updater.js 导入渲染日志的函数
import { appendMessage, appendWelcomeMessage, scrollToBottom, showToast, appendLogItem, appendLogItemWithThink } from '../core/ui_updater.js';
import { APP_PREFIX, generateSessionId, formatTimeSince, getModeDisplayName } from '../utils/helpers.js';
import { updateSidebarState, updateSessionManagerState, showProcessLogSidebar, hideProcessLogSidebar } from './layout_handler.js';


export function initializeCurrentSessionUI(isInitialLoadOrConnect = false) {
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

export function createNewSession(isInitialCreation = false) {
    const newId = generateSessionId();
    const now = Date.now();
    const sessionCount = Object.keys(state.sessions).length + 1;
    state.sessions[newId] = {
        id: newId,
        name: `光绘墨迹项目 ${sessionCount}`,
        messages: [],
        createdAt: now,
        lastActivity: now,
        executionLogs: [],
    };
    saveSessions();
    if (!isInitialCreation) {
        switchSession(newId, false);
        showToast('新光绘墨迹项目已创建!', 'success');
        if (!state.isSidebarExpanded) updateSidebarState(true);
        if (state.isSessionManagerCollapsed) updateSessionManagerState(false);
    }
    return newId;
}

export function switchSession(sessionId, isInitialLoadOrConnect = false) {
    if (!state.sessions[sessionId]) {
        console.error(`尝试切换到不存在的会话: ${sessionId}. 创建一个 fallback 会话.`);
        const fallbackId = createNewSession(true);
        state.currentSessionId = fallbackId;
    } else {
        state.currentSessionId = sessionId;
    }

    if (!isInitialLoadOrConnect) {
        sendWebSocketMessage({ type: 'init', session_id: state.currentSessionId });
    }

    localStorage.setItem(APP_PREFIX + 'lastSessionId', state.currentSessionId);
    if (state.sessions[state.currentSessionId]) {
        state.sessions[state.currentSessionId].lastActivity = Date.now();
        if (!state.sessions[state.currentSessionId].executionLogs) {
            state.sessions[state.currentSessionId].executionLogs = [];
        }
    }
    saveSessions();

    dom.currentSessionNameDisplay.textContent = state.sessions[state.currentSessionId]?.name || "初始化墨迹...";
    dom.chatBox.innerHTML = '';

    if (state.sessions[state.currentSessionId]?.messages.length === 0) {
        appendWelcomeMessage();
    } else {
        state.sessions[state.currentSessionId]?.messages.forEach(msg => {
            appendMessage(
                msg.content, 
                msg.sender, 
                msg.isHTML, 
                msg.thinking, 
                true, 
                msg.attachments, 
                msg.errorType,
                msg.clientRequestId, 
                msg.agentRequestId   
            );
        });
    }
    scrollToBottom(true);
    renderSessionList();
    dom.userInput.focus();

    if (dom.processLogSidebarContent) dom.processLogSidebarContent.innerHTML = '';
    hideProcessLogSidebar(); 

    console.log(`切换到光绘墨迹项目: ${state.sessions[state.currentSessionId]?.name} (ID: ${state.currentSessionId})`);
    const currentSessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
    dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${currentSessionNameForPlaceholder})...`;
}

export function deleteSession(sessionId, event) {
    if (event) event.stopPropagation();
    if (!state.sessions[sessionId]) return;

    const sessionName = state.sessions[sessionId].name;
    if (!confirm(`归档光绘墨迹项目 "${sessionName}" (ID: ${sessionId})? 此操作不可逆转.`)) {
        return;
    }

    const listItem = dom.sessionList.querySelector(`li[data-session-id="${sessionId}"]`);
    if (listItem) {
        if (state.animationLevel !== 'none') {
            listItem.classList.add('animate__animated', 'animate__zoomOutLeft');
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
            const newFallbackId = createNewSession(true);
            switchSession(newFallbackId, false);
        }
    } else {
        saveSessions();
        renderSessionList();
    }
    showToast(`光绘墨迹项目 "${sessionName}" 已归档.`, 'info');
    if (Object.keys(state.sessions).length === 0 && dom.sessionList) renderSessionList();
}

export function handleEditSessionName() {
    const currentSession = state.sessions[state.currentSessionId];
    if (!currentSession) return;

    const newName = prompt(`重命名光绘墨迹项目 "${currentSession.name}":`, currentSession.name);
    if (newName && newName.trim() !== "" && newName.trim() !== currentSession.name) {
        currentSession.name = newName.trim().substring(0, 70);
        currentSession.lastActivity = Date.now();
        dom.currentSessionNameDisplay.textContent = currentSession.name;
        saveSessions();
        renderSessionList();
        showToast("光绘墨迹项目名称已更新.", "success");
        const currentSessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
        dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${currentSessionNameForPlaceholder})...`;
    }
}

export function renderSessionList() {
    if (!dom.sessionList) return;
    dom.sessionList.innerHTML = '';
    const sortedSessions = Object.values(state.sessions)
        .sort((a, b) => b.lastActivity - a.lastActivity);

    if (sortedSessions.length === 0) {
        const emptyItem = document.createElement('li');
        emptyItem.classList.add('session-list-empty');
        emptyItem.innerHTML = '<i class="fas fa-folder-open"></i> 无光绘项目';
        dom.sessionList.appendChild(emptyItem);
        return;
    }

    sortedSessions.forEach(session => {
        const listItem = document.createElement('li');
        listItem.classList.add('session-list-item');
        if (session.id === state.currentSessionId) {
            listItem.classList.add('active-session');
        }
        listItem.dataset.sessionId = session.id;

        const timeSinceLastActivity = formatTimeSince(session.lastActivity);
        const lastActivityDate = new Date(session.lastActivity);
        const createdDate = new Date(session.createdAt);
        listItem.title = `最后修改: ${timeSinceLastActivity} (${lastActivityDate.toLocaleString()})\n创建于: ${createdDate.toLocaleDateString()}`;

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
        deleteBtn.title = "归档此光绘项目";
        deleteBtn.addEventListener('click', (e) => deleteSession(session.id, e));

        listItem.appendChild(contentWrapper);
        listItem.appendChild(deleteBtn);
        listItem.addEventListener('click', () => {
            if (state.currentSessionId !== session.id) switchSession(session.id, false);
        });
        dom.sessionList.appendChild(listItem);
    });
}

export function saveSessions() {
    try {
        localStorage.setItem(APP_PREFIX + 'sessions', JSON.stringify(state.sessions));
    } catch (e) {
        console.error("保存会话数据失败:", e);
        showToast("未能持久化会话数据. 归档异常.", "error");
    }
}

export function loadSessions() {
    const storedSessions = localStorage.getItem(APP_PREFIX + 'sessions');
    state.sessions = {};
    if (storedSessions) {
        try {
            const parsedSessions = JSON.parse(storedSessions);
            Object.keys(parsedSessions).forEach(id => {
                const s = parsedSessions[id];
                if (s && typeof s.id === 'string' && typeof s.name === 'string' && Array.isArray(s.messages)) {
                    state.sessions[id] = {
                        id: s.id,
                        name: s.name || "已归档项目",
                        messages: s.messages.map(m => ({
                            content: m.content || "",
                            sender: m.sender || "system",
                            timestamp: m.timestamp || Date.now(),
                            isHTML: m.isHTML || false,
                            attachments: m.attachments || [],
                            thinking: m.thinking || null,
                            rawResponseV1_PCP_CamelCase: m.rawResponseV1_PCP_CamelCase || m.rawResponseV1_3_2_CamelCase,
                            errorType: m.errorType,
                            clientRequestId: m.clientRequestId, 
                            agentRequestId: m.agentRequestId,   
                        })),
                        createdAt: s.createdAt || Date.now(),
                        lastActivity: s.lastActivity || Date.now(),
                        executionLogs: Array.isArray(s.executionLogs) ? s.executionLogs : [], 
                    };
                } else {
                    console.warn("发现损坏的光绘墨迹归档数据, 已跳过:", id, s);
                }
            });
        } catch (e) {
            console.error("加载或解析会话数据失败 (归档损坏):", e);
            state.sessions = {};
            localStorage.removeItem(APP_PREFIX + 'sessions');
            showToast("加载归档数据失败. 数据可能已损坏.", "error");
        }
    }
}

export function addMessageToCurrentSession(messageObject) {
    if (state.sessions[state.currentSessionId]) {
        if (messageObject.sender !== 'agent') {
            delete messageObject.rawResponseV1_PCP_CamelCase; 
            delete messageObject.thinking;
        }
        if (messageObject.clientRequestId === undefined) delete messageObject.clientRequestId;
        if (messageObject.agentRequestId === undefined) delete messageObject.agentRequestId;

        if (messageObject.errorType === undefined || messageObject.errorType === null) {
            delete messageObject.errorType;
        }
        state.sessions[state.currentSessionId].messages.push(messageObject);
        saveSessions();
    } else {
        console.error("尝试向不存在的会话添加消息:", state.currentSessionId);
    }
}

// 【老板，这是新增的函数！】
/**
 * Displays the historical execution logs for a specific user request.
 * @param {string} sessionId - The ID of the session containing the request.
 * @param {string|null} clientRequestId - The client-side ID of the request.
 * @param {string|null} agentRequestId - The agent-side ID of the request.
 */
export function showHistoricalLogsForRequest(sessionId, clientRequestId, agentRequestId) {
    if (!sessionId || !state.sessions[sessionId] || !state.sessions[sessionId].executionLogs) {
        console.warn(`无法找到会话 ${sessionId} 或其执行日志。`);
        showToast("未能加载历史执行轨迹：会话数据不存在。", "warning");
        return;
    }

    const executionLogs = state.sessions[sessionId].executionLogs;
    let targetLogCollection = null;

    // 优先使用 clientRequestId 查找，因为它是由前端生成的，更可靠地与用户消息关联
    if (clientRequestId) {
        targetLogCollection = executionLogs.find(logSet => logSet.clientRequestId === clientRequestId);
    }
    // 如果用 clientRequestId 找不到，并且有 agentRequestId，则尝试用 agentRequestId 找
    if (!targetLogCollection && agentRequestId) {
        targetLogCollection = executionLogs.find(logSet => logSet.agentRequestId === agentRequestId);
    }
    // 如果还是找不到，可以再尝试只用其中一个ID（如果另一个为空）
    if (!targetLogCollection) {
        if (clientRequestId && !agentRequestId) {
            targetLogCollection = executionLogs.find(logSet => logSet.clientRequestId === clientRequestId && !logSet.agentRequestId);
        } else if (!clientRequestId && agentRequestId) {
            targetLogCollection = executionLogs.find(logSet => logSet.agentRequestId === agentRequestId && !logSet.clientRequestId);
        }
    }


    if (!targetLogCollection || !Array.isArray(targetLogCollection.logItems) || targetLogCollection.logItems.length === 0) {
        const idUsed = clientRequestId ? `ClientReqID: ${clientRequestId}` : `AgentReqID: ${agentRequestId}`;
        console.warn(`未能找到与请求 (${idUsed}) 对应的历史执行日志，或日志为空。`);
        showToast("未能加载该请求的历史执行轨迹，或轨迹为空。", "info");
        // 即使找不到，也清空并显示日志栏，给用户一个明确的“无记录”状态
        if (dom.processLogSidebarContent) dom.processLogSidebarContent.innerHTML = '';
        appendLogItem(`未找到与请求 (${idUsed}) 关联的详细执行轨迹。`, 'fas fa-ghost log-muted', 'type-historical_log status-not_found');
        showProcessLogSidebar(true); // 确保日志栏可见并展开
        return;
    }

    if (dom.processLogSidebarContent) {
        dom.processLogSidebarContent.innerHTML = ''; // 清空当前实时日志
        
        // 添加一个头部，标明这是历史日志
        appendLogItem(
            `查看历史执行轨迹 (用户请求: "${targetLogCollection.userRequestContent.substring(0,50)}...", 请求时间: ${new Date(targetLogCollection.timestamp).toLocaleString()})`,
            'fas fa-history log-info',
            'type-historical_log status-header'
        );

        targetLogCollection.logItems.forEach(logEntry => {
            // 我们需要根据存储的 logEntry 的结构来调用 appendLogItem 或 appendLogItemWithThink
            // 假设 logEntry 存储了调用这两个函数所需的所有参数
            if (logEntry.details && logEntry.details.thinkContent) { // 这是一个粗略的判断，表明它可能是用 appendLogItemWithThink 创建的
                appendLogItemWithThink(
                    logEntry.messageText,
                    logEntry.iconClass,
                    logEntry.itemClasses,
                    logEntry.details.thinkContent,
                    logEntry.details.thinkBubbleLabel || "详细思考投影"
                );
            } else {
                appendLogItem(
                    logEntry.messageText,
                    logEntry.iconClass,
                    logEntry.itemClasses,
                    logEntry.details
                );
            }
        });
        showProcessLogSidebar(true); // 确保日志栏可见并展开
        scrollToProcessLogBottom(true); // 滚动到底部，即时显示
        showToast("历史执行轨迹已加载。", "success", 2000);
    } else {
        console.error("右侧日志栏容器 (processLogSidebarContent) 未找到，无法显示历史日志。");
    }
}

// ==========================================================================
// [ END OF FILE modules/session_handler.js ]
// ==========================================================================