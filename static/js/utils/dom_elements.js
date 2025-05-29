// ==========================================================================
// [ START OF FILE utils/dom_elements.js ]
// DOM Element Cache - 集中获取和管理所有DOM元素的引用。
// ==========================================================================

// 使用 const 声明 dom 对象，确保其在模块作用域内不被意外重新赋值。
// 立即执行函数 (IIFE) 用于封装DOM查询逻辑，确保在模块加载时执行一次。
const domElements = (() => {
    // 返回一个包含所有DOM元素引用的对象
    return {
        // 动态背景相关
        dynamicBackground: document.querySelector('.dynamic-crystal-background'),
        // 加载动画相关
        loader: document.getElementById('loader'),
        loaderCore: document.querySelector('.lumina-loader-core'),
        mainContainer: document.getElementById('main-container'),
        appBodyContainer: document.getElementById('appBodyContainer'),
        // 聊天核心区域
        chatArea: document.getElementById('chat-area'),
        chatBox: document.getElementById('chat-box'),
        userInput: document.getElementById('user-input'),
        sendButton: document.getElementById('send-button'),
        sendIcon: document.querySelector('.send-icon'),
        sendLoadingIcon: document.querySelector('.send-loading-icon'),
        // 头部与主题
        appHeader: document.getElementById('app-header'),
        themeToggleButton: document.getElementById('theme-toggle'),
        themeToggleIcon: document.querySelector('#theme-toggle i'),
        clearChatButton: document.getElementById('clear-chat'),
        leftSidebarToggle: document.getElementById('left-sidebar-toggle'),
        toggleProcessLogVisibilityButton: document.getElementById('toggle-process-log-visibility'),
        // 侧边栏与会话管理 (左侧边栏)
        sidebar: document.getElementById('sidebar'),
        sidebarButtons: document.querySelectorAll('.sidebar-button'),
        sessionManager: document.getElementById('session-manager'),
        sessionManagerToggle: document.getElementById('session-manager-toggle'),
        sessionListContainer: document.getElementById('session-list-container'),
        sessionList: document.getElementById('session-list'),
        createNewSessionButton: document.getElementById('create-new-session'),
        currentSessionNameDisplay: document.getElementById('current-session-name'),
        editSessionNameButton: document.getElementById('edit-session-name-btn'),
        // 输入区域与文件上传
        inputArea: document.getElementById('input-area'),
        attachButton: document.getElementById('attach-button'),
        micButton: document.getElementById('mic-button'),
        charCounter: document.getElementById('char-counter'),
        fileInput: document.getElementById('file-input'),
        filePreviewArea: document.getElementById('file-preview'),
        filePreviewContent: document.getElementById('file-preview-content'),
        closeFilePreviewButton: document.getElementById('close-preview'),
        // Toast 通知
        toastContainer: document.getElementById('toast-container'),
        // Agent 处理过程日志区域 (右侧悬浮侧栏)
        processLogSidebarContainer: document.getElementById('agent-process-sidebar'),
        processLogSidebarHeader: document.querySelector('#agent-process-sidebar .process-log-header'),
        processLogSidebarContent: document.getElementById('process-log-content-sidebar'),
        toggleProcessLogSidebarCollapseButton: document.getElementById('toggle-process-log-sidebar-collapse'),
        closeProcessLogSidebarButton: document.getElementById('close-process-log-sidebar'),
        // 设置模态框相关
        settingsModal: document.getElementById('settings-modal'),
        openSettingsButton: document.querySelector('.sidebar-button[data-mode="settings"]'),
        closeSettingsButton: document.getElementById('close-settings'),
        themeSelect: document.getElementById('theme-select'),
        fontSizeInput: document.getElementById('font-size'),
        fontSizeValue: document.getElementById('font-size-value'),
        animationLevelSelect: document.getElementById('animation-level'),
        autoScrollToggle: document.getElementById('auto-scroll'),
        soundEnabledToggle: document.getElementById('sound-enabled'),
        showChatBubblesThinkToggle: document.getElementById('show-chat-bubbles-think'),
        showLogBubblesThinkToggle: document.getElementById('show-log-bubbles-think'),
        autoSubmitQuickActionsToggle: document.getElementById('auto-submit-quick-actions'),
        componentVisibilityToggle: document.getElementById('component-visibility-toggle'),
        resetSettingsButton: document.getElementById('reset-settings'),
        saveSettingsButton: document.getElementById('save-settings'),
        
        // ==================================================================
        // 【老板，关键修复在这里！】
        // 新增：获取 LLM 模型选择下拉框 和 中文深度思考切换开关
        // 这两个元素在 settings_handler.js 中被频繁使用，之前遗漏了获取。
        llmModelSelect: document.getElementById('llm-model-select'), // 添加对模型选择下拉框的获取
        enableChineseDeepThinkingToggle: document.getElementById('enable-chinese-deep-thinking-toggle'), // 添加对中文思考开关的获取
        // ==================================================================

        // 3D组件显示开关与包装器
        idtComponentToggleBtn: document.getElementById('toggleIdtComponentBtn'),
        idtComponentWrapper: document.getElementById('idtTechComponentWrapper')
    };
})();

// 默认导出 domElements 对象，以便其他模块可以导入和使用。
// 使用 ES6 模块导出语法。
export default domElements;
// ==========================================================================
// [ END OF FILE utils/dom_elements.js ]
// ==========================================================================