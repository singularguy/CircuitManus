// ==========================================================================
// [ START OF FILE modules/settings_handler.js ]
// Settings Modal Logic - Opening, Closing, Saving, Resetting
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state, { savePersistentSettings, loadPersistentSettings } from '../core/state.js';
import { applyTheme, applyFontSize, applyAnimationLevel } from './theme_handler.js';
import { toggleThreeBlackHoleVisibility } from './three_visuals.js';
import { getThemeDisplayName, getModeDisplayName, APP_PREFIX } from '../utils/helpers.js'; 
import { updateSidebarState, updateSessionManagerState, applyFixedLogSidebarLayout, updateProcessLogSidebarCollapseState, showProcessLogSidebar, hideProcessLogSidebar } from './layout_handler.js';
import { showToast } from '../core/ui_updater.js';


/**
 * Populates the LLM model selection dropdown based on availability from backend.
 */
export function populateLLMModelSelect() { 
    if (!dom.llmModelSelect) {
        console.warn("LLM模型选择下拉框元素 (llm-model-select) 未找到。");
        return;
    }

    dom.llmModelSelect.innerHTML = ''; // 清空现有选项

    // 从 state.agentDefaultSettings 中获取包含可用性信息的模型列表
    const detailedLLMs = state.agentDefaultSettings?.detailed_available_llms;
    
    if (!detailedLLMs || !Array.isArray(detailedLLMs) || detailedLLMs.length === 0) {
        // 如果没有可用的模型信息，或者格式不正确，可以显示一个默认的或提示信息
        const defaultOption = document.createElement('option');
        defaultOption.value = state.agentDefaultSettings?.default_llm_identifier || "zhipu-ai";
        defaultOption.textContent = `默认 (${defaultOption.value === "zhipu-ai" ? "智谱GLM" : "未知"}) - 模型列表加载失败`;
        defaultOption.disabled = true; // 因为列表加载失败，所以禁用
        dom.llmModelSelect.appendChild(defaultOption);
        console.warn("未能从后端获取详细的可用LLM列表，或列表为空。");
        return;
    }
    
    detailedLLMs.forEach(modelInfo => {
        const option = document.createElement('option');
        option.value = modelInfo.id; 
        // 使用后端提供的 name 作为显示文本
        option.textContent = modelInfo.name || modelInfo.id; 
        
        if (modelInfo.available === false) { // 严格检查布尔值 false
            option.disabled = true;
            option.textContent += " (API Key未配置或不可用)"; // 附加提示信息
        } else {
            option.disabled = false;
        }
        dom.llmModelSelect.appendChild(option); 
    });

    // 设置下拉框的当前选中值为 state.selectedLLM 
    // 确保 state.selectedLLM 的值在可用且未禁用的选项中，否则选择第一个可用的
    let foundSelected = false;
    for (let i = 0; i < dom.llmModelSelect.options.length; i++) {
        if (dom.llmModelSelect.options[i].value === state.selectedLLM && !dom.llmModelSelect.options[i].disabled) {
            dom.llmModelSelect.value = state.selectedLLM;
            foundSelected = true;
            break;
        }
    }
    if (!foundSelected) { // 如果当前选中的模型不可用，则尝试选择默认模型，如果默认模型也不可用，则选第一个可用的
        let fallbackToDefault = false;
        const defaultIdentifier = state.agentDefaultSettings?.default_llm_identifier;
        for (let i = 0; i < dom.llmModelSelect.options.length; i++) {
            if (dom.llmModelSelect.options[i].value === defaultIdentifier && !dom.llmModelSelect.options[i].disabled) {
                dom.llmModelSelect.value = defaultIdentifier;
                state.selectedLLM = defaultIdentifier; // 更新state以反映实际选择
                fallbackToDefault = true;
                break;
            }
        }
        if (!fallbackToDefault) { // 如果默认模型也不可用，选择第一个可用的
            for (let i = 0; i < dom.llmModelSelect.options.length; i++) {
                if (!dom.llmModelSelect.options[i].disabled) {
                    dom.llmModelSelect.value = dom.llmModelSelect.options[i].value;
                    state.selectedLLM = dom.llmModelSelect.options[i].value; // 更新state
                    break;
                }
            }
        }
    }
    console.log(`模型选择UI已更新，当前选中: ${state.selectedLLM}`);
}


