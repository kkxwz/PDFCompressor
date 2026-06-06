/**
 * SlimPDF - Frontend Interaction Logic
 */
(function() {
    'use strict';

    // ========== Theme Switching ==========
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

    // DOM Elements
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

    // All switchable sections
    const allSections = [optionsSection, progressSection, resultSection, errorSection];

    // State
    let currentFile = null;
    let currentFileId = null;

    // Ring progress params
    const RING_RADIUS = 52;
    const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

    // ========== Utility Functions ==========

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

    // ========== Drag & Drop Upload ==========

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

    // ========== File Handling ==========

    function handleFile(file) {
        // Check MIME type first, then fallback to extension
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            showError('Only PDF format files are supported. Please select a .pdf file.');
            return;
        }

        const maxSize = 100 * 1024 * 1024;
        if (file.size > maxSize) {
            showError(`File too large (${formatSize(file.size)}), max supported 100MB`);
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
        btnCompress.innerHTML = '<span>Uploading...</span>';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || 'Upload failed');
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
                <span>Start Compression</span>
                <div class="btn-shimmer"></div>
            `;

        } catch (error) {
            console.error('Upload failed:', error);
            showError(error.message || 'File upload failed, please try again');
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

    // ========== Remove File ==========
    btnRemove.addEventListener('click', (e) => {
        e.stopPropagation();
        resetUpload();
    });

    // ========== Start Compression ==========
    btnCompress.addEventListener('click', startCompression);

    async function startCompression() {
        if (!currentFileId) {
            showError('Please upload a file first');
            return;
        }

        const level = document.querySelector('input[name="quality"]:checked').value;

        showSection(progressSection);
        progressFill.style.width = '0%';
        progressPercent.textContent = '0';
        setRingProgress(0);
        progressMessage.textContent = 'Starting compression engine...';
        progressTitle.textContent = 'Compressing...';

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
                throw new Error(data.message || 'Failed to start compression');
            }

            listenProgress(data.task_id);

        } catch (error) {
            console.error('Failed to start compression:', error);
            showError(error.message || 'Failed to start compression, please try again');
        }
    }

    // ========== Progress Listener ==========

    function listenProgress(taskId) {
        const eventSource = new EventSource(`/api/progress/${taskId}`);

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const progress = data.progress || 0;

            progressFill.style.width = `${progress}%`;
            progressPercent.textContent = progress;
            setRingProgress(progress);
            progressMessage.textContent = data.message || 'Processing...';

            if (data.stage === 'done') {
                eventSource.close();
                updateSteps(3, 'done');
                showResult(data.result);
            } else if (data.stage === 'error') {
                eventSource.close();
                showError(data.error || 'Compression failed');
            }
        };

        eventSource.onerror = () => {
            eventSource.close();
            // SSE connection lost, try to check task status via REST API
            setTimeout(() => {
                fetch(`/api/health`)
                    .then(() => {
                        // Server is alive, task may have completed while reconnecting
                        // Try to fetch task result directly
                        fetch(`/api/download/${taskId}`, { method: 'HEAD' })
                            .then(res => {
                                if (res.ok || res.status === 200) {
                                    // Task completed, redirect to download
                                    window.location.href = `/api/download/${taskId}`;
                                } else {
                                    // Task still processing or failed, retry SSE
                                    listenProgress(taskId);
                                }
                            })
                            .catch(() => {
                                showError('Connection interrupted. Please refresh the page and try again.');
                            });
                    })
                    .catch(() => {
                        showError('Server unreachable. Please check if the application is running.');
                    });
            }, 1000);
        };
    }

    // ========== Show Result ==========

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

    // ========== Restart ==========
    btnRestart.addEventListener('click', resetUpload);
    btnRetry.addEventListener('click', resetUpload);

    // ========== Initialization ==========
    updateSteps(1);

    fetch('/api/health')
        .then(res => res.json())
        .then(data => {
            if (!data.ghostscript.available) {
                showError('Ghostscript not installed. Compression is unavailable. Please install Ghostscript first.');
            }
        })
        .catch(() => {});

})();
