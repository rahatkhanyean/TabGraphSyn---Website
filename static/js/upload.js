/**
 * TabGraphSyn Upload/Journey Page JavaScript
 * Handles file uploads, metadata management, and pipeline execution
 */

(function () {
    'use strict';

    // ========================================================================
    // Utility Functions
    // ========================================================================

    /**
     * Get CSRF token from cookies
     */
    const getCookie = (name) => {
        const value = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
        return value ? decodeURIComponent(value[1]) : null;
    };

    /**
     * Convert array-like objects to actual arrays
     */
    const toArray = (collection) => {
        if (!collection) return [];
        if (Array.isArray(collection)) return collection;
        try {
            return Array.prototype.slice.call(collection);
        } catch (error) {
            const result = [];
            const length = collection && collection.length ? collection.length : 0;
            for (let index = 0; index < length; index += 1) {
                result.push(collection[index]);
            }
            return result;
        }
    };

    /**
     * Get first checked radio button from collection
     */
    const firstChecked = (collection) => {
        const items = toArray(collection);
        for (let index = 0; index < items.length; index += 1) {
            const item = items[index];
            if (item && item.checked) {
                return item;
            }
        }
        return null;
    };

    /**
     * Show loading state
     */
    const showLoading = (message = 'Processing...') => {
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay active';
        overlay.id = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner" style="margin: 0 auto 16px;"></div>
                <p style="margin: 0; color: var(--text-primary); font-weight: 600;">${message}</p>
            </div>
        `;
        document.body.appendChild(overlay);
    };

    /**
     * Hide loading state
     */
    const hideLoading = () => {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('active');
            setTimeout(() => overlay.remove(), 300);
        }
    };

    // ========================================================================
    // DOM Element References
    // ========================================================================

    const elements = {
        // Form elements
        datasetSelect: document.getElementById('id_dataset'),
        metadataTemplateField: document.getElementById('id_metadata_template'),
        dataSourceRadios: document.querySelectorAll('input[name="data_source"]'),
        metadataModeRadios: document.querySelectorAll('input[name="metadata_mode"]'),
        stagingTokenInput: document.getElementById('id_staging_token'),
        fileInput: document.getElementById('dataset-file'),
        datasetNameInput: document.getElementById('id_uploaded_dataset_name'),
        tableNameInput: document.getElementById('id_uploaded_table_name'),
        formElement: document.querySelector('form'),

        // UI components
        uploadSummary: document.getElementById('upload-summary'),
        metadataChoice: document.getElementById('metadata-choice'),
        metadataStep: document.getElementById('metadata-step'),
        metadataTemplatePanel: document.getElementById('metadata-template-panel'),
        metadataCustomPanel: document.getElementById('metadata-custom-panel'),
        templateSelect: document.getElementById('template-select'),
        finalizeButton: document.getElementById('finalize-metadata-button'),
        finalizeStatus: document.getElementById('finalize-status'),
        metadataReminder: document.getElementById('metadata-reminder'),
        columnTableBody: document.querySelector('#column-summary tbody'),
        runButton: document.getElementById('run-button'),

        // Status panel elements
        statusPanel: document.getElementById('run-status-panel'),
        statusStageEl: document.getElementById('run-status-stage'),
        statusMessageEl: document.getElementById('run-status-message'),
        statusLogsEl: document.getElementById('run-status-logs'),
        statusActions: document.getElementById('run-status-actions'),
        statusResultLink: document.getElementById('run-status-open-result'),
        statusPlaceholder: document.getElementById('status-placeholder'),

        // Preview elements
        commandPreview: document.getElementById('command-preview'),
        preloadedSection: document.getElementById('preloaded-options'),
        uploadSection: document.getElementById('upload-options'),
        trainingSection: document.getElementById('training-section'),
        commandSection: document.getElementById('command-preview-section'),
    };

    // ========================================================================
    // Application State
    // ========================================================================

    const state = {
        stagedUpload: null,
        metadataReady: false,
        customMetadataDirty: false,
        currentTable: null,
        activeJobToken: null,
        jobStatusTimer: null,
        jobIsRunning: false,
        pendingResultUrl: null,
    };

    // ========================================================================
    // Configuration
    // ========================================================================

    const config = {
        csrfToken: getCookie('csrftoken'),
        tableMap: {},
        defaults: {},
        apiUrls: {},
        runButtonDefaultLabel: 'Run pipeline',
        columnKinds: ['categorical', 'numerical', 'datetime', 'boolean', 'id'],
        representationOptions: ['Int64', 'Float'],
    };

    // Initialize configuration from embedded JSON
    try {
        const tableMapEl = document.getElementById('dataset-table-map');
        const defaultsEl = document.getElementById('pipeline-defaults');
        const apiUrlsEl = document.getElementById('synthetic-api-urls');

        if (tableMapEl) config.tableMap = JSON.parse(tableMapEl.textContent);
        if (defaultsEl) config.defaults = JSON.parse(defaultsEl.textContent);
        if (apiUrlsEl) config.apiUrls = JSON.parse(apiUrlsEl.textContent);
        if (elements.runButton) {
            config.runButtonDefaultLabel = elements.runButton.textContent.trim() || 'Run pipeline';
        }
    } catch (error) {
        console.error('Failed to load configuration:', error);
    }

    // ========================================================================
    // Getter Functions
    // ========================================================================

    const getSelectedDataSource = () => {
        const checked = firstChecked(elements.dataSourceRadios);
        return checked ? checked.value : 'preloaded';
    };

    const getSelectedMetadataMode = () => {
        const checked = firstChecked(elements.metadataModeRadios);
        return checked ? checked.value : null;
    };

    const statusUrlFor = (token) => config.apiUrls.status.replace('JOB_TOKEN', token);
    const resultUrlFor = (token) => config.apiUrls.result.replace('RUN_TOKEN', token);

    // ========================================================================
    // UI Helper Functions
    // ========================================================================

    const toggleVisibility = (element, shouldShow) => {
        if (!element) return;

        element.hidden = !shouldShow;
        if (shouldShow) {
            element.style.removeProperty('display');
        } else {
            element.style.display = 'none';
        }

        // Special handling for metadata choice
        if (element === elements.metadataChoice && elements.metadataStep) {
            elements.metadataStep.hidden = !shouldShow;
        }
    };

    const toggleStatusPlaceholder = () => {
        if (!elements.statusPanel || !elements.statusPlaceholder) return;
        elements.statusPlaceholder.hidden = !elements.statusPanel.hidden;
    };

    const showUploadSummary = (text, isError = false) => {
        if (!elements.uploadSummary) return;
        elements.uploadSummary.textContent = text;
        elements.uploadSummary.hidden = false;
        elements.uploadSummary.style.color = isError ? '#c53' : '';
    };

    const showAdvanced = () => {
        // Can be used to show additional advanced options
    };

    const hideAdvanced = () => {
        // Can be used to hide additional advanced options
    };

    // ========================================================================
    // Status Panel Functions
    // ========================================================================

    const resetStatusPanel = () => {
        if (!elements.statusPanel) return;

        state.pendingResultUrl = null;
        elements.statusPanel.hidden = true;
        elements.statusPanel.classList.remove('is-error');
        toggleStatusPlaceholder();

        if (elements.statusStageEl) elements.statusStageEl.textContent = 'Queued';
        if (elements.statusMessageEl) elements.statusMessageEl.textContent = '';
        if (elements.statusLogsEl) elements.statusLogsEl.textContent = '';
        if (elements.statusActions) elements.statusActions.hidden = true;
        if (elements.statusResultLink) {
            elements.statusResultLink.removeAttribute('href');
            elements.statusResultLink.textContent = 'View results';
        }
    };

    const updateStatusPanel = (data) => {
        if (!elements.statusPanel) return;

        elements.statusPanel.hidden = false;
        toggleStatusPlaceholder();
        elements.statusPanel.classList.remove('is-error');

        if (elements.statusActions) elements.statusActions.hidden = true;
        if (elements.statusResultLink) elements.statusResultLink.removeAttribute('href');

        if (elements.statusStageEl) {
            const stage = (data && data.stage)
                ? data.stage.replace(/_/g, ' ').replace(/^(.)/, (match) => match.toUpperCase())
                : 'Running';
            elements.statusStageEl.textContent = stage;
        }

        if (elements.statusMessageEl) {
            elements.statusMessageEl.textContent = (data && data.message) ? data.message : 'Processing...';
        }

        if (elements.statusLogsEl && data && data.log) {
            elements.statusLogsEl.textContent = data.log;
            // Auto-scroll to bottom
            elements.statusLogsEl.scrollTop = elements.statusLogsEl.scrollHeight;
        }
    };

    const handleJobCompletion = (resultToken) => {
        stopStatusPoll();
        state.jobIsRunning = false;
        updateRunButton();
        state.activeJobToken = null;

        if (elements.statusPanel) {
            elements.statusPanel.hidden = false;
            elements.statusPanel.classList.remove('is-error');
        }
        toggleStatusPlaceholder();

        const url = resultUrlFor(resultToken);
        state.pendingResultUrl = url;

        if (elements.statusStageEl) elements.statusStageEl.textContent = 'Completed';
        if (elements.statusMessageEl) elements.statusMessageEl.textContent = 'Pipeline completed successfully! Redirecting...';
        if (elements.statusActions) elements.statusActions.hidden = false;
        if (elements.statusResultLink) {
            elements.statusResultLink.href = url;
            elements.statusResultLink.textContent = 'View results';
        }

        // Auto-redirect after delay
        window.setTimeout(() => {
            if (state.pendingResultUrl) {
                window.location.href = state.pendingResultUrl;
            }
        }, 1500);
    };

    const handleJobFailure = (message) => {
        stopStatusPoll();
        state.jobIsRunning = false;
        updateRunButton();
        state.activeJobToken = null;
        state.pendingResultUrl = null;

        if (elements.statusPanel) {
            elements.statusPanel.hidden = false;
            elements.statusPanel.classList.add('is-error');
        }
        toggleStatusPlaceholder();

        if (elements.statusStageEl) elements.statusStageEl.textContent = 'Failed';
        if (elements.statusMessageEl) elements.statusMessageEl.textContent = message || 'Pipeline run failed.';
        if (elements.statusActions) elements.statusActions.hidden = true;
        if (elements.statusResultLink) elements.statusResultLink.removeAttribute('href');
    };

    // ========================================================================
    // Job Status Polling
    // ========================================================================

    const stopStatusPoll = () => {
        if (state.jobStatusTimer) {
            window.clearTimeout(state.jobStatusTimer);
            state.jobStatusTimer = null;
        }
    };

    const scheduleStatusPoll = (delay = 1000) => {
        stopStatusPoll();
        state.jobStatusTimer = window.setTimeout(fetchJobStatus, delay);
    };

    const fetchJobStatus = () => {
        if (!state.activeJobToken) return;

        fetch(statusUrlFor(state.activeJobToken), {
            headers: { 'Cache-Control': 'no-store' }
        })
            .then((response) => response.json().then((payload) => ({ ok: response.ok, payload })))
            .then(({ ok, payload }) => {
                if (!ok) throw payload;

                updateStatusPanel(payload);

                if (payload.stage === 'completed' && payload.resultToken) {
                    handleJobCompletion(payload.resultToken);
                } else if (payload.stage === 'failed') {
                    handleJobFailure(payload.error || 'Pipeline run failed.');
                } else {
                    scheduleStatusPoll(1000);
                }
            })
            .catch((error) => {
                console.error('Status polling error', error);
                if (state.activeJobToken) {
                    scheduleStatusPoll(2000);
                }
            });
    };

    // ========================================================================
    // Pipeline Execution
    // ========================================================================

    const startPipelineRun = () => {
        if (state.jobIsRunning) return;
        if (!elements.formElement) return;

        const dataSource = getSelectedDataSource();
        if (dataSource === 'uploaded' && (!state.stagedUpload || !state.metadataReady)) {
            return;
        }

        state.jobIsRunning = true;
        state.activeJobToken = null;
        state.pendingResultUrl = null;
        stopStatusPoll();
        resetStatusPanel();

        if (elements.statusPanel) elements.statusPanel.hidden = false;
        toggleStatusPlaceholder();
        if (elements.statusMessageEl) elements.statusMessageEl.textContent = 'Submitting job...';
        if (elements.statusStageEl) elements.statusStageEl.textContent = 'Queued';
        if (elements.statusLogsEl) elements.statusLogsEl.textContent = '';

        updateRunButton();
        showLoading('Starting pipeline...');

        const formData = new FormData(elements.formElement);

        fetch(config.apiUrls.start, {
            method: 'POST',
            headers: {
                'X-CSRFToken': config.csrfToken || '',
            },
            body: formData,
        })
            .then((response) => response.json().then((payload) => ({ ok: response.ok, payload })))
            .then(({ ok, payload }) => {
                hideLoading();
                if (!ok) throw payload;

                state.activeJobToken = payload.jobToken;
                updateStatusPanel(payload);
                scheduleStatusPoll(500);
            })
            .catch((error) => {
                hideLoading();
                console.error('Failed to start pipeline', error);

                const messages = [];
                if (error && error.errors) {
                    Object.keys(error.errors).forEach((key) => {
                        error.errors[key].forEach((msg) => messages.push(msg));
                    });
                }

                const fallback = (error && (error.error || error.message)) || 'Failed to start pipeline.';
                handleJobFailure(messages.length ? messages.join(' • ') : fallback);
            });
    };

    // ========================================================================
    // Upload State Management
    // ========================================================================

    const clearUploadState = () => {
        state.stagedUpload = null;
        state.metadataReady = false;
        state.customMetadataDirty = false;
        elements.stagingTokenInput.value = '';

        if (elements.uploadSummary) {
            elements.uploadSummary.hidden = true;
            elements.uploadSummary.textContent = '';
        }

        toggleVisibility(elements.metadataChoice, false);
        elements.finalizeButton.disabled = true;
        elements.finalizeButton.hidden = true;
        elements.finalizeStatus.textContent = '';
        elements.finalizeStatus.dataset.state = '';
        elements.columnTableBody.innerHTML = '';
        elements.datasetNameInput.value = '';
        elements.tableNameInput.value = '';
        state.currentTable = null;
        hideAdvanced();
        if (elements.metadataReminder) elements.metadataReminder.hidden = true;
        elements.runButton.disabled = true;
        updatePreview();

        if (!state.jobIsRunning) {
            resetStatusPanel();
        }
        updateRunButton();
    };

    // ========================================================================
    // Metadata Management
    // ========================================================================

    const renderColumnRows = (columns) => {
        elements.columnTableBody.innerHTML = '';

        columns.forEach((column) => {
            const row = document.createElement('tr');
            row.dataset.columnName = column.name;

            // Column name
            const nameCell = document.createElement('td');
            nameCell.textContent = column.name;
            row.appendChild(nameCell);

            // Inferred type
            const inferredCell = document.createElement('td');
            inferredCell.textContent = column.inferred_type;
            row.appendChild(inferredCell);

            // Missing values
            const missingCell = document.createElement('td');
            missingCell.textContent = column.allow_missing ? 'Yes' : 'No';
            row.appendChild(missingCell);

            // Kind select
            const kindCell = document.createElement('td');
            const kindSelect = document.createElement('select');
            kindSelect.className = 'input-control compact';
            kindSelect.dataset.columnName = column.name;
            kindSelect.dataset.role = 'kind';

            config.columnKinds.forEach((kind) => {
                const option = document.createElement('option');
                option.value = kind;
                option.textContent = kind;
                if (kind === column.inferred_type) {
                    option.selected = true;
                }
                kindSelect.appendChild(option);
            });
            kindCell.appendChild(kindSelect);
            row.appendChild(kindCell);

            // Representation select
            const representationCell = document.createElement('td');
            const representationPlaceholder = document.createElement('span');
            representationPlaceholder.className = 'text-muted';
            representationPlaceholder.textContent = '-';

            const representationSelect = document.createElement('select');
            representationSelect.className = 'input-control compact';
            representationSelect.dataset.columnName = column.name;
            representationSelect.dataset.role = 'representation';

            config.representationOptions.forEach((optionValue) => {
                const option = document.createElement('option');
                option.value = optionValue;
                option.textContent = optionValue;
                representationSelect.appendChild(option);
            });
            representationSelect.value = column.representation || 'Float';

            representationCell.appendChild(representationPlaceholder);
            representationCell.appendChild(representationSelect);
            row.appendChild(representationCell);

            // Sync representation visibility based on kind
            const syncRepresentationControls = () => {
                const isNumeric = kindSelect.value === 'numerical';
                representationSelect.hidden = !isNumeric;
                representationSelect.disabled = !isNumeric;
                representationPlaceholder.hidden = isNumeric;
            };
            syncRepresentationControls();

            // Event listeners for metadata changes
            const handleMetadataChange = () => {
                state.customMetadataDirty = true;
                elements.finalizeButton.disabled = false;
                elements.finalizeButton.hidden = false;
                elements.finalizeStatus.dataset.state = '';
                state.metadataReady = false;
                if (elements.metadataReminder) elements.metadataReminder.hidden = false;
                updateRunButton();
            };

            kindSelect.addEventListener('change', () => {
                handleMetadataChange();
                syncRepresentationControls();
            });

            representationSelect.addEventListener('change', handleMetadataChange);

            // Primary key radio
            const pkCell = document.createElement('td');
            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = 'primary-key';
            radio.value = column.name;
            radio.addEventListener('change', handleMetadataChange);
            pkCell.appendChild(radio);
            row.appendChild(pkCell);

            elements.columnTableBody.appendChild(row);
        });
    };

    const collectCustomMetadata = () => {
        const rows = toArray(elements.columnTableBody.querySelectorAll('tr'));
        const columns = rows.map((row) => {
            const name = row.dataset.columnName;
            const kindSelect = row.querySelector('select[data-role="kind"]');
            const representationSelect = row.querySelector('select[data-role="representation"]');
            const kind = kindSelect ? kindSelect.value : 'categorical';
            const representation = representationSelect && !representationSelect.disabled
                ? representationSelect.value
                : null;

            return { name, kind, representation };
        });

        const primaryRadio = elements.columnTableBody.querySelector('input[name="primary-key"]:checked');

        return {
            columns,
            primaryKey: primaryRadio ? primaryRadio.value : null,
        };
    };

    const finalizeCustomMetadata = () => {
        const { columns, primaryKey } = collectCustomMetadata();
        if (!columns.length) return;

        elements.finalizeButton.disabled = true;
        elements.finalizeStatus.textContent = 'Saving metadata...';
        elements.finalizeStatus.dataset.state = '';

        showLoading('Saving metadata...');

        fetch(config.apiUrls.finalize, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': config.csrfToken || '',
            },
            body: JSON.stringify({
                token: state.stagedUpload ? state.stagedUpload.token : null,
                columns,
                primaryKey,
            }),
        })
            .then((response) => response.json().then((payload) => ({ ok: response.ok, payload })))
            .then(({ ok, payload }) => {
                hideLoading();
                if (!ok) throw payload;

                elements.finalizeStatus.textContent = 'Metadata saved successfully.';
                elements.finalizeStatus.dataset.state = 'saved';
                state.customMetadataDirty = false;
                state.metadataReady = true;
                showAdvanced();
                updateRunButton();
            })
            .catch((error) => {
                hideLoading();
                console.error('Failed to save metadata', error);
                elements.finalizeStatus.textContent = 'Failed to save metadata';
                elements.finalizeStatus.dataset.state = '';
                elements.finalizeButton.disabled = false;
            });
    };

    const setMetadataMode = (value) => {
        if (value === 'template') {
            toggleVisibility(elements.metadataTemplatePanel, true);
            toggleVisibility(elements.metadataCustomPanel, false);
        } else if (value === 'custom') {
            toggleVisibility(elements.metadataTemplatePanel, false);
            toggleVisibility(elements.metadataCustomPanel, true);
        } else {
            toggleVisibility(elements.metadataTemplatePanel, false);
            toggleVisibility(elements.metadataCustomPanel, false);
        }
        updateMetadataState();
    };

    const updateMetadataState = () => {
        if (!state.stagedUpload) {
            toggleVisibility(elements.metadataChoice, false);
            state.metadataReady = false;
            hideAdvanced();
            if (elements.metadataReminder) elements.metadataReminder.hidden = true;
            updateRunButton();
            return;
        }

        toggleVisibility(elements.metadataChoice, true);
        const selectedMode = getSelectedMetadataMode();

        if (selectedMode === 'template') {
            state.metadataReady = Boolean(elements.templateSelect.value);
            elements.finalizeButton.hidden = true;
            elements.finalizeButton.disabled = true;
            elements.finalizeStatus.textContent = state.metadataReady
                ? 'Using selected template metadata.'
                : '';
            elements.finalizeStatus.dataset.state = state.metadataReady ? 'saved' : '';
            if (elements.metadataReminder) elements.metadataReminder.hidden = state.metadataReady;

            if (state.metadataReady) {
                showAdvanced();
            } else {
                hideAdvanced();
            }
        } else if (selectedMode === 'custom') {
            state.metadataReady = !state.customMetadataDirty && elements.finalizeStatus.dataset.state === 'saved';
            elements.finalizeButton.hidden = false;
            elements.finalizeButton.disabled = state.metadataReady;
            if (elements.metadataReminder) elements.metadataReminder.hidden = state.metadataReady;

            if (state.metadataReady) {
                showAdvanced();
            } else {
                hideAdvanced();
            }
        } else {
            state.metadataReady = false;
            hideAdvanced();
        }

        updateRunButton();
    };

    // ========================================================================
    // File Upload
    // ========================================================================

    const handleFileUpload = async () => {
        if (!elements.fileInput.files || !elements.fileInput.files.length) return;

        const file = elements.fileInput.files[0];
        if (!state.jobIsRunning) resetStatusPanel();

        const formData = new FormData();
        formData.append('dataset', file);

        if (elements.datasetNameInput.value) {
            formData.append('datasetName', elements.datasetNameInput.value);
        }
        if (elements.tableNameInput.value) {
            formData.append('tableName', elements.tableNameInput.value);
        }

        showUploadSummary('Uploading and profiling data...', false);
        showLoading('Uploading CSV file...');
        elements.runButton.disabled = true;
        state.metadataReady = false;
        state.customMetadataDirty = false;
        elements.finalizeStatus.textContent = '';
        elements.finalizeStatus.dataset.state = '';

        try {
            const response = await fetch(config.apiUrls.stage, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': config.csrfToken || '',
                },
                body: formData,
            });

            hideLoading();

            if (!response.ok) throw new Error('Upload failed');

            const payload = await response.json();
            state.stagedUpload = {
                token: payload.token,
                datasetName: payload.datasetName,
                tableName: payload.tableName,
                columns: payload.columns || [],
            };

            elements.stagingTokenInput.value = state.stagedUpload.token;
            showUploadSummary(
                `${payload.rowCount || 'Rows'} • ${payload.columns.length} columns`,
                false
            );

            renderColumnRows(state.stagedUpload.columns);
            state.metadataReady = false;
            state.customMetadataDirty = false;
            elements.finalizeStatus.dataset.state = '';
            elements.finalizeStatus.textContent = '';

            // Populate template options
            elements.templateSelect.innerHTML = '';
            if (payload.templates && payload.templates.length) {
                payload.templates.forEach((template) => {
                    const option = document.createElement('option');
                    option.value = template.value;
                    option.textContent = template.label;
                    elements.templateSelect.appendChild(option);
                });
                elements.templateSelect.value = '';
            }

            toggleVisibility(elements.metadataChoice, true);
            setMetadataMode('template');
            updatePreview();
        } catch (error) {
            hideLoading();
            console.error('Upload failed', error);
            clearUploadState();
            showUploadSummary('Upload failed. Please verify the file and try again.', true);
        }
    };

    // ========================================================================
    // Command Preview
    // ========================================================================

    const updatePreview = () => {
        const selectedDataset = elements.datasetSelect
            ? elements.datasetSelect.value || config.defaults.dataset
            : config.defaults.dataset;
        const dataSource = getSelectedDataSource();
        const epochsV = document.getElementById('id_epochs_vae').value || config.defaults.epochs_vae;
        const epochsG = document.getElementById('id_epochs_gnn').value || config.defaults.epochs_gnn;
        const epochsD = document.getElementById('id_epochs_diff').value || config.defaults.epochs_diff;

        let dataset = selectedDataset;
        let table = config.tableMap[selectedDataset] || selectedDataset;

        if (dataSource === 'uploaded' && state.stagedUpload) {
            dataset = state.stagedUpload.datasetName;
            if (elements.datasetNameInput.value) {
                dataset = elements.datasetNameInput.value.replace(/[^A-Za-z0-9_\-]/g, '_').toLowerCase() || dataset;
            }

            const selectedMode = getSelectedMetadataMode();
            if (selectedMode === 'template' && elements.templateSelect.value) {
                table = config.tableMap[elements.templateSelect.value] || state.stagedUpload.tableName;
            } else if (state.currentTable) {
                table = state.currentTable;
            } else if (elements.tableNameInput.value) {
                table = elements.tableNameInput.value;
            } else {
                table = state.stagedUpload.tableName;
            }
        }

        const previewCommand = [
            'python src/scripts/run_pipeline.py',
            `--dataset-name ${dataset}`,
            `--target-table ${table}`,
            `--epochs-gnn ${epochsG}`,
            `--epochs-vae ${epochsV}`,
            `--epochs-diff ${epochsD}`,
        ].join(' ');

        elements.commandPreview.textContent = previewCommand;
    };

    // ========================================================================
    // Data Source Management
    // ========================================================================

    const setDataSource = (value) => {
        if (!state.jobIsRunning) resetStatusPanel();

        if (value === 'preloaded') {
            toggleVisibility(elements.preloadedSection, true);
            toggleVisibility(elements.uploadSection, false);
            toggleVisibility(elements.metadataChoice, false);
            state.metadataReady = true;
            if (elements.metadataReminder) elements.metadataReminder.hidden = true;
            showAdvanced();
        } else {
            toggleVisibility(elements.preloadedSection, false);
            toggleVisibility(elements.uploadSection, true);
            toggleVisibility(elements.metadataChoice, Boolean(state.stagedUpload));
            if (!state.stagedUpload) {
                state.metadataReady = false;
                hideAdvanced();
            }
        }

        updatePreview();
        updateRunButton();
    };

    // ========================================================================
    // Run Button Management
    // ========================================================================

    const updateRunButton = () => {
        if (!elements.runButton) return;

        if (state.jobIsRunning) {
            elements.runButton.disabled = true;
            elements.runButton.textContent = 'Running...';
            return;
        }

        elements.runButton.textContent = config.runButtonDefaultLabel;
        const dataSource = getSelectedDataSource();

        if (dataSource === 'uploaded') {
            const ready = Boolean(state.stagedUpload) && state.metadataReady;
            elements.runButton.disabled = !ready;
            if (elements.metadataReminder) elements.metadataReminder.hidden = ready;
        } else {
            elements.runButton.disabled = false;
            if (elements.metadataReminder) elements.metadataReminder.hidden = true;
        }
    };

    // ========================================================================
    // Template Management
    // ========================================================================

    const ensureTemplateOptions = () => {
        if (elements.metadataTemplateField && elements.templateSelect) {
            elements.templateSelect.innerHTML = '';
            toArray(elements.metadataTemplateField.querySelectorAll('option')).forEach((option) => {
                const clone = option.cloneNode(true);
                elements.templateSelect.appendChild(clone);
            });
            elements.templateSelect.value = elements.metadataTemplateField.value || '';
        }
    };

    const updateTemplateSelection = (value) => {
        if (elements.metadataTemplateField) {
            elements.metadataTemplateField.value = value;
        }
        updateMetadataState();
    };

    // ========================================================================
    // Event Listeners
    // ========================================================================

    const attachEventListeners = () => {
        // Data source selection
        toArray(elements.dataSourceRadios).forEach((radio) => {
            radio.addEventListener('change', (event) => {
                setDataSource(event.target.value);
            });
        });

        // Metadata mode selection
        toArray(elements.metadataModeRadios).forEach((radio) => {
            radio.addEventListener('change', (event) => {
                setMetadataMode(event.target.value);
            });
        });

        // Dataset selection
        if (elements.datasetSelect) {
            elements.datasetSelect.addEventListener('change', () => {
                if (elements.metadataTemplateField) {
                    elements.metadataTemplateField.value = elements.datasetSelect.value;
                }
                if (!state.jobIsRunning) resetStatusPanel();
                updatePreview();
            });
        }

        // Metadata template field
        if (elements.metadataTemplateField) {
            elements.metadataTemplateField.addEventListener('change', () => {
                if (!state.jobIsRunning) resetStatusPanel();
                updatePreview();
            });
        }

        // Template selection
        elements.templateSelect.addEventListener('change', () => {
            updateTemplateSelection(elements.templateSelect.value);
            if (state.stagedUpload) {
                state.metadataReady = Boolean(elements.templateSelect.value);
                elements.finalizeStatus.textContent = state.metadataReady
                    ? 'Using selected template metadata.'
                    : '';
                elements.finalizeStatus.dataset.state = state.metadataReady ? 'saved' : '';
                if (elements.metadataReminder) elements.metadataReminder.hidden = state.metadataReady;
                if (state.metadataReady) {
                    showAdvanced();
                } else {
                    hideAdvanced();
                }
                setMetadataMode('template');
            }
            updateRunButton();
        });

        // File upload
        elements.fileInput.addEventListener('change', () => {
            clearUploadState();
            if (elements.fileInput.files && elements.fileInput.files.length) {
                handleFileUpload();
            }
        });

        // Dataset name input
        elements.datasetNameInput.addEventListener('input', () => {
            if (state.stagedUpload) {
                state.metadataReady = false;
                elements.finalizeStatus.dataset.state = '';
                state.customMetadataDirty = true;
                elements.finalizeButton.disabled = false;
                elements.finalizeButton.hidden = false;
                if (elements.metadataReminder) elements.metadataReminder.hidden = false;
                if (!state.jobIsRunning) resetStatusPanel();
                updateRunButton();
                updatePreview();
            }
        });

        // Table name input
        elements.tableNameInput.addEventListener('input', () => {
            if (state.stagedUpload) {
                state.metadataReady = false;
                elements.finalizeStatus.dataset.state = '';
                state.customMetadataDirty = true;
                elements.finalizeButton.disabled = false;
                elements.finalizeButton.hidden = false;
                state.currentTable = elements.tableNameInput.value || state.stagedUpload.tableName;
                if (elements.metadataReminder) elements.metadataReminder.hidden = false;
                if (!state.jobIsRunning) resetStatusPanel();
                updateRunButton();
                updatePreview();
            }
        });

        // Finalize metadata button
        elements.finalizeButton.addEventListener('click', finalizeCustomMetadata);

        // Epoch inputs
        ['id_epochs_vae', 'id_epochs_gnn', 'id_epochs_diff'].forEach((id) => {
            const input = document.getElementById(id);
            if (input) {
                input.addEventListener('input', updatePreview);
            }
        });

        // Form submission
        if (elements.formElement) {
            elements.formElement.addEventListener('submit', (event) => {
                event.preventDefault();
                startPipelineRun();
            });
        }

        // Cleanup on page unload
        window.addEventListener('beforeunload', stopStatusPoll);
    };

    // ========================================================================
    // Initialization
    // ========================================================================

    const init = () => {
        ensureTemplateOptions();
        attachEventListeners();
        resetStatusPanel();
        toggleStatusPlaceholder();
        setDataSource(getSelectedDataSource());
        setMetadataMode('template');
        updatePreview();
        updateRunButton();

        console.log('TabGraphSyn upload interface initialized');
    };

    // Run initialization when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
