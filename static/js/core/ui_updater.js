// ==========================================================================
// [ START OF FILE core/ui_updater.js ]
// UI Update Functions - DOM manipulation for displaying data and states.
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from './state.js'; 
import { attachQuickActionButtonListeners } from '../modules/quick_actions_handler.js'; 
import { formatLogDetails, parseItemClasses } from '../utils/helpers.js'; 
// 【老板，重要！】确保从 session_handler.js 导入 showHistoricalLogsForRequest
import { showHistoricalLogsForRequest } from '../modules/session_handler.js';

/**
 * Appends a new message to the chat box.
 * 【老板，重大修改！】为Agent的最终回复添加一个清晰的“查看执行轨迹”按钮。
 * @param {string} content - The message content.
 * @param {string} sender - 'user', 'agent', 'system-info', 'error-system'.
 * @param {boolean} [isHTML=false] - Is the content HTML?
 * @param {string|null} [thinkContent=null] - Agent's thinking process.
 * @param {boolean} [isSwitchingSession=false] - Is this for loading history?
 * @param {Array} [attachments=[]] - Message attachments.
 * @param {string|null} [errorType=null] - Specific error type for styling.
 * @param {string|null} [clientRequestId=null] - The client-side request ID for this interaction.
 * @param {string|null} [agentRequestId=null] - The agent-side request ID for this interaction.
 */
