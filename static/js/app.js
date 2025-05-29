// ==========================================================================
// [ START OF FILE app.js ]
// Main Application Entry Point - Initializes and coordinates all modules.
// ==========================================================================

import dom from './utils/dom_elements.js';
import state, { loadPersistentSettings, savePersistentSettings } from './core/state.js'; 
import { connectWebSocket } from './core/websocket_manager.js';
import { setupEventListeners } from './core/event_listener_setup.js';
import { adjustTextareaHeight, updateCharCounter } from './core/ui_updater.js'; 
import { applyCurrentTheme, applyFontSize, applyAnimationLevel } from './modules/theme_handler.js';
import { initializeCurrentSessionUI } from './modules/session_handler.js';
// 导入 settings_handler.js 中的 openSettingsModal, populateLLMModelSelect, updateChineseDeepThinkingToggleState
import { openSettingsModal, populateLLMModelSelect, updateChineseDeepThinkingToggleState } from './modules/settings_handler.js'; 
import { updateSidebarState, updateSessionManagerState, applyFixedLogSidebarLayout, updateProcessLogSidebarCollapseState, showProcessLogSidebar, hideProcessLogSidebar, updateInputAreaHeightVar } from './modules/layout_handler.js';
import { toggleThreeBlackHoleVisibility } from './modules/three_visuals.js';
import { attachQuickActionButtonListeners } from './modules/quick_actions_handler.js';
import { APP_PREFIX } from './utils/helpers.js';


document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    console.log("CircuitManus Pro - 光绘墨迹终端 (V1.1.0 Lumina Multi-LLM) 初始化..."); // 版本更新

    loadPersistentSettings(); // 加载持久化设置到 state 对象

    applyCurrentTheme(); 
    applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16'); 
    applyAnimationLevel(state.animationLevel); 

    setupEventListeners(); 

    adjustTextareaHeight();
    updateCharCounter();
    updateInputAreaHeightVar();

    updateSidebarState(state.isSidebarExpanded, true); 
    updateSessionManagerState(state.isSessionManagerCollapsed, true); 

    applyFixedLogSidebarLayout();
    updateProcessLogSidebarCollapseState(state.isProcessLogSidebarCollapsed, true);
    if (state.isProcessLogSidebarVisible) {
        showProcessLogSidebar(false); 
    } else {
        hideProcessLogSidebar();
    }

    toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);
    dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
    const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
    if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';

    // 重要：在连接WebSocket之前，确保与设置相关的UI（尤其是依赖后端数据的）已准备好被填充
    // populateLLMModelSelect 和 updateChineseDeepThinkingToggleState 会在 WebSocket 的 init_success 中被调用，
    // 因为它们依赖于从后端获取的 agentDefaultSettings。
    // 所以此处不需要显式调用它们。

    initializeCurrentSessionUI(true); 

    connectWebSocket(); 


    console.log("光绘墨迹终端 系统就绪. 等待数据流.");

    setTimeout(() => {
        if (dom.loader && !dom.loader.classList.contains('loader-fatal-error')) {
            dom.loader.classList.add('hidden');
        }
        if (dom.mainContainer) {
            dom.mainContainer.classList.add('loaded');
        }
    }, 500); 
}
// ==========================================================================
// [ END OF FILE app.js ]
// ==========================================================================
