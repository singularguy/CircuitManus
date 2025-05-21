// ==========================================================================
// [ START OF FILE modules/three_visuals.js ]
// Three.js Black Hole Visual Effect Management and Dragging
// ==========================================================================

import dom from '../utils/dom_elements.js';
import state from '../core/state.js';
import { showToast } from '../core/ui_updater.js'; // For error reporting

const APP_PREFIX = 'CircuitManusPro_LuminaScript_';

/**
 * Initializes the Three.js black hole effect.
 * @param {HTMLElement} container - The DOM element for the Three.js canvas.
 */
export function initThreeBlackHole(container) {
    if (state.threeJsInitialized) {
        if (!state.threeJsAnimationId && state.isIdtComponentVisible) {
            animateThreeBlackHole(); // Restart animation if component is visible
        }
        return;
    }
    if (!container) {
        console.error("Three.js: Container element not found for black hole.");
        return;
    }
    if (typeof THREE === 'undefined') {
        console.error("Three.js library is not loaded.");
        showToast("错误: 3D核心组件库未能加载。", "error", 5000);
        return;
    }

    state.threeJsScene = new THREE.Scene();
    state.threeJsCamera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 2000);
    state.threeJsCamera.position.z = 60;

    state.threeJsRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    state.threeJsRenderer.setSize(container.clientWidth, container.clientHeight);
    state.threeJsRenderer.setPixelRatio(window.devicePixelRatio);
    container.querySelectorAll('canvas').forEach(canvas => canvas.remove()); // Clear previous
    container.appendChild(state.threeJsRenderer.domElement);

    const ambientLight = new THREE.AmbientLight(0xaaaaaa, 0.5);
    state.threeJsScene.add(ambientLight);
    const pointLight = new THREE.PointLight(0xffffff, 1, 500);
    pointLight.position.set(0, 20, 30);
    state.threeJsScene.add(pointLight);

    state.threeBlackHoleGroup = new THREE.Group();
    const sphereRadius = 12;
    const sphereGeometry = new THREE.SphereGeometry(sphereRadius, 48, 48);
    const sphereMaterial = new THREE.MeshStandardMaterial({ color: 0x000000, roughness: 0.8, metalness: 0.1 });
    const eventHorizon = new THREE.Mesh(sphereGeometry, sphereMaterial);
    state.threeBlackHoleGroup.add(eventHorizon);

    const diskColors = [0xff6600, 0xff9933, 0xffcc66];
    const diskOpacities = [0.6, 0.7, 0.8];
    const diskRadii = [sphereRadius + 7, sphereRadius + 14, sphereRadius + 21];
    const diskTubeRadii = [2.5, 3.5, 4.5];
    const diskRotationSpeeds = [0.01, -0.008, 0.012];

    // Initialize with dummy objects to avoid null checks later if creation fails
    state.threeAccretionDiskOuter = new THREE.Mesh();
    state.threeAccretionDiskMiddle = new THREE.Mesh();
    state.threeAccretionDiskInner = new THREE.Mesh();

    [state.threeAccretionDiskOuter, state.threeAccretionDiskMiddle, state.threeAccretionDiskInner] = diskRadii.map((radius, i) => {
        const diskMaterial = new THREE.MeshPhongMaterial({
            color: diskColors[i],
            emissive: new THREE.Color(diskColors[i]).multiplyScalar(0.5),
            specular: 0x333333, shininess: 20,
            side: THREE.DoubleSide, transparent: true, opacity: diskOpacities[i],
            blending: THREE.AdditiveBlending
        });
        const disk = new THREE.Mesh(new THREE.TorusGeometry(radius, diskTubeRadii[i], 16, 60), diskMaterial);
        disk.rotation.x = Math.PI / 1.8;
        disk.userData.rotationSpeed = diskRotationSpeeds[i];
        state.threeBlackHoleGroup.add(disk);
        return disk;
    });

    const starGeometry = new THREE.BufferGeometry();
    const starMaterial = new THREE.PointsMaterial({
        color: 0xffffff, size: 0.25, transparent: true, opacity: 0.7,
        sizeAttenuation: true, blending: THREE.AdditiveBlending
    });
    const starVertices = [];
    for (let i = 0; i < 3000; i++) {
        const x = THREE.MathUtils.randFloatSpread(500);
        const y = THREE.MathUtils.randFloatSpread(500);
        const z = THREE.MathUtils.randFloatSpread(500);
        starVertices.push(x, y, z);
    }
    starGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starVertices, 3));
    state.threeStarField = new THREE.Points(starGeometry, starMaterial);
    state.threeJsScene.add(state.threeStarField);

    state.threeJsScene.add(state.threeBlackHoleGroup);
    state.threeJsInitialized = true;
    animateThreeBlackHole();
    console.log("Three.js black hole initialized successfully.");
}