export function appendMessage(content, sender, isHTML = false, thinkContent = null, isSwitchingSession = false, attachments = [], errorType = null, clientRequestId = null, agentRequestId = null) {
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
            messageDiv.style.setProperty('--animate-duration', state.animationLevel === 'full' ? '0.45s' : '0.35s');
        }
    }

    const avatarDiv = document.createElement('div');
    avatarDiv.classList.add('message-avatar');
    let avatarIcon = 'fas fa-question-circle';
    if (sender === 'user') avatarIcon = 'fas fa-user-pen';
    else if (sender === 'agent') avatarIcon = 'fas fa-lightbulb';
    else if (sender === 'system-info') avatarIcon = 'fas fa-info-circle';
    else if (sender === 'error-system') avatarIcon = 'fas fa-exclamation-triangle';
    avatarDiv.innerHTML = `<i class="${avatarIcon}"></i>`;

    if (sender === 'agent' || sender === 'system-info' || sender === 'error-system') {
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
        const jsonBlockRegex = /```json\s*([\s\S]*?)\s*```/gi;
        formattedThink = formattedThink.replace(jsonBlockRegex, (match, jsonContentStr) => {
            const trimmedJson = jsonContentStr.trim();
            try {
                const parsedJson = JSON.parse(trimmedJson);
                const escapedJsonString = JSON.stringify(parsedJson, null, 2)
                    .replace(/&/g, "&").replace(/</g, "<").replace(/>/g, ">"); // 更安全的HTML转义
                return `<pre class="embedded-json"><code>${escapedJsonString}</code></pre>`;
            } catch (e) {
                console.warn("Chat bubble: JSON parsing for pretty print failed within thought:", e);
                const escapedOriginalJson = trimmedJson.replace(/&/g, "&").replace(/</g, "<").replace(/>/g, ">");
                return `<pre class="embedded-json error"><code>${escapedOriginalJson}<br>(无效JSON投影)</code></pre>`;
            }
        });
        thinkPrefixDiv.innerHTML = `<strong><i class="fas fa-brain"></i> AI思维墨迹:</strong><div class="think-bubble-content">${formattedThink}</div>`;
        messageContentWrapper.appendChild(thinkPrefixDiv);
    }

    const textContentDiv = document.createElement('div');
    textContentDiv.classList.add('message-text-content');
    if (isHTML) {
        textContentDiv.innerHTML = content;
    } else {
        const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
        const linkedContent = String(content)
            .replace(/&/g, "&").replace(/</g, "<").replace(/>/g, ">") // 更安全的HTML转义
            .replace(/"/g, "'").replace(/'/g, "'")
            .replace(/\n/g, '<br>')
            .replace(urlRegex, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer" class="external-link"><i class="fas fa-external-link-alt"></i> ${url}</a>`);
        textContentDiv.innerHTML = linkedContent;
    }
    messageContentWrapper.appendChild(textContentDiv);

    if (attachments && attachments.length > 0) {
        const attachmentsDiv = document.createElement('div');
        attachmentsDiv.classList.add('message-attachments-summary');
        attachmentsDiv.innerHTML = `<i class="fas fa-paperclip"></i> 数据模块已附加 (${attachments.length}): `;
        attachments.forEach(file => {
            const fileChip = document.createElement('span');
            fileChip.classList.add('filename-chip');
            fileChip.textContent = file.name;
            fileChip.title = `${file.name} (${(file.size / 1024).toFixed(1)}KB, 类型: ${file.type || '未知'})`;
            attachmentsDiv.appendChild(fileChip);
        });
        messageContentWrapper.appendChild(attachmentsDiv);
    }

    messageBubbleDiv.appendChild(messageContentWrapper);
    
    // 【老板，这是本次修改的核心！】
    // 只有当消息是Agent的最终回复，并且有关联的请求ID时，才添加“查看执行轨迹”按钮
    // 我们假设 clientRequestId 总是存在于用户发起的请求对应的Agent回复中
    // isSwitchingSession 为 true 时，表示正在加载历史消息，此时也应该创建按钮（如果历史消息有关联ID）
    if (sender === 'agent' && (clientRequestId || agentRequestId)) { 
        const bubbleControls = document.createElement('div');
        bubbleControls.className = 'message-bubble-controls'; // 用于按钮容器的样式

        const viewLogsButton = document.createElement('button');
        // 使用 'lumina-button' 和 'lumina-button-secondary' (或自定义一个更小的按钮样式)
        viewLogsButton.className = 'view-execution-logs-btn lumina-button lumina-button-outline'; // 改为更明显的按钮样式
        viewLogsButton.innerHTML = '<i class="fas fa-history"></i> 查看执行轨迹'; // 按钮文本和图标
        viewLogsButton.title = '查看本次交互的详细执行轨迹';
        
        // 确保即使ID是null也存储为空字符串，避免dataset中出现"null"字符串
        viewLogsButton.dataset.clientRequestId = clientRequestId || ''; 
        viewLogsButton.dataset.agentRequestId = agentRequestId || '';

        // 点击事件的监听器将在 event_listener_setup.js 中通过事件委托添加到 dom.chatBox
        
        bubbleControls.appendChild(viewLogsButton);
        messageBubbleDiv.appendChild(bubbleControls); // 添加到气泡底部
    }


    messageDiv.appendChild(messageBubbleDiv);

    if (sender === 'user') {
        messageDiv.appendChild(avatarDiv);
    }

    dom.chatBox.appendChild(messageDiv);
    attachQuickActionButtonListeners(messageDiv); 
    if (!isSwitchingSession) { scrollToBottom(); }
}


