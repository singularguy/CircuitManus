// ==========================================================================
// [ START OF FILE core/state.js ]
// Application State Management and Persistence
// ==========================================================================

import { APP_PREFIX } from '../utils/helpers.js'; 

let state = {
    sessions: {}, 
    currentSessionId: null,
    currentTheme: 'auto-crystal', 
    autoScroll: true, 
    soundEnabled: false, 
    showChatBubblesThink: true, 
    showLogBubblesThink: true, 
    animationLevel: 'full', 
    currentMode: 'chat', 
    uploadedFiles: [], 
    isAgentTyping: false, 
    isLoading: false, 
    isSidebarExpanded: window.innerWidth > 1024, 
    isSessionManagerCollapsed: false, 
    isProcessLogSidebarVisible: false, 
    isProcessLogSidebarCollapsed: true, 
    maxInputChars: 8000,
    currentClientRequestId: null, 
    lastResponseThinking: null, 
    autoSubmitQuickActions: true, 
    isIdtComponentVisible: true, 
    isDraggingComponent: false,
    componentDragStartX: 0,
    componentDragStartY: 0,
    componentInitialTopPx: 0,
    componentInitialLeftPx: 0,
    threeJsScene: null, 
    threeJsRenderer: null, 
    threeJsCamera: null, 
    threeJsAnimationId: null, 
    threeJsInitialized: false, 
    threeBlackHoleGroup: null, 
    threeAccretionDiskOuter: null, 
    threeAccretionDiskMiddle: null, 
    threeAccretionDiskInner: null, 
    threeStarField: null, 
    pendingToolCalls: {}, 

    selectedLLM: 'zhipu-ai', 
    enableChineseDeepThinking: false, 
    
    agentDefaultSettings: {
        default_llm_identifier: 'zhipu-ai', 
        default_enable_chinese_thinking: false, 
        globally_enable_chinese_thinking: true, 
        // 【修改】键名改为 detailed_available_llms，并期望其值为对象数组
        detailed_available_llms: [ 
            // { id: "zhipu-ai", name: "智谱清言 (GLM)", available: true }, // 示例结构
            // { id: "deepseek", name: "DeepSeek 大模型", available: false }
        ]
    }
};

export function savePersistentSettings() {
    try {
        localStorage.setItem(APP_PREFIX + 'theme', state.currentTheme);
        const effectiveFontSize = document.documentElement.style.getPropertyValue('--base-font-size').replace('px', '');
        localStorage.setItem(APP_PREFIX + 'fontSize', effectiveFontSize || '16');
        localStorage.setItem(APP_PREFIX + 'animationLevel', state.animationLevel);
        localStorage.setItem(APP_PREFIX + 'autoScroll', state.autoScroll.toString());
        localStorage.setItem(APP_PREFIX + 'soundEnabled', state.soundEnabled.toString());
        localStorage.setItem(APP_PREFIX + 'showChatBubblesThink', state.showChatBubblesThink.toString());
        localStorage.setItem(APP_PREFIX + 'showLogBubblesThink', state.showLogBubblesThink.toString());
        localStorage.setItem(APP_PREFIX + 'sidebarExpanded', state.isSidebarExpanded.toString());
        localStorage.setItem(APP_PREFIX + 'sessionManagerCollapsed', state.isSessionManagerCollapsed.toString());
        localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarVisible', state.isProcessLogSidebarVisible.toString());
        localStorage.setItem(APP_PREFIX + 'isProcessLogSidebarCollapsed', state.isProcessLogSidebarCollapsed.toString());
        localStorage.setItem(APP_PREFIX + 'autoSubmitQuickActions', state.autoSubmitQuickActions.toString());
        localStorage.setItem(APP_PREFIX + 'currentMode', state.currentMode);
        localStorage.setItem(APP_PREFIX + 'isIdtComponentVisible', state.isIdtComponentVisible.toString());
        localStorage.setItem(APP_PREFIX + 'idtComponentTopPercent', document.documentElement.style.getPropertyValue('--idt-offset-top-percentage'));
        localStorage.setItem(APP_PREFIX + 'idtComponentLeftPercent', document.documentElement.style.getPropertyValue('--idt-offset-left-percentage'));
        localStorage.setItem(APP_PREFIX + 'selectedLLM', state.selectedLLM);
        localStorage.setItem(APP_PREFIX + 'enableChineseDeepThinking', state.enableChineseDeepThinking.toString());

        console.log("系统参数数据已保存到归档 (localStorage).");
    } catch (e) {
        console.error("保存设置到localStorage失败:", e);
    }
}