/**
 * Animation loop for the Three.js black hole.
 */
export function animateThreeBlackHole() {
    if (!state.threeJsInitialized || !state.isIdtComponentVisible) {
        if (state.threeJsAnimationId) cancelAnimationFrame(state.threeJsAnimationId);
        state.threeJsAnimationId = null;
        return;
    }
    state.threeJsAnimationId = requestAnimationFrame(animateThreeBlackHole);

    if (state.threeBlackHoleGroup) {
        state.threeBlackHoleGroup.rotation.y += 0.0015;
        state.threeBlackHoleGroup.rotation.x += 0.0007;
    }
    if (state.threeAccretionDiskOuter) state.threeAccretionDiskOuter.rotation.z += state.threeAccretionDiskOuter.userData.rotationSpeed;
    if (state.threeAccretionDiskMiddle) state.threeAccretionDiskMiddle.rotation.z += state.threeAccretionDiskMiddle.userData.rotationSpeed;
    if (state.threeAccretionDiskInner) state.threeAccretionDiskInner.rotation.z += state.threeAccretionDiskInner.userData.rotationSpeed;
    if (state.threeStarField) {
        state.threeStarField.rotation.x += 0.0001;
        state.threeStarField.rotation.y += 0.00015;
    }

    if (state.threeJsRenderer && state.threeJsScene && state.threeJsCamera) {
        state.threeJsRenderer.render(state.threeJsScene, state.threeJsCamera);
    }
}

/**
 * Toggles the visibility of the Three.js scene and animation.
 * @param {boolean} isVisible - True to show, false to hide.
 */
export function toggleThreeBlackHoleVisibility(isVisible) {
    if (!dom.idtComponentWrapper) return;
    dom.idtComponentWrapper.classList.toggle('is-visible', isVisible);
    state.isIdtComponentVisible = isVisible; // Update state

    if (isVisible) {
        if (!state.threeJsInitialized) {
            initThreeBlackHole(dom.idtComponentWrapper);
        } else if (!state.threeJsAnimationId) { // Already initialized, but animation might be stopped
            animateThreeBlackHole();
        }
    } else { // Hiding
        if (state.threeJsAnimationId) {
            cancelAnimationFrame(state.threeJsAnimationId);
            state.threeJsAnimationId = null;
        }
    }
    // Persisting isIdtComponentVisible is handled by settings_handler or event_listener_setup
}


/**
 * Handles mousedown on the 3D component for dragging.
 * @param {MouseEvent} e
 */
