// ==========================================================================
// [ START OF FILE modules/theme_handler.js ]
// Theme, Font Size, and Animation Level Management
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from '../core/state.js';
import { savePersistentSettings } from '../core/state.js'; // For saving after user interaction if not initial load
import { getThemeDisplayName } from '../utils/helpers.js'; // For toast messages

/**
 * Applies the specified theme.
 * @param {string} themeName - 'light-crystal', 'dark-crystal', 'auto-crystal'.
 * @param {boolean} [initialLoad=false] - Is this the initial load?
 */
export function applyTheme(themeName, initialLoad = false) {
    const body = document.body;
    body.classList.remove('light-crystal-active', 'dark-crystal-active');
    const themeIcon = dom.themeToggleButton.querySelector('i');

    if (themeName === 'auto-crystal') {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            body.classList.add('dark-crystal-active');
        } else {
            body.classList.add('light-crystal-active');
        }
        if (themeIcon) themeIcon.className = 'fas fa-magic';
    } else if (themeName === 'dark-crystal') {
        body.classList.add('dark-crystal-active');
        if (themeIcon) themeIcon.className = 'fas fa-sun';
    } else { // light-crystal
        body.classList.add('light-crystal-active');
        if (themeIcon) themeIcon.className = 'fas fa-moon';
    }
    body.dataset.theme = themeName;
    state.currentTheme = themeName;
    if (dom.themeSelect) dom.themeSelect.value = themeName;

    if (!initialLoad) savePersistentSettings(); // Save if user changed it
    console.log(`显示模式已设定为: ${themeName} (实际生效类: ${body.className.match(/(light|dark)-crystal-active/)?.[0] || '无特定激活类'})`);
}

/**
 * Applies the current theme based on state.
 * Convenience function for initial load or when theme name isn't directly passed.
 */
export function applyCurrentTheme() {
    applyTheme(state.currentTheme, true); // true for initial load
}


/**
 * Applies the specified font size.
 * @param {string|number} size - Font size value (e.g., '16').
 */
export function applyFontSize(size) {
    const newSize = parseInt(size, 10);
    if (isNaN(newSize) || newSize < 12 || newSize > 20) {
        document.documentElement.style.setProperty('--base-font-size', '16px');
        if (dom.fontSizeInput) dom.fontSizeInput.value = '16';
        if (dom.fontSizeValue) dom.fontSizeValue.textContent = '16px';
        return;
    }
    document.documentElement.style.setProperty('--base-font-size', `${newSize}px`);
    if (dom.fontSizeInput) dom.fontSizeInput.value = newSize;
    if (dom.fontSizeValue) dom.fontSizeValue.textContent = `${newSize.toFixed(0)}px`;
}

/**
 * Applies the specified animation level.
 * @param {string} level - 'full', 'basic', 'none'.
 */
export function applyAnimationLevel(level) {
    document.body.dataset.animationLevel = level;
    state.animationLevel = level;
    if (dom.animationLevelSelect && dom.animationLevelSelect.value !== level) {
        dom.animationLevelSelect.value = level;
    }
    console.log(`动态效果等级已设定为: ${level}`);
}

// ==========================================================================
// [ END OF FILE modules/theme_handler.js ]
// ==========================================================================