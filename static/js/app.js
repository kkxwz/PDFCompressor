/**
 * PDF Compressor - 前端交互逻辑
 */
(function() {
    'use strict';

    // ========== 主题换肤 ==========
    const THEME_KEY = 'pdf-compressor-theme';
    const themeToggle = document.getElementById('themeToggle');

    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function applyTheme(theme) {
        const effective = theme === 'system' ? getSystemTheme() : theme;
        document.documentElement.setAttribute('data-theme', effective);

        // Update active button
        themeToggle.querySelectorAll('.theme-toggle-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.themeValue === theme);
        });

        // Save preference
        localStorage.setItem(THEME_KEY, theme);
    }

    // Init theme
    const savedTheme = localStorage.getItem(THEME_KEY) || 'system';
    applyTheme(savedTheme);

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const current = localStorage.getItem(THEME_KEY) || 'system';
        if (current === 'system') applyTheme('system');
    });

    // Theme toggle click
    themeToggle.addEventListener('click', (e) => {
        const btn = e.target.closest('.theme-toggle-btn');
        if (!btn) return;
        applyTheme(btn.dataset.themeValue);
    });

    // DOM 元素
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const btnRemove = document.getElementById('btnRemove');
    const optionsSection = document.getElementById('optionsSection');
    const btnCompress = document.getElementById('btnCompress');
    const progressSection = document.getElementById('progressSection');
    const progressFill = document.getElementById('progressFill');
    const progressPercent = document.getElementById('progressPercent');
    const progressRing = document.getElementById('progressRing');
    const progressMessage = document.getElementById('progressMessage');
    const progressTitle = document.getElementById('progressTitle');
    const resultSection = document.getElementById('resultSection');
    const originalSizeEl = document.getElementById('originalSize');
    const compressedSizeEl = document.getElementById('compressedSize');
    const compressionRatioEl = document.getElementById('compressionRatio');
    const resultWarning = document.getElementById('resultWarning');
    const warningText = document.getElementById('warningText');
    const btnDownload = document.getElementById('btnDownload');
    const btnRestart = document.getElementById('btnRestart');
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');
    const btnRetry = document.getElementById('btnRetry');

    // 所有可切换区域
    const allSections = [optionsSection, progressSection, resultSection, errorSection];

    // 状态
    let currentFile = null;
    let currentFileId = null;

    // 圆环进度参数
    const RING_RADIUS = 52;
    const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

    // ========== 工具函数 ==========

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    }

    function showSection(section) {
        allSections.forEach(s => { s.style.display = 'none'; });
        if (section) {
            section.style.display = 'block';
        }
    }

    function showError(message) {
        showSection(errorSection);
        errorMessage.textContent = message;
        updateSteps(3, 'error');
    }

    function updateSteps(activeStep, state) {
        const steps = document.querySelectorAll('.step');
        steps.forEach((step, i) => {
            const stepNum = i + 1;
            step.classList.remove('active', 'done');
            if (stepNum < activeStep) {
                step.classList.add('done');
            } else if (stepNum === activeStep) {
                step.classList.add('active');
            }
        });
    }

    function setRingProgress(percent) {
        const offset = RING_CIRCUMFERENCE - (percent / 100) * RING_CIRCUMFERENCE;
        progressRing.style.strokeDashoffset = offset;
    }

    // ========== 拖拽上传 ==========

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFile(files[0]);
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFile(e.target.files[0]);
    });

    // ========== 文件处理 ==========

    function handleFile(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showError('仅支持 PDF 格式文件，请选择 .pdf 文件');
            return;
        }

        const maxSize = 100 * 1024 * 1024;
        if (file.size > maxSize) {
            showError(`文件过大（${formatSize(file.size)}），最大支持 100MB`);
            return;
        }

        currentFile = file;
        uploadFile(file);
    }

    async function uploadFile(file) {
        dropZone.style.display = 'none';
        fileInfo.style.display = 'flex';
        fileName.textContent = file.name;
        fileSize.textContent = formatSize(file.size);
        btnCompress.disabled = true;
        btnCompress.innerHTML = '<span>上传中...</span>';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || '上传失败');
            }

            currentFileId = data.file_id;
            fileName.textContent = data.filename;
            fileSize.textContent = data.size_human;

            showSection(optionsSection);
            updateSteps(2);
            btnCompress.disabled = false;
            btnCompress.innerHTML = `
                <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M3 10l4 4L17 4" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>开始压缩</span>
                <div class="btn-shimmer"></div>
            `;

        } catch (error) {
            console.error('上传失败:', error);
            showError(error.message || '文件上传失败，请重试');
            resetUpload();
        }
    }

    function resetUpload() {
        currentFile = null;
        currentFileId = null;
        fileInput.value = '';
        dropZone.style.display = 'block';
        fileInfo.style.display = 'none';
        showSection(null);
        updateSteps(1);
    }

    // ========== 移除文件 ==========
    btnRemove.addEventListener('click', (e) => {
        e.stopPropagation();
        resetUpload();
    });

    // ========== 开始压缩 ==========
    btnCompress.addEventListener('click', startCompression);

    async function startCompression() {
        if (!currentFileId) {
            showError('请先上传文件');
            return;
        }

        const level = document.querySelector('input[name="quality"]:checked').value;

        showSection(progressSection);
        progressFill.style.width = '0%';
        progressPercent.textContent = '0';
        setRingProgress(0);
        progressMessage.textContent = '正在启动压缩引擎...';
        progressTitle.textContent = '正在压缩...';

        try {
            const response = await fetch('/api/compress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_id: currentFileId,
                    level: level
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || '启动压缩失败');
            }

            listenProgress(data.task_id);

        } catch (error) {
            console.error('启动压缩失败:', error);
            showError(error.message || '启动压缩失败，请重试');
        }
    }

    // ========== 进度监听 ==========

    function listenProgress(taskId) {
        const eventSource = new EventSource(`/api/progress/${taskId}`);

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const progress = data.progress || 0;

            progressFill.style.width = `${progress}%`;
            progressPercent.textContent = progress;
            setRingProgress(progress);
            progressMessage.textContent = data.message || '处理中...';

            if (data.stage === 'done') {
                eventSource.close();
                updateSteps(3, 'done');
                showResult(data.result);
            } else if (data.stage === 'error') {
                eventSource.close();
                showError(data.error || '压缩失败');
            }
        };

        eventSource.onerror = () => {
            eventSource.close();
            setTimeout(() => {
                fetch(`/api/progress/${taskId}`)
                    .then(res => {
                        if (res.ok) listenProgress(taskId);
                    })
                    .catch(() => {
                        showError('连接中断，请刷新页面重试');
                    });
            }, 1000);
        };
    }

    // ========== 显示结果 ==========

    function showResult(result) {
        showSection(resultSection);

        originalSizeEl.textContent = formatSize(result.original_size);
        compressedSizeEl.textContent = formatSize(result.compressed_size);
        compressionRatioEl.textContent = result.ratio + '%';

        btnDownload.href = result.download_url;

        if (result.warning) {
            resultWarning.style.display = 'flex';
            warningText.textContent = result.warning;
        } else {
            resultWarning.style.display = 'none';
        }
    }

    // ========== 重新开始 ==========
    btnRestart.addEventListener('click', resetUpload);
    btnRetry.addEventListener('click', resetUpload);

    // ========== 初始化 ==========
    updateSteps(1);

    fetch('/api/health')
        .then(res => res.json())
        .then(data => {
            if (!data.ghostscript.available) {
                showError('Ghostscript 未安装，压缩功能不可用。请先安装 Ghostscript。');
            }
        })
        .catch(() => {});

})();
