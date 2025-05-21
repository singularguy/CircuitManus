// ==========================================================================
// [ START OF FILE app.js ]
// Main Application Entry Point - Initializes and coordinates all modules.
// ==========================================================================

// Import DOM elements and initial state
import dom from './utils/dom_elements.js';
import state, { loadPersistentSettings, savePersistentSettings } from './core/state.js'; // Include save/load for settings module

// Import core functionalities
import { connectWebSocket } from './core/websocket_manager.js';
import { setupEventListeners } from './core/event_listener_setup.js';
import { adjustTextareaHeight, updateCharCounter } from './core/ui_updater.js'; // Basic UI updaters for init

// Import module handlers
import { applyCurrentTheme, applyFontSize, applyAnimationLevel } from './modules/theme_handler.js';
import { initializeCurrentSessionUI } from './modules/session_handler.js';
import { updateSidebarState, updateSessionManagerState, applyFixedLogSidebarLayout, updateProcessLogSidebarCollapseState, showProcessLogSidebar, hideProcessLogSidebar, updateInputAreaHeightVar } from './modules/layout_handler.js';
import { toggleThreeBlackHoleVisibility } from './modules/three_visuals.js';
import { attachQuickActionButtonListeners } from './modules/quick_actions_handler.js';


// DOMContentLoaded to ensure all HTML is loaded before scripts run
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

/**
 * Initializes the entire frontend application.
 */
function initializeApp() {
    console.log("CircuitManus Pro - 光绘墨迹终端 (V1.0.0 Lumina) 初始化...");

    // 1. Load persistent settings from localStorage into the state object
    loadPersistentSettings();

    // 2. Apply loaded settings to the UI
    applyCurrentTheme(); // Applies theme based on loaded state.currentTheme
    applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16'); // Font size needs the raw value
    applyAnimationLevel(state.animationLevel); // Applies animation level from state

    // 3. Setup all event listeners
    // This will make dom elements interactive and use state for decisions
    setupEventListeners(); // Defined in core/event_listener_setup.js

    // 4. Initialize UI components based on loaded state
    adjustTextareaHeight();
    updateCharCounter();
    updateInputAreaHeightVar();

    updateSidebarState(state.isSidebarExpanded, true); // true for instant update
    updateSessionManagerState(state.isSessionManagerCollapsed, true); // true for instant

    applyFixedLogSidebarLayout();
    updateProcessLogSidebarCollapseState(state.isProcessLogSidebarCollapsed, true);
    if (state.isProcessLogSidebarVisible) {
        showProcessLogSidebar(false); // Show, but don't force expand if it was collapsed
    } else {
        hideProcessLogSidebar();
    }

    toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);
    dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
    const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
    if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';


    // 5. Initialize session UI (loads or creates a session)
    // loadSessions() is called within initializeCurrentSessionUI if needed by session_handler
    initializeCurrentSessionUI(true); // true for initial load context

    // 6. Attach listeners for dynamically added content if necessary (e.g. quick actions in welcome)
    // appendWelcomeMessage (called by initializeCurrentSessionUI if no messages) already calls attachQuickActionButtonListeners
    // For any other dynamic content, listeners should be attached when content is added.

    // 7. Connect WebSocket
    connectWebSocket(); // Defined in core/websocket_manager.js


    console.log("光绘墨迹终端 系统就绪. 等待数据流.");

    // Hide loader after a short delay to ensure content is rendered
    // This can be refined based on actual rendering time or specific events
    setTimeout(() => {
        if (dom.loader && !dom.loader.classList.contains('loader-fatal-error')) {
            dom.loader.classList.add('hidden');
        }
        if (dom.mainContainer) {
            dom.mainContainer.classList.add('loaded');
        }
    }, 500); // Adjust delay as needed
}

// Expose handleSendMessage globally if quick_actions_handler needs it directly
// This is a workaround for simple modularity. A better way is event bus or dependency injection.
// Or, ensure quick_actions_handler's click directly triggers the sendButton's click event.
// For now, if event_listener_setup defines handleSendMessage in its scope and attaches to sendButton,
// and quick_actions_handler simulates a click on sendButton, it should work.
// Let's assume the quick_actions_handler is updated to dom.sendButton.click().
// window.handleSendMessage = handleSendMessage; // No longer needed if quick_actions calls sendButton.click()

// Re-export APP_PREFIX if it's defined in state.js or helpers.js and needed by other top-level files not using modules.
// However, with ES6 modules, it's better to import where needed.
const APP_PREFIX = 'CircuitManusPro_LuminaScript_'; // Ensure consistency

// ==========================================================================
// [ END OF FILE app.js ]
// ==========================================================================