// ==========================================================================
// [ START OF FILE modules/copy_handler.js ]
// Message Copy Functionality
// ==========================================================================

import dom from '../utils/dom_elements.js';
import { showToast } from '../core/ui_updater.js'; // For feedback

/**
 * Handles mouseover on chat messages to show copy button.
 * @param {MouseEvent} event
 */
export function handleChatBoxMouseOver(event) {
    const targetMessageBubble = event.target.closest('.message-agent .message-bubble');
    if (targetMessageBubble) {
        let copyButton = targetMessageBubble.querySelector('.copy-llm-response-btn');
        if (!copyButton) {
            copyButton = document.createElement('button');
            copyButton.className = 'copy-llm-response-btn icon-btn';
            copyButton.innerHTML = '<i class="fas fa-copy"></i>';
            copyButton.title = '复制回复内容';
            copyButton.addEventListener('click', handleCopyLlmResponse);
            targetMessageBubble.appendChild(copyButton);
        }
        copyButton.style.opacity = '1';
        copyButton.style.visibility = 'visible';
    }
}

/**
 * Handles mouseout from chat messages to hide copy button.
 * @param {MouseEvent} event
 */
export function handleChatBoxMouseOut(event) {
    const targetMessageBubble = event.target.closest('.message-agent .message-bubble');
    if (targetMessageBubble) {
        const copyButton = targetMessageBubble.querySelector('.copy-llm-response-btn');
        // Check if relatedTarget is not the button itself or a child of the button
        if (copyButton && !targetMessageBubble.contains(event.relatedTarget) &&
            event.relatedTarget !== copyButton && !copyButton.contains(event.relatedTarget)
        ) {
            copyButton.style.opacity = '0';
            copyButton.style.visibility = 'hidden';
        }
    } else {
        // If mouse left the chatBox entirely, hide all copy buttons
        dom.chatBox.querySelectorAll('.message-agent .message-bubble .copy-llm-response-btn').forEach(btn => {
            btn.style.opacity = '0';
            btn.style.visibility = 'hidden';
        });
    }
}

/**
 * Handles click on the copy button to copy message content.
 * @param {MouseEvent} event
 */
export function handleCopyLlmResponse(event) {
    event.stopPropagation(); // Prevent bubble click if any
    const button = event.currentTarget;
    const messageBubble = button.closest('.message-bubble');
    const textContentDiv = messageBubble.querySelector('.message-text-content');

    if (textContentDiv) {
        let textToCopy = textContentDiv.innerHTML.replace(/<br\s*\/?>/gi, '\n'); // Convert <br> to newlines
        // Strip other HTML tags to get plain text
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = textToCopy;
        textToCopy = tempDiv.textContent || tempDiv.innerText || "";

        // Remove "下一步行动投影:" section if present
        const suggestionIndex = textToCopy.indexOf("下一步行动投影:");
        if (suggestionIndex !== -1) {
            textToCopy = textToCopy.substring(0, suggestionIndex).trim();
        }

        navigator.clipboard.writeText(textToCopy.trim())
            .then(() => {
                showToast('回复已复制到剪贴板!', 'success', 2000);
                button.innerHTML = '<i class="fas fa-check"></i>';
                setTimeout(() => { button.innerHTML = '<i class="fas fa-copy"></i>'; }, 1500);
            })
            .catch(err => {
                console.error('无法复制文本: ', err);
                showToast('复制失败!', 'error');
            });
    }
}
// ==========================================================================
// [ END OF FILE modules/copy_handler.js ]
// ==========================================================================