export function updateChineseDeepThinkingToggleState() { 
    const settingItem = document.getElementById('chinese-deep-thinking-setting-item');
    if (!settingItem || !dom.enableChineseDeepThinkingToggle) return;

    const globallyEnabled = state.agentDefaultSettings?.globally_enable_chinese_thinking;

    if (globallyEnabled === false) { 
        settingItem.style.display = 'none'; 
        settingItem.setAttribute('aria-hidden', 'true'); // For accessibility
        state.enableChineseDeepThinking = false; 
        dom.enableChineseDeepThinkingToggle.checked = false;
        dom.enableChineseDeepThinkingToggle.disabled = true; 
    } else {
        settingItem.style.display = 'flex'; 
        settingItem.setAttribute('aria-hidden', 'false');
        dom.enableChineseDeepThinkingToggle.disabled = false; 
        dom.enableChineseDeepThinkingToggle.checked = state.enableChineseDeepThinking;
    }
    console.log(`中文深度思考UI已更新，全局启用: ${globallyEnabled}, 当前用户偏好(开关状态): ${dom.enableChineseDeepThinkingToggle.checked}`);
}


export function openSettingsModal() {
    // 先从 state 中加载当前值到 UI 控件 (这些是localStorage加载或之前状态)
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

    // 再调用这两个函数，它们会使用 state.agentDefaultSettings (由init_success填充) 和 state.selectedLLM/enableChineseDeepThinking 来正确设置UI
    populateLLMModelSelect(); 
    updateChineseDeepThinkingToggleState(); 

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
        loadPersistentSettings(); // 这会从localStorage加载，并可能覆盖当前的state值

        // 应用加载回来的设置到UI
        applyTheme(state.currentTheme, true); 
        applyFontSize(localStorage.getItem(APP_PREFIX + 'fontSize') || '16');
        applyAnimationLevel(state.animationLevel);

        if (dom.autoScrollToggle) dom.autoScrollToggle.checked = state.autoScroll;
        if (dom.soundEnabledToggle) dom.soundEnabledToggle.checked = state.soundEnabled;
        if (dom.showChatBubblesThinkToggle) dom.showChatBubblesThinkToggle.checked = state.showChatBubblesThink;
        if (dom.showLogBubblesThinkToggle) dom.showLogBubblesThinkToggle.checked = state.showLogBubblesThink;
        if (dom.autoSubmitQuickActionsToggle) dom.autoSubmitQuickActionsToggle.checked = state.autoSubmitQuickActions;
        if (dom.componentVisibilityToggle) dom.componentVisibilityToggle.checked = state.isIdtComponentVisible;
        
        // 确保模型和中文思考UI也恢复到保存的状态
        // loadPersistentSettings 已经更新了 state.selectedLLM 和 state.enableChineseDeepThinking
        populateLLMModelSelect();
        updateChineseDeepThinkingToggleState();

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

    if (dom.llmModelSelect) {
        state.selectedLLM = dom.llmModelSelect.value;
    }
    if (dom.enableChineseDeepThinkingToggle) {
        if (state.agentDefaultSettings?.globally_enable_chinese_thinking !== false) {
            state.enableChineseDeepThinking = dom.enableChineseDeepThinkingToggle.checked;
        } else {
            state.enableChineseDeepThinking = false; 
        }
    }
    
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
        // 使用 agentDefaultSettings 中的值作为重置目标
        selectedLLM: state.agentDefaultSettings?.default_llm_identifier || 'zhipu-ai',
        enableChineseDeepThinking: state.agentDefaultSettings?.default_enable_chinese_thinking || false,
    };

    // 应用所有默认设置到 state 和 UI
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

    // 更新UI控件以反映默认值
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

    // 重置模型选择和中文思考的状态和UI
    state.selectedLLM = defaults.selectedLLM;
    state.enableChineseDeepThinking = defaults.enableChineseDeepThinking;
    populateLLMModelSelect(); // 这会根据新的 state.selectedLLM 和 agentDefaultSettings.detailed_available_llms 更新UI
    updateChineseDeepThinkingToggleState(); // 这会根据新的 state.enableChineseDeepThinking 和全局设置更新UI

    dom.sidebarButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === defaults.currentMode));
    const sessionNameForPlaceholder = state.sessions[state.currentSessionId]?.name || '当前项目';
    dom.userInput.placeholder = `向Lumina核心发送指令 (${getModeDisplayName(state.currentMode)}模式，当前项目: ${sessionNameForPlaceholder})...`;

    savePersistentSettings();
    showToast('系统参数已恢复为默认光绘配置!', 'success');
}
// ==========================================================================
// [ END OF FILE modules/settings_handler.js ]
// ==========================================================================