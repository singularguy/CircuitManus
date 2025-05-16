// /static/idtComponent.js

// 尝试从CDN或本地路径导入Three.js。
// 如果你的项目有构建步骤（如Webpack/Rollup），你可以使用:
// import * as THREE from 'three';
// 否则，依赖于在index.html中全局引入的THREE对象
let THREE_Instance;
if (typeof THREE !== 'undefined') {
    THREE_Instance = THREE;
} else {
    // 尝试从CDN动态加载（这是一个后备方案，最好还是在HTML中显式引入或使用构建工具）
    // 为了简单起见，我们假设THREE已经在全局可用
    console.error("THREE.js library is not loaded. Please ensure it's included in your HTML or build process.");
    // 你可以在这里抛出错误或者尝试动态加载脚本
}


class IdtComponentManager {
    constructor(containerElement) {
        if (!THREE_Instance) {
            console.error("IdtComponentManager: THREE.js instance not available.");
            return;
        }
        if (!containerElement) {
            console.error("IdtComponentManager: Container element is required.");
            return;
        }

        this.container = containerElement;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.animationId = null;
        this.isInitialized = false;
        this.isVisible = false; // 组件初始不可见，由外部控制

        // 用于存储黑洞特效的各个部分
        this.blackHoleGroup = null;
        this.accretionDiskOuter = null;
        this.accretionDiskMiddle = null;
        this.accretionDiskInner = null;
        this.starField = null;

        console.log("IdtComponentManager instantiated.");
    }

    _initializeThree() {
        if (this.isInitialized) return;

        this.scene = new THREE_Instance.Scene();
        this.camera = new THREE_Instance.PerspectiveCamera(75, this.container.clientWidth / this.container.clientHeight, 0.1, 2000);
        this.camera.position.z = 60;

        this.renderer = new THREE_Instance.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);

        this.container.innerHTML = ''; // 清空容器
        this.container.appendChild(this.renderer.domElement);

        this._setupSceneObjects(); // 创建3D对象

