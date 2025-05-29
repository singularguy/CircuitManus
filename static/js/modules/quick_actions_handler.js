// ==========================================================================
// [ START OF FILE modules/quick_actions_handler.js ]
// Quick Action Button Handling
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from '../core/state.js';
// handleSendMessage 不再需要从其他地方导入或假设全局存在
import { adjustTextareaHeight, updateCharCounter } from '../core/ui_updater.js';

/**
 * Attaches click event listeners to quick action buttons within a container.
 * @param {HTMLElement} container - The parent element containing quick action buttons.
 */
export function attachQuickActionButtonListeners(container) {
    container.querySelectorAll('.quick-action-btn').forEach(button => {
        button.removeEventListener('click', handleQuickActionButtonClick);
        button.addEventListener('click', handleQuickActionButtonClick);
    });
}

/**
 * Handles the click event of a quick action button.
 * Fills the user input with the button's message and optionally auto-submits by clicking the send button.
 * @param {MouseEvent} e - The click event.
 */
function handleQuickActionButtonClick(e) {
    e.preventDefault();
    const messageToSend = e.target.closest('.quick-action-btn').dataset.message;
    if (messageToSend) {
        dom.userInput.value = messageToSend;
        adjustTextareaHeight();
        updateCharCounter();
        dom.userInput.focus();
        if (state.autoSubmitQuickActions) {
            // 直接触发发送按钮的点击事件
            if(dom.sendButton) {
                dom.sendButton.click(); // 模拟点击发送按钮
            } else {
                console.error("发送按钮 (dom.sendButton) 未找到，无法自动提交快捷操作。");
            }
        }
    }
}

// ==========================================================================
// [ END OF FILE modules/quick_actions_handler.js ]
// ==========================================================================