export function loadPersistentSettings() {
    state.currentTheme = localStorage.getItem(APP_PREFIX + 'theme') || state.currentTheme;
    state.animationLevel = localStorage.getItem(APP_PREFIX + 'animationLevel') || state.animationLevel;
    state.autoScroll = (localStorage.getItem(APP_PREFIX + 'autoScroll') || state.autoScroll.toString()) === 'true';
    state.soundEnabled = (localStorage.getItem(APP_PREFIX + 'soundEnabled') || state.soundEnabled.toString()) === 'true';
    state.showChatBubblesThink = (localStorage.getItem(APP_PREFIX + 'showChatBubblesThink') || state.showChatBubblesThink.toString()) === 'true';
    state.showLogBubblesThink = (localStorage.getItem(APP_PREFIX + 'showLogBubblesThink') || state.showLogBubblesThink.toString()) === 'true';
    state.isSidebarExpanded = (localStorage.getItem(APP_PREFIX + 'sidebarExpanded') || state.isSidebarExpanded.toString()) === 'true';
    state.isSessionManagerCollapsed = (localStorage.getItem(APP_PREFIX + 'sessionManagerCollapsed') || state.isSessionManagerCollapsed.toString()) === 'true';
    state.isProcessLogSidebarVisible = (localStorage.getItem(APP_PREFIX + 'isProcessLogSidebarVisible') || state.isProcessLogSidebarVisible.toString()) === 'true';
    state.isProcessLogSidebarCollapsed = (localStorage.getItem(APP_PREFIX + 'isProcessLogSidebarCollapsed') || state.isProcessLogSidebarCollapsed.toString()) === 'true';
    state.autoSubmitQuickActions = (localStorage.getItem(APP_PREFIX + 'autoSubmitQuickActions') || state.autoSubmitQuickActions.toString()) === 'true';
    state.currentMode = localStorage.getItem(APP_PREFIX + 'currentMode') || state.currentMode;
    state.isIdtComponentVisible = (localStorage.getItem(APP_PREFIX + 'isIdtComponentVisible') || state.isIdtComponentVisible.toString()) === 'true';

    const savedTopPercent = localStorage.getItem(APP_PREFIX + 'idtComponentTopPercent');
    const savedLeftPercent = localStorage.getItem(APP_PREFIX + 'idtComponentLeftPercent');
    if (savedTopPercent !== null) document.documentElement.style.setProperty('--idt-offset-top-percentage', savedTopPercent);
    if (savedLeftPercent !== null) document.documentElement.style.setProperty('--idt-offset-left-percentage', savedLeftPercent);
    
    const savedFontSize = localStorage.getItem(APP_PREFIX + 'fontSize') || '16'; 
    document.documentElement.style.setProperty('--base-font-size', `${savedFontSize}px`);

    // 加载 selectedLLM 和 enableChineseDeepThinking 时，使用 agentDefaultSettings 中的默认值作为后备
    // 注意：agentDefaultSettings 此刻可能还未被后端数据填充，所以这里的 || state.agentDefaultSettings... 仍然会是JS层面最初始的定义
    // 真正的后端默认值会在 init_success 消息处理时覆盖这些。
    state.selectedLLM = localStorage.getItem(APP_PREFIX + 'selectedLLM') || state.agentDefaultSettings.default_llm_identifier; 
    state.enableChineseDeepThinking = (localStorage.getItem(APP_PREFIX + 'enableChineseDeepThinking') || state.agentDefaultSettings.default_enable_chinese_thinking.toString()) === 'true';

    console.log("从localStorage加载了用户偏好设置到应用状态。");
}

export default state;
// ==========================================================================
// [ END OF FILE core/state.js ]
// ==========================================================================
