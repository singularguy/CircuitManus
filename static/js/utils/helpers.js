// ==========================================================================
// [ START OF FILE utils/helpers.js ]
// 通用辅助函数库
// ==========================================================================

// 定义并导出应用前缀常量 - 这是 APP_PREFIX 的唯一真实来源
export const APP_PREFIX = 'CircuitManusPro_LuminaScript_';

/**
 * 生成唯一的会话ID。
 * @returns {string} 生成的会话ID。
 */
export function generateSessionId() {
    return `session_lumina_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 12)}`;
}

/**
 * 生成唯一的客户端请求ID。
 * @returns {string} 生成的请求ID。
 */
export function generateClientRequestId() {
    return `creq_lumina_proc_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 10)}`;
}

/**
 * 格式化时间戳为用户友好的相对时间字符串。
 * @param {number} dateTimestamp - 时间戳。
 * @returns {string} 格式化后的时间字符串。
 */
export function formatTimeSince(dateTimestamp) {
    const now = new Date();
    const secondsPast = (now.getTime() - dateTimestamp) / 1000;

    if (secondsPast < 60) return '刚刚';
    if (secondsPast < 3600) return `${Math.round(secondsPast / 60)}分前`;
    if (secondsPast <= 86400) return `${Math.round(secondsPast / 3600)}时前`;

    const daysPast = Math.round(secondsPast / 86400);
    if (daysPast === 1) return '昨天';
    if (daysPast < 7) return `${daysPast}天前`;

    const date = new Date(dateTimestamp);
    if (now.getFullYear() === date.getFullYear()) {
        return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    }
    return date.toLocaleDateString(undefined, { year: '2-digit', month: 'short', day: 'numeric' });
}

/**
 * 根据文件类型和名称获取对应的FontAwesome图标类。
 * @param {string} fileType - 文件的MIME类型。
 * @param {string} fileName - 文件名。
 * @returns {string} FontAwesome图标类名。
 */