export function appendWelcomeMessage() {
    const lastMessage = dom.chatBox.lastElementChild;
    if (lastMessage && lastMessage.classList.contains('system-message-initial')) { return; }

    const welcomeHTML = `
        <div class="message-content">
            <div class="welcome-header">
                <i class="fas fa-dna robot-icon animate__animated animate__pulse animate__infinite" style="--animate-duration: 3.5s;"></i>
                <h2>CircuitManus <span class="version-pro">Lumina <span class="version-number">v1.1.1</span></span></h2>
            </div>
            <p class="welcome-subtitle">您的光绘墨迹交互界面，赋能创意与构想。Lumina核心已激活，请挥洒您的灵感。</p>
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
             <div class="quick-actions">
                <p>开始您的创作或选择预设指令:</p>
                <ul>
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
    const welcomeDiv = document.createElement('div');
    const animClass = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInUp' : 'animate__fadeIn') : '';
    welcomeDiv.className = `message system-message system-message-initial lumina-panel ${animClass ? 'animate__animated ' + animClass : ''}`;
    if (animClass) welcomeDiv.style.setProperty('--animate-duration', '0.65s');
    welcomeDiv.innerHTML = welcomeHTML;
    dom.chatBox.appendChild(welcomeDiv);
    attachQuickActionButtonListeners(welcomeDiv);
}

export function scrollToBottom(instant = false) {
    if (state.autoScroll) {
        const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth';
        dom.chatBox.scrollTo({ top: dom.chatBox.scrollHeight, behavior: behavior });
    }
}

export function showTypingIndicator() {
    if (state.isAgentTyping) return;
    state.isAgentTyping = true;

    const typingDiv = document.createElement('div');
    typingDiv.id = 'typing-indicator';
    const animationClass = state.animationLevel !== 'none' ? 'animate__fadeInUp' : '';
    typingDiv.classList.add('message', 'message-agent', 'typing-indicator');
    if (animationClass) {
        typingDiv.classList.add('animate__animated', animationClass);
        typingDiv.style.setProperty('--animate-duration', '0.4s');
    }

    const avatarDiv = document.createElement('div');
    avatarDiv.classList.add('message-avatar');
    avatarDiv.innerHTML = '<i class="fas fa-lightbulb fa-beat"></i>';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.classList.add('message-bubble');
    const contentWrapper = document.createElement('div');
    contentWrapper.classList.add('message-content-wrapper');
    const textContent = document.createElement('div');
    textContent.classList.add('message-text-content');
    let dotsHTML = Array(3).fill('<span class="typing-dot"></span>').join('');
    textContent.innerHTML = `Lumina核心构思中<span class="typing-dots">${dotsHTML}</span>`;

    contentWrapper.appendChild(textContent);
    bubbleDiv.appendChild(contentWrapper);
    typingDiv.appendChild(avatarDiv);
    typingDiv.appendChild(bubbleDiv);
    dom.chatBox.appendChild(typingDiv);
    scrollToBottom();
}

export function hideTypingIndicator() {
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

export function adjustTextareaHeight() {
    dom.userInput.style.height = 'auto';
    let scrollHeight = dom.userInput.scrollHeight;
    const maxHeight = parseInt(getComputedStyle(dom.userInput).maxHeight, 10) || 200;
    const minHeight = parseInt(getComputedStyle(dom.userInput).minHeight, 10) || 52;
    const singleLinePadding = 5;

    if (dom.userInput.value.split('\n').length <= 1 && scrollHeight < minHeight + singleLinePadding * 2) {
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

export function updateCharCounter() {
    const currentLength = dom.userInput.value.length;
    dom.charCounter.textContent = `${currentLength}/${state.maxInputChars}`;
    dom.charCounter.classList.remove('warn', 'error');
    if (currentLength > state.maxInputChars) {
        dom.charCounter.classList.add('error');
    } else if (currentLength > state.maxInputChars * 0.9) {
        dom.charCounter.classList.add('warn');
    }
}

export function showToast(message, type = 'info', duration = 3500) {
    if (!dom.toastContainer) { console.error("Toast container element not found."); return; }

    const toast = document.createElement('div');
    toast.classList.add('toast', 'lumina-panel', `toast-${type}`);

    const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeInRight' : 'animate__fadeIn') : '';
    const animOut = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__fadeOutRight' : 'animate__fadeOut') : '';

    if (state.animationLevel !== 'none' && animIn) {
        toast.classList.add('animate__animated', animIn);
        toast.style.setProperty('--animate-duration', '0.45s');
    }

    const icons = { 'info': 'fa-info-circle', 'success': 'fa-check-circle', 'warning': 'fa-exclamation-triangle', 'error': 'fa-times-circle' };
    const iconClass = icons[type] || 'fa-info-circle';

    const messageSpan = document.createElement('span');
    messageSpan.className = 'toast-message';
    messageSpan.textContent = message;

    toast.innerHTML = `<i class="fas ${iconClass} toast-icon"></i>`;
    toast.appendChild(messageSpan);

    const closeButton = document.createElement('button');
    closeButton.className = 'toast-close icon-btn';
    closeButton.innerHTML = '<i class="fas fa-times"></i>';
    closeButton.setAttribute('title', '关闭通知');
    closeButton.addEventListener('click', () => removeToast(toast, animOut, true));
    toast.appendChild(closeButton);

    dom.toastContainer.appendChild(toast);

    if (duration > 0) {
        const timeoutId = setTimeout(() => {
            removeToast(toast, animOut, false);
        }, duration);
        toast.dataset.timeoutId = timeoutId.toString();
    }
}

export function removeToast(toast, animOut, isManualClose = false) {
    if (toast.parentElement) {
        if (isManualClose && toast.dataset.timeoutId) {
            clearTimeout(parseInt(toast.dataset.timeoutId, 10));
        }
        if (state.animationLevel !== 'none' && animOut && toast.classList.contains('animate__animated')) {
            toast.classList.remove('animate__fadeInRight', 'animate__fadeIn');
            toast.classList.add(animOut);
            toast.style.setProperty('--animate-duration', '0.3s');
            toast.addEventListener('animationend', () => {
                if (toast.parentElement) toast.remove();
            }, { once: true });
        } else {
            toast.remove();
        }
    }
}

export function setLoadingState(isLoading) {
    state.isLoading = isLoading;
    if (dom.sendButton) dom.sendButton.disabled = isLoading;
    if (dom.userInput) dom.userInput.disabled = isLoading;
    if (dom.sendIcon) dom.sendIcon.style.display = isLoading ? 'none' : 'inline-block';
    if (dom.sendLoadingIcon) dom.sendLoadingIcon.style.display = isLoading ? 'inline-block' : 'none';
    if (dom.sendButton) dom.sendButton.title = isLoading ? "墨迹传输中..." : "发送指令";
    if (dom.inputArea) dom.inputArea.classList.toggle('processing', isLoading);
    if (dom.sendButton) dom.sendButton.classList.toggle('processing-active', isLoading);
}

export function appendLogItem(messageText, iconClass, itemClasses = '', details = null) {
    if (!dom.processLogSidebarContent) {
        console.error("日志侧栏内容元素 (processLogSidebarContent) 未找到。");
        return null;
    }
    const logItemDiv = document.createElement('div');
    logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
    logItemDiv.style.setProperty('--animate-duration', '0.3s');
    if (itemClasses) {
        logItemDiv.classList.add(...itemClasses.split(' ').filter(cls => cls));
    }

    const iconEl = document.createElement('i');
    iconEl.className = iconClass; 
    logItemDiv.appendChild(iconEl);

    const contentAreaWrapper = document.createElement('div');
    contentAreaWrapper.classList.add('log-item-content-area');

    const messageEl = document.createElement('span');
    messageEl.className = 'log-item-message';
    messageEl.textContent = messageText;
    contentAreaWrapper.appendChild(messageEl);

    if (details && Object.keys(details).length > 0) {
        const detailsEl = document.createElement('div');
        detailsEl.className = 'log-item-details';
        const { type: logType, stage: logStage, status: logStatus } = parseItemClasses(logItemDiv.className);
        const formattedDetailsHtml = formatLogDetails(details, logType, logStage, logStatus);

        if (formattedDetailsHtml) {
            detailsEl.innerHTML = formattedDetailsHtml;
        } else {
             detailsEl.innerHTML = `<span class="log-detail-item"><strong class="log-detail-key">详细信息:</strong> <span class="log-detail-value">(无或格式化失败)</span></span>`;
            try {
                let rawDetailsStr = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details);
                detailsEl.innerHTML += `<pre class="log-detail-raw-json error"><code>${rawDetailsStr.replace(/</g, "<").replace(/>/g, ">")}<br>(原始数据)</code></pre>`; // 更安全的HTML转义
            } catch (e_raw) {
                 detailsEl.innerHTML += `<span class="log-detail-item error"><strong class="log-detail-key">原始数据错误:</strong> <span class="log-detail-value">${e_raw.message}</span></span>`;
            }
        }
        contentAreaWrapper.appendChild(detailsEl);
    }
    logItemDiv.appendChild(contentAreaWrapper);

    if (state.currentRequestLogCollection && state.currentRequestLogCollection.logItems) {
        state.currentRequestLogCollection.logItems.push({
            timestamp: Date.now(),
            messageText,
            iconClass,
            itemClasses, 
            details 
        });
    }

    dom.processLogSidebarContent.appendChild(logItemDiv);
    scrollToProcessLogBottom();
    return logItemDiv;
}

export function appendLogItemWithThink(headerText, headerIconClass, itemClasses, thinkContent, thinkBubbleLabel = "详细思考投影") {
    if (!dom.processLogSidebarContent) {
        console.error("日志侧栏内容元素 (processLogSidebarContent) 未找到。");
        return null;
    }
    const logItemDiv = document.createElement('div');
    logItemDiv.className = 'log-item animate__animated animate__fadeInUp';
    logItemDiv.style.setProperty('--animate-duration', '0.3s');
    if (itemClasses) logItemDiv.classList.add(...itemClasses.split(' '));

    const iconEl = document.createElement('i');
    iconEl.className = headerIconClass;
    logItemDiv.appendChild(iconEl);

    const contentAreaWrapper = document.createElement('div');
    contentAreaWrapper.classList.add('log-item-content-area');

    const messageEl = document.createElement('span');
    messageEl.className = 'log-item-message';
    messageEl.textContent = headerText;
    contentAreaWrapper.appendChild(messageEl);

    if (thinkContent) {
        const thinkDiv = document.createElement('div');
        thinkDiv.classList.add('log-think-content'); 
        let formattedThink = String(thinkContent).replace(/\n/g, '<br>');
        const jsonBlockRegex = /```json\s*([\s\S]*?)\s*```/gi;
        formattedThink = formattedThink.replace(jsonBlockRegex, (match, jsonContentStr) => {
            const trimmedJson = jsonContentStr.trim();
            try {
                const parsedJson = JSON.parse(trimmedJson);
                const escapedJsonString = JSON.stringify(parsedJson, null, 2)
                    .replace(/&/g, "&").replace(/</g, "<").replace(/>/g, ">"); // 更安全的HTML转义
                return `<pre class="log-detail-raw-json"><code>${escapedJsonString}</code></pre>`;
            } catch (jsonErr) {
                console.warn("Log item with think: JSON parsing for pretty print failed within thought:", jsonErr);
                const escapedOriginalJson = trimmedJson.replace(/&/g, "&").replace(/</g, "<").replace(/>/g, ">");
                return `<pre class="log-detail-raw-json error"><code>${escapedOriginalJson}<br>(无效JSON投影)</code></pre>`;
            }
        });
        thinkDiv.innerHTML = `<strong><i class="fas fa-brain"></i> ${thinkBubbleLabel}:</strong><div class="think-bubble">${formattedThink}</div>`;
        contentAreaWrapper.appendChild(thinkDiv);
    }
    logItemDiv.appendChild(contentAreaWrapper);

    if (state.currentRequestLogCollection && state.currentRequestLogCollection.logItems) {
        state.currentRequestLogCollection.logItems.push({
            timestamp: Date.now(),
            messageText: headerText, 
            iconClass: headerIconClass,
            itemClasses,
            details: { thinkContent: thinkContent, thinkBubbleLabel: thinkBubbleLabel } 
        });
    }

    dom.processLogSidebarContent.appendChild(logItemDiv);
    scrollToProcessLogBottom();
    return logItemDiv;
}

export function scrollToProcessLogBottom(instant = false) {
    if (!dom.processLogSidebarContent) {
        console.error("日志侧栏内容元素 (processLogSidebarContent) 未找到，无法滚动。");
        return;
    }
    const container = dom.processLogSidebarContent;
    const behavior = instant || state.animationLevel === 'none' ? 'auto' : 'smooth';
    container.scrollTo({ top: container.scrollHeight, behavior: behavior });
}
// ==========================================================================
// [ END OF FILE core/ui_updater.js ]
// ==========================================================================