export function handleComponentMouseDown(e) {
    if (!dom.idtComponentWrapper.classList.contains('is-visible') || e.button !== 0) { return; }
    state.isDraggingComponent = true;
    dom.idtComponentWrapper.style.cursor = 'grabbing';
    document.body.style.userSelect = 'none';

    const styles = getComputedStyle(document.documentElement);
    const currentTopPercent = parseFloat(styles.getPropertyValue('--idt-offset-top-percentage').replace('%','')) || 0;
    const currentLeftPercent = parseFloat(styles.getPropertyValue('--idt-offset-left-percentage').replace('%','')) || 0;

    state.componentInitialTopPx = (dom.idtComponentWrapper.style.top && dom.idtComponentWrapper.style.top.endsWith('px'))
        ? parseFloat(dom.idtComponentWrapper.style.top)
        : (currentTopPercent / 100) * window.innerHeight;
    state.componentInitialLeftPx = (dom.idtComponentWrapper.style.left && dom.idtComponentWrapper.style.left.endsWith('px'))
        ? parseFloat(dom.idtComponentWrapper.style.left)
        : (currentLeftPercent / 100) * window.innerWidth;

    state.componentDragStartX = e.clientX;
    state.componentDragStartY = e.clientY;

    document.addEventListener('mousemove', handleComponentMouseMove);
    document.addEventListener('mouseup', handleComponentMouseUp);
    document.addEventListener('mouseleave', handleComponentMouseUp); // If mouse leaves window
    e.preventDefault();
}

/**
 * Handles mousemove during 3D component dragging.
 * @param {MouseEvent} e
 */
export function handleComponentMouseMove(e) {
    if (!state.isDraggingComponent) return;
    const deltaX = e.clientX - state.componentDragStartX;
    const deltaY = e.clientY - state.componentDragStartY;

    let newTopPx = state.componentInitialTopPx + deltaY;
    let newLeftPx = state.componentInitialLeftPx + deltaX;

    const componentRect = dom.idtComponentWrapper.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    newTopPx = Math.max(0, Math.min(newTopPx, viewportHeight - componentRect.height));
    newLeftPx = Math.max(0, Math.min(newLeftPx, viewportWidth - componentRect.width));

    dom.idtComponentWrapper.style.top = `${newTopPx}px`;
    dom.idtComponentWrapper.style.left = `${newLeftPx}px`;
}

/**
 * Handles mouseup to end 3D component dragging.
 */
export function handleComponentMouseUp() {
    if (!state.isDraggingComponent) return;
    state.isDraggingComponent = false;
    dom.idtComponentWrapper.style.cursor = 'grab';
    document.body.style.userSelect = '';
    document.removeEventListener('mousemove', handleComponentMouseMove);
    document.removeEventListener('mouseup', handleComponentMouseUp);
    document.removeEventListener('mouseleave', handleComponentMouseUp);

    // Convert final pixel position to percentage and store
    const finalTopPx = parseFloat(dom.idtComponentWrapper.style.top) || 0;
    const finalLeftPx = parseFloat(dom.idtComponentWrapper.style.left) || 0;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    const componentWidthPercent = (dom.idtComponentWrapper.offsetWidth / viewportWidth) * 100;
    const componentHeightPercent = (dom.idtComponentWrapper.offsetHeight / viewportHeight) * 100;

    let newTopPercent = (finalTopPx / viewportHeight) * 100;
    let newLeftPercent = (finalLeftPx / viewportWidth) * 100;

    // Re-clamp percentages
    newTopPercent = Math.max(0, Math.min(newTopPercent, 100 - componentHeightPercent));
    newLeftPercent = Math.max(0, Math.min(newLeftPercent, 100 - componentWidthPercent));

    document.documentElement.style.setProperty('--idt-offset-top-percentage', `${newTopPercent.toFixed(2)}%`);
    document.documentElement.style.setProperty('--idt-offset-left-percentage', `${newLeftPercent.toFixed(2)}%`);

    // Clear inline styles so CSS vars take over
    dom.idtComponentWrapper.style.top = '';
    dom.idtComponentWrapper.style.left = '';

    localStorage.setItem(APP_PREFIX + 'idtComponentTopPercent', `${newTopPercent.toFixed(2)}%`);
    localStorage.setItem(APP_PREFIX + 'idtComponentLeftPercent', `${newLeftPercent.toFixed(2)}%`);
}


// ==========================================================================
// [ END OF FILE modules/three_visuals.js ]
// ==========================================================================