export function getFileIconClass(fileType, fileName) {
    if (fileType.startsWith('image/')) return 'fa-file-image';
    if (fileType.startsWith('audio/')) return 'fa-file-audio';
    if (fileType.startsWith('video/')) return 'fa-file-video';
    if (fileType === 'application/pdf') return 'fa-file-pdf';
    if (fileType === 'application/zip' || fileName.endsWith('.zip') || fileName.endsWith('.rar') || fileName.endsWith('.7z')) return 'fa-file-archive';

    const ext = fileName.slice(fileName.lastIndexOf(".")).toLowerCase();
    const codeExtensions = ['.js', '.ts', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sh', '.bat', '.v', '.sv', '.vhd', '.md', '.txt', '.log', '.sch', '.brd', '.cir', '.net', '.vhd'];
    if (codeExtensions.includes(ext) || fileType.includes('text')) return 'fa-file-code';
    if (['.doc', '.docx'].includes(ext)) return 'fa-file-word';
    if (['.xls', '.xlsx', '.csv'].includes(ext)) return 'fa-file-excel';
    if (['.ppt', '.pptx'].includes(ext)) return 'fa-file-powerpoint';
    if (['.dwg', '.dxf'].includes(ext)) return 'fa-drafting-compass';
    return 'fa-file-alt'; // Default icon
}

/**
 * 总结工具调用的参数对象，用于日志显示。
 * @param {object} argsObj - 工具参数对象。
 * @returns {string} 参数的简短字符串表示。
 */
export function summarizeArguments(argsObj) {
    if (!argsObj || typeof argsObj !== 'object' || Object.keys(argsObj).length === 0) {
        return "(无参数)";
    }
    try {
        return JSON.stringify(argsObj, (key, value) => {
            if (typeof value === 'string' && value.length > 40) {
                return value.substring(0, 37) + "...";
            }
            return value;
        }).substring(0, 200);
    } catch (e) {
        console.warn("总结参数时发生错误:", e);
        return "(参数总结出错)";
    }
}

/**
 * 解析日志项的CSS类字符串，提取类型、阶段和状态。
 * @param {string} itemClassesStr - 包含多个CSS类的字符串。
 * @returns {object} 解析后的对象，包含 type, stage, status 属性。
 */
export function parseItemClasses(itemClassesStr) {
    const classes = itemClassesStr ? itemClassesStr.split(' ') : [];
    const parsed = { type: null, stage: null, status: null };
    classes.forEach(cls => {
        if (cls.startsWith('type-')) parsed.type = cls.substring(5);
        else if (cls.startsWith('stage-')) parsed.stage = cls.substring(6);
        else if (cls.startsWith('status-')) parsed.status = cls.substring(7);
        else if (cls.startsWith('phase-')) parsed.stage = cls.substring(6); // Compatibility
    });
    return parsed;
}

/**
 * 获取当前模式的用户友好显示名称。
 * @param {string} mode - 模式的内部标识符。
 * @returns {string} 模式的显示名称。
 */
export function getModeDisplayName(mode) {
    const names = { chat: '灵感交流', code: '代码绘卷', circuit: '电路拓印', settings: '参数调校' };
    return names[mode] || '未知领域';
}

/**
 * 获取当前主题的用户友好显示名称。
 * @param {string} theme - 主题的内部标识符。
 * @returns {string} 主题的显示名称。
 */
export function getThemeDisplayName(theme) {
    const names = {
        'light-crystal': '月白宣纸 (Light)',
        'dark-crystal': '墨黑星空 (Dark)',
        'auto-crystal': '随境而变 (Auto)'
    };
    return names[theme] || '未知意境';
}

/**
 * 格式化日志项的详细信息对象为HTML字符串。
 * @param {object} details - 包含详细信息的对象。
 * @param {string|null} type - 日志项类型。
 * @param {string|null} stage - 日志项阶段。
 * @param {string|null} status - 日志项状态。
 * @returns {string|null} 格式化后的HTML字符串，如果无有效细节则返回null。
 */
export function formatLogDetails(details, type, stage, status) {
    if (!details || typeof details !== 'object' || Object.keys(details).length === 0) {
        return null;
    }
    let html = '';
    const formatRecursive = (obj, currentType, currentStage, currentStatus, indentLevel = 0) => {
        let partHtml = '';
        for (const key in obj) {
            if (Object.prototype.hasOwnProperty.call(obj, key)) {
                const value = obj[key];
                const displayKey = key
                    .replace(/([A-Z])/g, " $1")
                    .replace(/_/g, ' ')
                    .trim()
                    .replace(/\b\w/g, char => char.toUpperCase());
                const paddingLeftStyle = `padding-left: ${indentLevel * 10}px;`;

                if ((type === 'plan_details' || type === 'tool_status_update') && key === 'tool_call_id') {
                    continue;
                }

                if (key === 'uiHints' && typeof value === 'object' && value !== null) {
                    const dn = String(value.displayNameForTool || 'N/A').replace(/</g, "<").replace(/>/g, ">");
                    const ed = String(value.estimatedDurationCategory || 'N/A').replace(/</g, "<").replace(/>/g, ">");
                    const spg = value.showProgressGranularly !== undefined ? `, 细粒度进度: ${value.showProgressGranularly ? '是' : '否'}` : '';
                    partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">UI投影:</strong> <span class="log-detail-value">显示: ${dn}, 时长: ${ed}${spg}</span></div>`;
                } else if (key === 'result_data_preview' && typeof value === 'string') {
                    let previewContent = String(value).replace(/</g, "<").replace(/>/g, ">");
                    partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">结果预览:</strong> <pre class="log-detail-raw-json"><code>${previewContent}</code></pre></div>`;
                } else if ((type === 'plan_details' || type === 'tool_status_update') && (key === 'arguments' || key === 'toolArguments') && typeof value === 'object' && value !== null) {
                    let argItems = [];
                    for (const argKey in value) {
                        const formattedArgKey = argKey.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                        const argValue = value[argKey];
                        let formattedArgValue;
                        if (typeof argValue === 'object' && argValue !== null) {
                            try { formattedArgValue = JSON.stringify(argValue).replace(/</g, "<").replace(/>/g, ">"); }
                            catch (e) { formattedArgValue = String(argValue).replace(/</g, "<").replace(/>/g, ">") + " (JSON error)"; }
                        } else {
                            formattedArgValue = String(argValue).replace(/</g, "<").replace(/>/g, ">");
                        }
                        argItems.push(`<em class="log-arg-key">${formattedArgKey}</em>: ${formattedArgValue}`);
                    }
                    partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong> <span class="log-detail-value">${argItems.join('; ')}</span></div>`;
                } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    partHtml += `<div class="log-detail-item log-detail-object-header" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong></div>`;
                    partHtml += formatRecursive(value, currentType, currentStage, currentStatus, indentLevel + 1);
                } else if (Array.isArray(value)) {
                    const arrayItems = value.map(item => {
                        if (typeof item === 'object' && item !== null) return JSON.stringify(item).replace(/</g, "<").replace(/>/g, ">");
                        return String(item).replace(/</g, "<").replace(/>/g, ">");
                    });
                    partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong> <span class="log-detail-value log-detail-array">[${arrayItems.join(', ')}]</span></div>`;
                } else {
                    const sanitizedValue = String(value).replace(/</g, "<").replace(/>/g, ">");
                    partHtml += `<div class="log-detail-item" style="${paddingLeftStyle}"><strong class="log-detail-key">${displayKey}:</strong> <span class="log-detail-value">${sanitizedValue}</span></div>`;
                }
            }
        }
        return partHtml;
    };
    html = formatRecursive(details, type, stage, status, 0);
    return html || null;
}
// ==========================================================================
// [ END OF FILE utils/helpers.js ]
// ==========================================================================