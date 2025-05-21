// ==========================================================================
// [ START OF FILE modules/quick_actions_handler.js ]
// Quick Action Button Handling
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from '../core/state.js';
// handleSendMessage will be imported and called from event_listener_setup.js or app.js context
// For modularity, if handleSendMessage is complex, it could also be in a core_actions.js
// For now, we assume it's available in the scope where event listeners are attached.
// To make this module fully self-contained in terms of its direct dependencies for *its own functions*,
// handleSendMessage would ideally be passed in or imported if it were directly called here.
// However, attachQuickActionButtonListeners only *sets up* the listener which *then* calls a global/passed handleSendMessage.
import { adjustTextareaHeight, updateCharCounter } from '../core/ui_updater.js';

/**
 * Attaches click event listeners to quick action buttons within a container.
 * @param {HTMLElement} container - The parent element containing quick action buttons.
 */
export function attachQuickActionButtonListeners(container) {
    container.querySelectorAll('.quick-action-btn').forEach(button => {
        // Remove existing to prevent duplicates if called multiple times on same container
        button.removeEventListener('click', handleQuickActionButtonClick);
        button.addEventListener('click', handleQuickActionButtonClick);
    });
}

/**
 * Handles the click event of a quick action button.
 * Fills the user input with the button's message and optionally auto-submits.
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
            // Assuming handleSendMessage is globally available or imported in the main script
            // that calls initializeApp and setupEventListeners.
            // To call it directly from here, it would need to be imported:
            // import { handleSendMessage } from '../core/event_listener_setup.js'; // Or wherever it's defined
            if (typeof window.handleSendMessage === 'function') { // Check if it's globally available
                 window.handleSendMessage();
            } else {
                console.warn("handleSendMessage not found globally to auto-submit quick action.");
                // Fallback: trigger a custom event that the main script listens for, or explicitly pass handleSendMessage.
                // For now, we rely on the setup in event_listener_setup.js which defines handleSendMessage in its scope.
                // This is a slight break in pure modularity for this specific interaction.
                // A better way is for event_listener_setup.js to call this module's function if needed,
                // or for this function to emit an event.
                // For simplicity matching original structure, we assume event_listener_setup.js's handleSendMessage will be triggered.
                // Actually, the sendButton's event listener is what calls handleSendMessage.
                // So, if autoSubmit, we can just click the send button.
                if(dom.sendButton) dom.sendButton.click();
            }
        }
    }
}

// ==========================================================================
// [ END OF FILE modules/quick_actions_handler.js ]
// ==========================================================================