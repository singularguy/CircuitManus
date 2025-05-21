// ==========================================================================
// [ START OF FILE modules/settings_handler.js ]
// Settings Modal Logic - Opening, Closing, Saving, Resetting
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state, { savePersistentSettings, loadPersistentSettings } from '../core/state.js';
import { applyTheme, applyFontSize, applyAnimationLevel } from './theme_handler.js';
import { toggleThreeBlackHoleVisibility } from './three_visuals.js';
// 修正导入：APP_PREFIX 和 getThemeDisplayName 都从 helpers.js 导入
import { getThemeDisplayName, getModeDisplayName, APP_PREFIX } from '../utils/helpers.js'; // Added getModeDisplayName
import { updateSidebarState, updateSessionManagerState, applyFixedLogSidebarLayout, updateProcessLogSidebarCollapseState, showProcessLogSidebar, hideProcessLogSidebar } from './layout_handler.js';
import { showToast } from '../core/ui_updater.js';


export function openSettingsModal() {
    if (dom.themeSelect) dom.themeSelect.value = state.currentTheme;
    const currentFontSize = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--base-font-size').replace('px', '')) || 16;
    if (dom.fontSizeInput) dom.fontSizeInput.value = currentFontSize;
    if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${currentFontSize.toFixed(0)}px`;
    if (dom.animationLevelSelect) dom.animationLevelSelect.value = state.animationLevel;
    if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
    if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
    if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
    if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
    if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;
    if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;

    dom.settingsModal.style.display = 'flex';
    const modalContent = dom.settingsModal.querySelector('.modal-content');
    modalContent.classList.remove('animate__fadeOutDown', 'animate__zoomOut', 'animate__fadeOut');
    const animIn = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__zoomIn' : 'animate__fadeIn') : '';
    if (animIn) {
        modalContent.classList.add('animate__animated', animIn);
        modalContent.style.setProperty('--animate-duration', '0.45s');
    }
}

export function closeSettingsModal(revertChanges = true) {
    if (revertChanges) {
        loadPersistentSettings(); 

        applyTheme(state.currentTheme, true); 
        // APP_PREFIX 从 helpers.js 导入
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
        applyAnimationLevel(state.animationLevel);

        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;
        if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;
        toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);
        const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
        if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';
    }

    const modalContent = dom.settingsModal.querySelector('.modal-content');
    modalContent.classList.remove('animate__zoomIn', 'animate__fadeIn');
    const animOut = state.animationLevel !== 'none' ? (state.animationLevel === 'full' ? 'animate__zoomOut' : 'animate__fadeOut') : '';

    const animationEndHandler = () => {
        dom.settingsModal.style.display = 'none';
        if (animOut) modalContent.classList.remove('animate__animated', animOut);
    };

    if (state.animationLevel !== 'none' && animOut) {
        modalContent.classList.add('animate__animated', animOut);
        modalContent.style.setProperty('--animate-duration', '0.35s');
        modalContent.addEventListener('animationend', animationEndHandler, { once: true });
    } else {
        animationEndHandler();
    }
}

export function collectAndSaveSettings() {
    applyTheme(dom.themeSelect.value);
    applyFontSize(dom.fontSizeInput.value);
    applyAnimationLevel(dom.animationLevelSelect.value);

    state.autoScroll = dom.autoScrollToggle.checked;
    state.soundEnabled = dom.soundEnabledToggle.checked;
    state.showChatBubblesThink = dom.showChatBubblesThinkToggle.checked;
    state.showLogBubblesThink = dom.showLogBubblesThinkToggle.checked;
    state.autoSubmitQuickActions = dom.autoSubmitQuickActionsToggle.checked;
    state.isIdtComponentVisible = dom.componentVisibilityToggle.checked;
    toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);

    dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
    const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
    if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';

    savePersistentSettings();
}

export function resetToDefaultSettings() {
    const defaults = {
        theme: 'auto-crystal',
        fontSize: '16',
        animationLevel: 'full',
        autoScroll: true,
        soundEnabled: false,
        showChatBubblesThink: true,
        showLogBubblesThink: true,
        sidebarExpanded: window.innerWidth > 1024,
        sessionManagerCollapsed: false,
        isProcessLogSidebarVisible: false,
        isProcessLogSidebarCollapsed: true,
        autoSubmitQuickActions: true,
        currentMode: 'chat',
        isIdtComponentVisible: true,
        idtComponentTopPercent: '2.5%',
        idtComponentLeftPercent: '1.8%',
    };

    applyTheme(defaults.theme);
    applyFontSize(defaults.fontSize);
    applyAnimationLevel(defaults.animationLevel);
    state.autoScroll = defaults.autoScroll;
    state.soundEnabled = defaults.soundEnabled;
    state.showChatBubblesThink = defaults.showChatBubblesThink;
    state.showLogBubblesThink = defaults.showLogBubblesThink;
    state.autoSubmitQuickActions = defaults.autoSubmitQuickActions;
    state.currentMode = defaults.currentMode;
    state.isIdtComponentVisible = defaults.isIdtComponentVisible;
    toggleThreeBlackHoleVisibility(state.isIdtComponentVisible);

    updateSidebarState(defaults.sidebarExpanded, true);
    updateSessionManagerState(defaults.sessionManagerCollapsed, true);
    state.isProcessLogSidebarVisible = defaults.isProcessLogSidebarVisible;
    state.isProcessLogSidebarCollapsed = defaults.isProcessLogSidebarCollapsed;
    applyFixedLogSidebarLayout();
    updateProcessLogSidebarCollapseState(state.isProcessLogSidebarCollapsed, true);
    if (state.isProcessLogSidebarVisible) showProcessLogSidebar(false); else hideProcessLogSidebar();

    dom.idtComponentToggleBtn.setAttribute('title', state.isIdtComponentVisible ? '停用核心投影' : '激活核心投影');
    const idtIcon = dom.idtComponentToggleBtn.querySelector('i');
    if (idtIcon) idtIcon.className = state.isIdtComponentVisible ? 'fas fa-eye-slash' : 'fas fa-atom';

    document.documentElement.style.setProperty('--idt-offset-top-percentage', defaults.idtComponentTopPercent);
    document.documentElement.style.setProperty('--idt-offset-left-percentage', defaults.idtComponentLeftPercent);

    if (dom.themeSelect) dom.themeSelect.value = defaults.theme;
    if (dom.fontSizeInput) dom.fontSizeInput.value = defaults.fontSize;
    if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${defaults.fontSize}px`;
    if (dom.animationLevelSelect) dom.animationLevelSelect.value = defaults.animationLevel;
    if (dom.autoScrollToggle) dom.autoScrollToggle.checked = defaults.autoScroll;
    if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = defaults.soundEnabled;
    if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = defaults.showChatBubblesThink;
    if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = defaults.showLogBubblesThink;
    if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = defaults.autoSubmitQuickActions;
    if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = defaults.isIdtComponentVisible;

    dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === defaults.currentMode));
    const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
    // 使用导入的 getModeDisplayName
    dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${sessionNameForPlaceholder})...`;

    savePersistentSettings();
    showToast('系统参数已恢复为默认光绘配置!', 'success');
}
// ==========================================================================
// [ END OF FILE modules/settings_handler.js ]
// ==========================================================================