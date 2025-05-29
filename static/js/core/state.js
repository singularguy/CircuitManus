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
    currentClientRequestId: null, // 前端为当前用户请求生成的唯一ID
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
        detailed_available_llms: []
    },

    // 【老板，新增属性！】 用于存储当前正在处理的用户请求的日志条目集合
    // 当一个新请求开始时，我们会在这里创建一个新的日志集合对象。
    // 当请求结束时（收到 final_response），此对象会被移入到 sessions[sessionId].executionLogs 中。
    currentRequestLogCollection: null 
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

    state.selectedLLM = localStorage.getItem(APP_PREFIX + 'selectedLLM') || state.agentDefaultSettings.default_llm_identifier; 
    state.enableChineseDeepThinking = (localStorage.getItem(APP_PREFIX + 'enableChineseDeepThinking') || state.agentDefaultSettings.default_enable_chinese_thinking.toString()) === 'true';

    console.log("从localStorage加载了用户偏好设置到应用状态。");
}

export default state;
// ==========================================================================
// [ END OF FILE core/state.js ]
// ==========================================================================