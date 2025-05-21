// ==========================================================================
// [ START OF FILE modules/file_handler.js ]
// File Handling - Selection, Preview, Removal
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from '../core/state.js';
import { showToast } from '../core/ui_updater.js';
import { getFileIconClass } from '../utils/helpers.js';

/**
 * Handles file selection from the input element.
 * @param {Event} event - The file input change event.
 */
export function handleFileSelection(event) {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    const MAX_FILES = 5;
    const MAX_SIZE_MB = 2;

    files.forEach(file => {
        if (state.uploadedFiles.length >= MAX_FILES) {
            showToast(`每次传输最多允许 ${MAX_FILES} 个数据卷轴.`, 'warning');
            return; // Exits forEach iteration for this file, but continues for others if any
        }
        if (file.size > MAX_SIZE_MB * 1024 * 1024) {
            showToast(`数据卷轴 "${file.name}" 大小超过 ${MAX_SIZE_MB}MB 限制.`, 'warning');
            return; // Skip this file
        }
        if (!state.uploadedFiles.find(f => f.name === file.name && f.size === file.size)) {
            state.uploadedFiles.push(file);
            addFileToPreview(file);
        } else {
            showToast(`数据卷轴 "${file.name}" 已在队列中.`, 'info');
        }
    });

    if (state.uploadedFiles.length > 0) {
        dom.filePreviewArea.classList.add('active');
    }
    dom.fileInput.value = ''; // Reset file input to allow selecting the same file again
}

/**
 * Adds a file to the UI preview area.
 * @param {File} file - The file object to add.
 */
export function addFileToPreview(file) {
    const fileItem = document.createElement('div');
    fileItem.classList.add('file-item');
    if (state.animationLevel !== 'none') {
        fileItem.classList.add('animate__animated', 'animate__bounceIn');
        fileItem.style.setProperty('--animate-duration', '0.4s');
    }
    fileItem.dataset.fileName = file.name;
    fileItem.dataset.fileSize = file.size;

    const iconClass = getFileIconClass(file.type, file.name);
    fileItem.innerHTML = `
        <i class="fas ${iconClass} file-icon"></i>
        <span class="file-name" title="${file.name} (${(file.size / 1024).toFixed(1)}KB, 类型: ${file.type || '未知'})">${file.name}</span>
        <button class="file-remove icon-btn" title="移除数据卷轴"><i class="fas fa-times-circle"></i></button>`;

    fileItem.querySelector('.file-remove').addEventListener('click', (e) => {
        e.stopPropagation();
        removeFileFromPreview(file.name, file.size);
    });
    dom.filePreviewContent.appendChild(fileItem);
}

/**
 * Removes a file from the preview area and the upload list.
 * @param {string} fileName - Name of the file to remove.
 * @param {number} fileSize - Size of the file to remove (for disambiguation).
 */
export function removeFileFromPreview(fileName, fileSize) {
    state.uploadedFiles = state.uploadedFiles.filter(f => !(f.name === fileName && f.size === fileSize));
    const fileItemElement = dom.filePreviewContent.querySelector(`.file-item[data-file-name="${CSS.escape(fileName)}"][data-file-size="${fileSize}"]`);

    if (fileItemElement) {
        if (state.animationLevel !== 'none') {
            fileItemElement.classList.remove('animate__bounceIn');
            fileItemElement.classList.add('animate__animated', 'animate__bounceOut');
            fileItemElement.addEventListener('animationend', () => {
                if (fileItemElement.parentElement) {
                     fileItemElement.remove();
                     if (state.uploadedFiles.length === 0) closeFilePreview();
                }
            }, { once: true });
        } else {
            fileItemElement.remove();
            if (state.uploadedFiles.length === 0) closeFilePreview();
        }
    }
}

/**
 * Closes (hides) the file preview area.
 */
export function closeFilePreview() {
    dom.filePreviewArea.classList.remove('active');
}

// ==========================================================================
// [ END OF FILE modules/file_handler.js ]
// ==========================================================================