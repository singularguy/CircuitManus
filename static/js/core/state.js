// ==========================================================================
// [ START OF FILE core/state.js ]
// Application State Management and Persistence
// ==========================================================================

import { APP_PREFIX } from '../utils/helpers.js'; // 从 helpers.js 导入 APP_PREFIX

// 初始应用状态对象。
// 该对象包含应用运行时的所有核心状态和用户配置。
let state = {
    sessions: {}, // 结构: { [sessionId]: { id, name, messages: [], createdAt, lastActivity } }
    currentSessionId: null,
    currentTheme: 'auto-crystal', // 可选值: 'auto-crystal', 'light-crystal', 'dark-crystal'
    autoScroll: true,
    soundEnabled: false,
    showChatBubblesThink: true,
    showLogBubblesThink: true,
    animationLevel: 'full', // 可选值: 'full', 'basic', 'none'
    currentMode: 'chat', // 可选值: 'chat', 'code', 'circuit', 'settings'
    uploadedFiles: [], // File对象的数组
    isAgentTyping: false,
    isLoading: false, // 全局加载状态，用于Agent回复
    isSidebarExpanded: window.innerWidth > 1024, // 根据窗口宽度初始化侧边栏展开状态
    isSessionManagerCollapsed: false,
    isProcessLogSidebarVisible: false,
    isProcessLogSidebarCollapsed: true,
    maxInputChars: 8000,
    currentClientRequestId: null, // 用于跟踪特定客户端请求的响应
    lastResponseThinking: null, // 缓存上一次的思考过程，以备JSON解析失败时显示
    autoSubmitQuickActions: true,
    isIdtComponentVisible: true, // 3D组件的可见性状态
    // 3D组件拖拽相关状态
    isDraggingComponent: false,
    componentDragStartX: 0,
    componentDragStartY: 0,
    componentInitialTopPx: 0,
    componentInitialLeftPx: 0,
    // Three.js 相关状态
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
    // UI中用于跟踪处理日志中待处理工具调用的状态
    pendingToolCalls: {}, // 结构: { [toolCallId]: { name, args_summary, ui_hints, order } }
};

/**
 * 将所有持久化的应用设置保存到localStorage。
 */
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

        console.log("系统参数数据已保存到归档 (localStorage).");
    } catch (e) {
        console.error("保存设置到localStorage失败:", e);
        // import { showToast } from './ui_updater.js'; // 假设可以这样导入
        // showToast("未能保存用户偏好设置。", "error");
    }
}

/**
 * 从localStorage加载持久化的应用设置到state对象。
 */
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
    // --idt-offset-top-percentage 和 --idt-offset-left-percentage 的默认值来自 CSS :root
    // 这里如果 localStorage 没有值，则不改变 CSS 变量，让 CSS 的默认值生效
    if (savedTopPercent !== null) document.documentElement.style.setProperty('--idt-offset-top-percentage', savedTopPercent);
    if (savedLeftPercent !== null) document.documentElement.style.setProperty('--idt-offset-left-percentage', savedLeftPercent);
    
    const savedFontSize = localStorage.getItem(APP_PREFIX + 'fontSize') || '16'; // Default to '16' if not found
    document.documentElement.style.setProperty('--base-font-size', `${savedFontSize}px`);

    console.log("从localStorage加载了用户偏好设置到应用状态。");
}

export default state;
// ==========================================================================
// [ END OF FILE core/state.js ]
// ==========================================================================