        this.isInitialized = true;
        console.log("IdtComponentManager: Three.js initialized and scene objects created.");
    }

    _setupSceneObjects() {
        // 1. 光照
        const ambientLight = new THREE_Instance.AmbientLight(0xaaaaaa, 0.5);
        this.scene.add(ambientLight);
        const pointLight = new THREE_Instance.PointLight(0xffffff, 1, 500);
        pointLight.position.set(0, 20, 30);
        this.scene.add(pointLight);

        // 2. 创建黑洞对象组
        this.blackHoleGroup = new THREE_Instance.Group();

        // 事件视界 (3D球体)
        const sphereRadius = 12;
        const sphereGeometry = new THREE_Instance.SphereGeometry(sphereRadius, 48, 48);
        const sphereMaterial = new THREE_Instance.MeshStandardMaterial({
            color: 0x000000,
            roughness: 0.8,
            metalness: 0.1
        });
        const eventHorizon = new THREE_Instance.Mesh(sphereGeometry, sphereMaterial);
        this.blackHoleGroup.add(eventHorizon);

        // 吸积盘 (用多个TorusGeometry模拟)
        const diskColors = [0xff6600, 0xff9933, 0xffcc66];
        const diskOpacities = [0.6, 0.7, 0.8];
        const diskRadii = [sphereRadius + 7, sphereRadius + 14, sphereRadius + 21];
        const diskTubeRadii = [2.5, 3.5, 4.5];
        const diskRotationSpeeds = [0.01, -0.008, 0.012]; // 为每个盘片存储旋转速度

        const disks = diskRadii.map((radius, i) => {
            const diskMaterial = new THREE_Instance.MeshPhongMaterial({
                color: diskColors[i],
                emissive: new THREE_Instance.Color(diskColors[i]).multiplyScalar(0.5),
                specular: 0x333333,
                shininess: 20,
                side: THREE_Instance.DoubleSide,
                transparent: true,
                opacity: diskOpacities[i],
                blending: THREE_Instance.AdditiveBlending
            });
            const disk = new THREE_Instance.Mesh(new THREE_Instance.TorusGeometry(radius, diskTubeRadii[i], 16, 60), diskMaterial);
            disk.rotation.x = Math.PI / 1.8; // 调整倾斜角度
            disk.userData.rotationSpeed = diskRotationSpeeds[i]; // 将旋转速度存到userData
            this.blackHoleGroup.add(disk);
            return disk;
        });
        this.accretionDiskOuter = disks[0];
        this.accretionDiskMiddle = disks[1];
        this.accretionDiskInner = disks[2];

        this.scene.add(this.blackHoleGroup);

        // 背景星场 (粒子系统)
        const starGeometry = new THREE_Instance.BufferGeometry();
        const starMaterial = new THREE_Instance.PointsMaterial({
            color: 0xffffff,
            size: 0.25,
            transparent: true,
            opacity: 0.7,
            sizeAttenuation: true,
            blending: THREE_Instance.AdditiveBlending
        });
        const starVertices = [];
        for (let i = 0; i < 3000; i++) {
            const x = THREE_Instance.MathUtils.randFloatSpread(500);
            const y = THREE_Instance.MathUtils.randFloatSpread(500);
            const z = THREE_Instance.MathUtils.randFloatSpread(500);
            starVertices.push(x, y, z);
        }
        starGeometry.setAttribute('position', new THREE_Instance.Float32BufferAttribute(starVertices, 3));
        this.starField = new THREE_Instance.Points(starGeometry, starMaterial);
        this.scene.add(this.starField); // 星场直接添加到主场景，不随黑洞组旋转
    }

    _animate() {
        if (!this.isVisible || !this.renderer) { // 如果不可见或未初始化渲染器，则停止动画
            if (this.animationId) {
                cancelAnimationFrame(this.animationId);
                this.animationId = null;
            }
            return;
        }

        this.animationId = requestAnimationFrame(() => this._animate()); // 递归调用以形成循环

        // 更新黑洞组的旋转
        if (this.blackHoleGroup) {
            this.blackHoleGroup.rotation.y += 0.0015;
            this.blackHoleGroup.rotation.x += 0.0007;
        }

        // 更新吸积盘的旋转
        if (this.accretionDiskOuter) this.accretionDiskOuter.rotation.z += this.accretionDiskOuter.userData.rotationSpeed;
        if (this.accretionDiskMiddle) this.accretionDiskMiddle.rotation.z += this.accretionDiskMiddle.userData.rotationSpeed;
        if (this.accretionDiskInner) this.accretionDiskInner.rotation.z += this.accretionDiskInner.userData.rotationSpeed;
        
        // 更新星场的旋转
        if (this.starField) {
            this.starField.rotation.x += 0.0001;
            this.starField.rotation.y += 0.00015;
        }

        // 渲染场景
        this.renderer.render(this.scene, this.camera);
    }

    setVisible(isVisible) {
        this.isVisible = isVisible;
        if (this.container) { // 确保容器存在
            this.container.classList.toggle('is-visible', isVisible);
        }

        if (isVisible) {
            if (!this.isInitialized) {
                this._initializeThree(); // 首次可见时初始化
            }
            if (!this.animationId) { // 如果动画未运行，则启动
                this._animate();
            }
        } else {
            if (this.animationId) { // 如果隐藏，则停止动画
                cancelAnimationFrame(this.animationId);
                this.animationId = null;
            }
        }
        console.log(`IdtComponentManager: Visibility set to ${isVisible}`);
    }

    updateSize(width, height) {
        if (!this.isInitialized) return;

        if (this.camera) {
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
        }
        if (this.renderer) {
            this.renderer.setSize(width, height);
        }
        console.log(`IdtComponentManager: Size updated to ${width}x${height}`);
    }

    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        // 清理Three.js资源 (非常重要)
        if (this.scene) {
            this.scene.traverse(object => {
                if (object.geometry) object.geometry.dispose();
                if (object.material) {
                    if (Array.isArray(object.material)) {
                        object.material.forEach(material => material.dispose());
                    } else {
                        object.material.dispose();
                    }
                }
            });
            this.scene = null;
        }
        if (this.renderer) {
            this.renderer.dispose();
            // 从DOM中移除canvas
            if (this.renderer.domElement && this.renderer.domElement.parentElement) {
                this.renderer.domElement.parentElement.removeChild(this.renderer.domElement);
            }
            this.renderer = null;
        }
        this.camera = null;
        this.isInitialized = false;
        console.log("IdtComponentManager: Disposed.");
    }
}

// 导出类，以便在 script.js 中使用
// 如果你的环境不支持 ES Modules, 你可能需要将这个类附加到 window 对象上
// 例如: window.IdtComponentManager = IdtComponentManager;
// 并在 script.js 中通过 window.IdtComponentManager 访问
export { IdtComponentManager };