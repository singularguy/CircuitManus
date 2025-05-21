// ==========================================================================
// [ START OF FILE modules/layout_handler.js ]
// Dynamic Layout Adjustment Functions
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from '../core/state.js';

/**
 * Updates the expanded/collapsed state of the left sidebar.
 * @param {boolean} expand - True to expand, false to collapse.
 * @param {boolean} [instant=false] - True for instant update without animation.
 */
export function updateSidebarState(expand, instant = false) {
    state.isSidebarExpanded = expand;
    dom.sidebar.classList.toggle('expanded', state.isSidebarExpanded);
    if (dom.leftSidebarToggle) {
        dom.leftSidebarToggle.setAttribute('aria-expanded', state.isSidebarExpanded.toString());
        const toggleIcon = dom.leftSidebarToggle.querySelector('i');
        if (toggleIcon) {
            toggleIcon.className = state.isSidebarExpanded ? 'fas fa-times' : 'fas fa-bars';
        }
    }
    // If sidebar is collapsed and session manager is expanded, collapse session manager
    if (!state.isSidebarExpanded && !state.isSessionManagerCollapsed) {
        updateSessionManagerState(true, instant);
    }
    // Persist this state if needed (e.g., in settings_handler or directly)
    // localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());
}

/**
 * Updates the collapsed/expanded state of the session manager within the sidebar.
 * @param {boolean} collapse - True to collapse, false to expand.
 * @param {boolean} [instant=false] - True for instant update.
 */
export function updateSessionManagerState(collapse, instant = false) {
    state.isSessionManagerCollapsed = collapse;
    dom.sessionManager.classList.toggle('collapsed', state.isSessionManagerCollapsed);
    dom.sessionManagerToggle.setAttribute('aria-expanded', (!state.isSessionManagerCollapsed).toString());
    const sessionToggleIcon = dom.sessionManagerToggle.querySelector('.toggle-icon');
    if (sessionToggleIcon) {
        sessionToggleIcon.className = state.isSessionManagerCollapsed ? 'fas fa-caret-right' : 'fas fa-caret-down';
    }
    // Persist this state
    // localStorage.setItem(APP_PREFIX + 'sessionManagerCollapsed', state.isSessionManagerCollapsed.toString());
}

/**
 * Updates the CSS variable for input area height.
 */
export function updateInputAreaHeightVar() {
    if (dom.inputArea) {
        const heightPx = dom.inputArea.offsetHeight;
        document.documentElement.style.setProperty('--input-area-height', `${heightPx}px`);
    }
}


/**
 * Applies layout adjustments for the fixed right process log sidebar.
 */
export function applyFixedLogSidebarLayout() {
    if (!dom.processLogSidebarContainer || !dom.chatArea) return;
    const logSidebarFixedWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--process-log-sidebar-width').replace('px', '')) || 350;
    const logSidebarCollapsedWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--process-log-sidebar-width-collapsed').replace('px', '')) || 55;

    if (state.isProcessLogSidebarVisible) {
        if (state.isProcessLogSidebarCollapsed) {
            dom.chatArea.style.marginRight = `${logSidebarCollapsedWidth + parseInt(getComputedStyle(dom.chatArea).paddingRight || '0', 10)}px`;
            dom.processLogSidebarContainer.style.width = `${logSidebarCollapsedWidth}px`;
            if(dom.closeProcessLogSidebarButton) dom.closeProcessLogSidebarButton.style.display = 'none';
            if(dom.toggleProcessLogSidebarCollapseButton) dom.toggleProcessLogSidebarCollapseButton.style.display = 'flex';
        } else {
            dom.chatArea.style.marginRight = `${logSidebarFixedWidth + parseInt(getComputedStyle(dom.chatArea).paddingRight || '0', 10)}px`;
            dom.processLogSidebarContainer.style.width = `${logSidebarFixedWidth}px`;
            if(dom.closeProcessLogSidebarButton) dom.closeProcessLogSidebarButton.style.display = 'flex';
            if(dom.toggleProcessLogSidebarCollapseButton) dom.toggleProcessLogSidebarCollapseButton.style.display = 'flex';
        }
    } else {
        dom.chatArea.style.marginRight = ''; // Revert to default
        if(dom.closeProcessLogSidebarButton) dom.closeProcessLogSidebarButton.style.display = 'none';
        // Keep collapse button visible for consistency even if sidebar is hidden
        if(dom.toggleProcessLogSidebarCollapseButton) dom.toggleProcessLogSidebarCollapseButton.style.display = 'flex';
    }
}

/**
 * Updates the collapsed/expanded state of the right process log sidebar.
 * @param {boolean} collapse - True to collapse.
 * @param {boolean} [instant=false] - True for instant update.
 */
export function updateProcessLogSidebarCollapseState(collapse, instant = false) {
    state.isProcessLogSidebarCollapsed = collapse;
    if (dom.processLogSidebarContainer) {
        dom.processLogSidebarContainer.classList.toggle('collapsed', state.isProcessLogSidebarCollapsed);
        const iconElement = dom.toggleProcessLogSidebarCollapseButton.querySelector('i');
        if (iconElement) {
            iconElement.className = state.isProcessLogSidebarCollapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-left';
        }
    }
    applyFixedLogSidebarLayout();
    // localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarCollapsed', state.isProcessLogSidebarCollapsed.toString());
}

/**
 * Hides the right process log sidebar.
 */
export function hideProcessLogSidebar() {
    if (!dom.processLogSidebarContainer) return;
    state.isProcessLogSidebarVisible = false;
    dom.processLogSidebarContainer.classList.remove('visible');
    if (dom.appBodyContainer) {
        dom.appBodyContainer.classList.remove('with-process-log-open', 'log-sidebar-collapsed');
    }
    applyFixedLogSidebarLayout();
    // localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarVisible', state.isProcessLogSidebarVisible.toString());
    console.log("右侧日志侧栏已隐藏。");
}

/**
 * Shows the right process log sidebar.
 * @param {boolean} [ensureExpanded=false] - If true and sidebar is collapsed, expand it.
 */
export function showProcessLogSidebar(ensureExpanded = false) {
    if (!dom.processLogSidebarContainer) return;
    state.isProcessLogSidebarVisible = true;
    dom.processLogSidebarContainer.classList.add('visible');

    if (dom.appBodyContainer) {
        dom.appBodyContainer.classList.add('with-process-log-open');
        dom.appBodyContainer.classList.toggle('log-sidebar-collapsed', state.isProcessLogSidebarCollapsed);
    }

    if (ensureExpanded && state.isProcessLogSidebarCollapsed) {
        toggleProcessLogSidebarCollapse(false); // false to expand
    } else {
        applyFixedLogSidebarLayout();
    }
    // localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarVisible', state.isProcessLogSidebarVisible.toString());
    console.log(`右侧日志侧栏已显示 (强制展开: ${ensureExpanded}, 当前折叠状态: ${state.isProcessLogSidebarCollapsed}).`);
}

/**
 * Toggles the collapsed/expanded state of the right process log sidebar.
 * @param {boolean} [instant=false] - True for instant update.
 */
export function toggleProcessLogSidebarCollapse(instant = false) {
    if (!dom.processLogSidebarContainer || !dom.toggleProcessLogSidebarCollapseButton) return;
    updateProcessLogSidebarCollapseState(!state.isProcessLogSidebarCollapsed, instant);
    console.log(`右侧日志侧栏折叠状态切换为: ${state.isProcessLogSidebarCollapsed ? '已折叠' : '已展开'}`);
}


// ==========================================================================
// [ END OF FILE modules/layout_handler.js ]
// ==========================================================================