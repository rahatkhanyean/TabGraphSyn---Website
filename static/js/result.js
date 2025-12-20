// Interactive features for the result page (no page scroll layout)

let umapData = null;
let currentHoveredRow = null;
let allDataRows = [];
let allHeaders = [];
let selectedHeaders = [];
let currentDisplayMode = 'all';
const PREVIEW_ROW_COUNT = 20;
let statsSelectedColumn = null;
let rowSearchQuery = '';

function initializeInteractiveUMAP(umapCoordinates) {
    if (!umapCoordinates || umapCoordinates.length === 0) return;
    umapData = umapCoordinates;

    const realPoints = umapCoordinates.filter(p => p.type === 'real');
    const syntheticPoints = umapCoordinates.filter(p => p.type === 'synthetic');

    const realTrace = {
        x: realPoints.map(p => p.x),
        y: realPoints.map(p => p.y),
        mode: 'markers',
        type: 'scatter',
        name: 'Real Data',
        marker: { color: '#3b82f6', size: 8, opacity: 0.6, line: { color: '#1e40af', width: 1 } },
        hovertemplate: '<b>Real Data</b><br>Index: %{customdata}<br>x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>',
        customdata: realPoints.map(p => p.index)
    };

    const syntheticTrace = {
        x: syntheticPoints.map(p => p.x),
        y: syntheticPoints.map(p => p.y),
        mode: 'markers',
        type: 'scatter',
        name: 'Synthetic Data',
        marker: { color: '#22c55e', size: 8, opacity: 0.6, line: { color: '#15803d', width: 1 } },
        hovertemplate: '<b>Synthetic Data</b><br>Row: %{customdata}<br>x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>',
        customdata: syntheticPoints.map(p => p.index),
        ids: syntheticPoints.map(p => `synthetic-${p.index}`)
    };

    const plotDiv = document.getElementById('interactive-umap-plot');
    const layout = {
        autosize: true,
        xaxis: {
            title: { text: 'UMAP Dimension 1', standoff: 12, font: { size: 12, family: 'Inter, sans-serif', color: '#475569' } },
            tickfont: { size: 11, family: 'Inter, sans-serif', color: '#475569' },
            gridcolor: 'rgba(148, 163, 184, 0.1)',
            zeroline: false,
            automargin: true
        },
        yaxis: {
            title: { text: 'UMAP Dimension 2', standoff: 10, font: { size: 12, family: 'Inter, sans-serif', color: '#475569' } },
            tickfont: { size: 11, family: 'Inter, sans-serif', color: '#475569' },
            gridcolor: 'rgba(148, 163, 184, 0.1)',
            zeroline: false,
            automargin: true
        },
        hovermode: 'closest',
        showlegend: true,
        legend: {
            orientation: 'h',
            x: 0.5,
            xanchor: 'center',
            y: 1.12,
            yanchor: 'bottom',
            bgcolor: 'rgba(255,255,255,0.95)',
            bordercolor: 'rgba(148,163,184,0.3)',
            borderwidth: 1,
            font: { size: 11, family: 'Inter, sans-serif', color: '#334155' }
        },
        plot_bgcolor: '#ffffff',
        paper_bgcolor: '#ffffff',
        margin: { l: 48, r: 24, t: 56, b: 48 }
    };

    const config = { responsive: true, displayModeBar: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'], displaylogo: false };

    if (plotDiv) {
        Plotly.newPlot(plotDiv, [realTrace, syntheticTrace], layout, config);
        requestAnimationFrame(() => Plotly.Plots.resize(plotDiv));
        if (!plotDiv.dataset.resizeBound) {
            plotDiv.dataset.resizeBound = 'true';
            window.addEventListener('resize', () => Plotly.Plots.resize(plotDiv));
        }
    }
}

function highlightUMAPPoint(rowIndex) {
    if (!umapData || rowIndex === null) return;
    const syntheticPoint = umapData.find(p => p.type === 'synthetic' && p.index === rowIndex);
    if (!syntheticPoint) return;

    const highlightTrace = {
        x: [syntheticPoint.x],
        y: [syntheticPoint.y],
        mode: 'markers',
        type: 'scatter',
        name: 'Highlighted',
        marker: { color: '#f59e0b', size: 16, opacity: 1, line: { color: '#d97706', width: 3 }, symbol: 'star' },
        hovertemplate: '<b>Highlighted Row</b><br>Row: %{customdata}<br>x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>',
        customdata: [rowIndex],
        showlegend: false
    };

    const plotDiv = document.getElementById('interactive-umap-plot');
    if (plotDiv && plotDiv.data) {
        if (plotDiv.data.length > 2) {
            Plotly.deleteTraces(plotDiv, 2);
        }
        Plotly.addTraces(plotDiv, highlightTrace);
    }
}

function removeUMAPHighlight() {
    const plotDiv = document.getElementById('interactive-umap-plot');
    if (plotDiv && plotDiv.data && plotDiv.data.length > 2) {
        Plotly.deleteTraces(plotDiv, 2);
    }
}

function attachTableHoverListeners() {
    const tableBody = document.querySelector('.data-preview-table tbody');
    if (!tableBody) return;

    const rows = tableBody.querySelectorAll('tr');
    rows.forEach((row, index) => {
        if (!row.hasAttribute('data-row-index')) row.setAttribute('data-row-index', index);
        row.addEventListener('mouseenter', function () {
            const idx = Number(this.getAttribute('data-row-index'));
            currentHoveredRow = idx;
            this.classList.add('row-highlighted');
            highlightUMAPPoint(idx);
        });
        row.addEventListener('mouseleave', function () {
            currentHoveredRow = null;
            this.classList.remove('row-highlighted');
            removeUMAPHighlight();
        });
    });
}

function toggleDataView() {
    const toggleButton = document.getElementById('toggle-data-view');
    if (!toggleButton) return;

    currentDisplayMode = currentDisplayMode === 'preview' ? 'all' : 'preview';
    toggleButton.innerHTML = currentDisplayMode === 'preview'
        ? '<i class="fa-solid fa-expand"></i> View all rows'
        : '<i class="fa-solid fa-compress"></i> Show Preview (20 rows)';

    renderCurrentView();
}

function renderRows(rows, offset, rowIndexes = null) {
    const tableBody = document.querySelector('.data-preview-table tbody');
    if (!tableBody) return;
    const columnIndexes = getSelectedColumnIndexes();
    const headersToRender = columnIndexes.length ? columnIndexes.map(idx => allHeaders[idx]) : allHeaders;
    tableBody.innerHTML = '';

    updateTableHeader(headersToRender);

    if (!rows.length) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.className = 'loading-row';
        td.textContent = 'No matching rows.';
        td.colSpan = headersToRender.length || 1;
        tr.appendChild(td);
        tableBody.appendChild(tr);
        return;
    }

    rows.forEach((row, idx) => {
        const tr = document.createElement('tr');
        const rowIndex = rowIndexes ? rowIndexes[idx] : offset + idx;
        tr.setAttribute('data-row-index', rowIndex);
        const source = columnIndexes.length ? columnIndexes : null;
        const cells = source ? source.map(ci => row[ci]) : row;
        cells.forEach(cell => {
            const td = document.createElement('td');
            td.textContent = cell;
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });
}

function renderAllData() {
    if (!allDataRows.length) return;
    renderRows(allDataRows, 0);
}

function renderPreviewData() {
    if (!allDataRows.length) return;
    renderRows(allDataRows.slice(0, PREVIEW_ROW_COUNT), 0);
}

function updateRowCountDisplay(displayedRows = null, totalRowsOverride = null, isFiltered = false) {
    const totalRows = totalRowsOverride ?? allDataRows.length;
    const displayed = displayedRows ?? (currentDisplayMode === 'preview' ? Math.min(PREVIEW_ROW_COUNT, totalRows) : totalRows);
    const selectedColumns = getSelectedColumnIndexes();
    const selectedCount = selectedColumns.length || allHeaders.length;

    const modeLabel = document.getElementById('data-mode-label');
    const rowCount = document.getElementById('data-row-count');
    const rowTotal = document.getElementById('data-row-total');
    const columnCount = document.getElementById('data-column-count');

    if (modeLabel) {
        if (isFiltered) {
            modeLabel.textContent = 'Filtered view';
        } else {
            modeLabel.textContent = currentDisplayMode === 'preview' && totalRows > PREVIEW_ROW_COUNT ? 'Preview view' : 'Full dataset';
        }
    }
    if (rowCount) rowCount.textContent = displayed;
    if (rowTotal) rowTotal.textContent = totalRows;
    if (columnCount) columnCount.textContent = selectedCount;
}

function renderCurrentView() {
    if (!allDataRows.length) return;
    const search = rowSearchQuery.trim().toLowerCase();
    if (search) {
        const columnIndexes = getSelectedColumnIndexes();
        const searchIndexes = columnIndexes.length ? columnIndexes : allHeaders.map((_, idx) => idx);
        const matches = [];
        const matchIndexes = [];
        allDataRows.forEach((row, idx) => {
            const hit = searchIndexes.some(ci => String(row[ci] ?? '').toLowerCase().includes(search));
            if (hit) {
                matches.push(row);
                matchIndexes.push(idx);
            }
        });
        const limitedRows = matches.slice(0, PREVIEW_ROW_COUNT);
        const limitedIndexes = matchIndexes.slice(0, PREVIEW_ROW_COUNT);
        renderRows(limitedRows, 0, limitedIndexes);
        updateRowCountDisplay(limitedRows.length, matches.length, true);
    } else {
        if (currentDisplayMode === 'preview') renderPreviewData(); else renderAllData();
        updateRowCountDisplay();
    }
    attachTableHoverListeners();
}

function initMetricTooltips() {
    const triggers = Array.from(document.querySelectorAll('.metric-help'));
    if (!triggers.length) return;

    const closeAll = (except = null) => {
        document.querySelectorAll('.metric-help.is-open').forEach((el) => {
            if (except && el === except) return;
            el.classList.remove('is-open');
            el.setAttribute('aria-expanded', 'false');
        });
    };

    const toggleTooltip = (trigger) => {
        const isOpen = trigger.classList.contains('is-open');
        closeAll(trigger);
        if (isOpen) {
            trigger.classList.remove('is-open');
            trigger.setAttribute('aria-expanded', 'false');
        } else {
            trigger.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
        }
    };

    triggers.forEach((el) => {
        if (!el.hasAttribute('aria-expanded')) el.setAttribute('aria-expanded', 'false');
        el.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            toggleTooltip(el);
        });
        el.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            toggleTooltip(el);
        });
    });

    document.addEventListener('click', (event) => {
        const target = event.target instanceof Element ? event.target : event.target?.parentElement;
        if (!target) return;
        if (target.closest('.metric-tooltip')) return;
        if (!target.closest('.metric-help')) closeAll();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeAll();
            return;
        }
    });
}

function updateTableHeader(headersToRender) {
    const headerRow = document.querySelector('.data-preview-table thead tr');
    if (!headerRow) return;
    headerRow.innerHTML = '';
    headersToRender.forEach(header => {
        const th = document.createElement('th');
        th.textContent = header;
        headerRow.appendChild(th);
    });
}

function getSelectedColumnIndexes() {
    if (!allHeaders.length) return [];
    if (!selectedHeaders.length) return allHeaders.map((_, idx) => idx);
    return selectedHeaders.map(h => allHeaders.indexOf(h)).filter(idx => idx >= 0);
}

function populateColumnSelector(headers) {
    const selector = document.getElementById('column-selector');
    if (!selector || !headers.length) return;
    selector.innerHTML = '';
    headers.forEach(header => {
        const option = document.createElement('option');
        option.value = header;
        option.textContent = header;
        option.selected = selectedHeaders.length === 0 || selectedHeaders.includes(header);
        option.hidden = false;
        selector.appendChild(option);
    });
}

function filterColumnOptions(query) {
    const selector = document.getElementById('column-selector');
    if (!selector) return;
    const search = query.trim().toLowerCase();
    Array.from(selector.options).forEach(option => {
        option.hidden = search ? !option.value.toLowerCase().includes(search) : false;
    });
}

function resetColumnSelection() {
    if (!allHeaders.length) return;
    selectedHeaders = [...allHeaders];
    populateColumnSelector(allHeaders);
    renderCurrentView();
    const columnSearch = document.getElementById('column-search');
    if (columnSearch) {
        columnSearch.value = '';
        filterColumnOptions('');
    }
}

function isNumericColumn(index) {
    if (!allDataRows.length) return false;
    for (let i = 0; i < Math.min(allDataRows.length, 30); i++) {
        const num = Number(allDataRows[i][index]);
        if (!Number.isFinite(num)) return false;
    }
    return true;
}

function computeStatsForColumn(index) {
    if (index == null || index < 0) return null;
    const values = [];
    const uniques = new Set();
    allDataRows.forEach(row => {
        const raw = row[index];
        if (raw === '' || raw === null || raw === undefined) return;
        const num = Number(raw);
        if (Number.isFinite(num)) {
            values.push(num);
            uniques.add(raw);
        } else {
            uniques.add(raw);
        }
    });
    if (!values.length) {
        return { count: 0, unique: uniques.size, min: '-', max: '-', mean: '-', std: '-' };
    }
    const count = values.length;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const mean = values.reduce((a, b) => a + b, 0) / count;
    const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / count;
    const std = Math.sqrt(variance);
    return { count, unique: uniques.size, min, max, mean, std };
}

function updateStatsUI(stats) {
    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    };
    const fmt = (v) => typeof v === 'number' ? Number(v).toFixed(4).replace(/\.?0+$/, '') : v;
    setText('stat-count', stats?.count ?? '-');
    setText('stat-unique', stats?.unique ?? '-');
    setText('stat-min', stats ? fmt(stats.min) : '-');
    setText('stat-max', stats ? fmt(stats.max) : '-');
    setText('stat-mean', stats ? fmt(stats.mean) : '-');
    setText('stat-std', stats ? fmt(stats.std) : '-');
}

function selectStatsColumnByIndex(idx) {
    if (idx == null || idx < 0) return;
    statsSelectedColumn = idx;
    const selector = document.getElementById('stats-column-selector');
    if (selector) selector.value = allHeaders[idx];
    const stats = computeStatsForColumn(idx);
    updateStatsUI(stats);
}

function initStatsSelector() {
    const selector = document.getElementById('stats-column-selector');
    if (!selector) return;
    selector.innerHTML = '';
    allHeaders.forEach((header, index) => {
        const option = document.createElement('option');
        option.value = header;
        option.textContent = header;
        selector.appendChild(option);
    });
    let defaultIdx = allHeaders.findIndex((_, idx) => isNumericColumn(idx));
    if (defaultIdx === -1) defaultIdx = 0;
    selectStatsColumnByIndex(defaultIdx);
    selector.addEventListener('change', (e) => {
        const header = e.target.value;
        const idx = allHeaders.indexOf(header);
        if (idx >= 0) selectStatsColumnByIndex(idx);
    });
}

async function loadFullDataset(token) {
    try {
        const response = await fetch(`/api/dataset/${token}/`);
        if (!response.ok) throw new Error('Failed to load full dataset');
        const data = await response.json();
        allHeaders = data.headers || allHeaders;
        selectedHeaders = selectedHeaders.length ? selectedHeaders.filter(h => allHeaders.includes(h)) : [...allHeaders];
        allDataRows = data.rows;
        currentDisplayMode = allDataRows.length > PREVIEW_ROW_COUNT ? 'preview' : 'all';

        const toggleButton = document.getElementById('toggle-data-view');
        if (toggleButton) {
            toggleButton.disabled = false;
            toggleButton.style.display = 'inline-flex';
            toggleButton.innerHTML = currentDisplayMode === 'preview'
                ? '<i class="fa-solid fa-expand"></i> View all rows'
                : '<i class="fa-solid fa-compress"></i> Show Preview (20 rows)';
        }

        populateColumnSelector(allHeaders);
        renderCurrentView();
        initStatsSelector();
    } catch (error) {
        console.error('Error loading full dataset:', error);
        const tableBody = document.querySelector('.data-preview-table tbody');
        if (tableBody && tableBody.querySelectorAll('tr').length === 0) {
            tableBody.innerHTML = '<tr><td class="loading-row">Failed to load dataset.</td></tr>';
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const resultPage = document.querySelector('.result-viewport');
    if (!resultPage) return;

    const tableBody = document.querySelector('.data-preview-table tbody');
    if (tableBody && tableBody.children.length === 0) {
        tableBody.innerHTML = '<tr><td class="loading-row">Loading full dataset.</td></tr>';
    }

    const tokenElement = document.querySelector('[data-run-token]');
    const runToken = tokenElement ? tokenElement.getAttribute('data-run-token') : null;

    const umapDataElement = document.getElementById('umap-data');
    if (umapDataElement) {
        try {
            const umapCoordinates = JSON.parse(umapDataElement.textContent);
            initializeInteractiveUMAP(umapCoordinates);
        } catch (error) {
            console.error('Error parsing UMAP data:', error);
        }
    }

    attachTableHoverListeners();
    if (runToken) loadFullDataset(runToken);

    const toggleButton = document.getElementById('toggle-data-view');
    if (toggleButton) {
        toggleButton.style.display = 'inline-flex';
        toggleButton.addEventListener('click', toggleDataView);
    }

    const columnSelector = document.getElementById('column-selector');
    if (columnSelector) {
        columnSelector.addEventListener('change', () => {
            const selected = Array.from(columnSelector.selectedOptions).map(opt => opt.value);
            selectedHeaders = selected.length ? selected : [...allHeaders];
            renderCurrentView();
        });
    }

    const columnSearch = document.getElementById('column-search');
    if (columnSearch) {
        columnSearch.addEventListener('input', (event) => filterColumnOptions(event.target.value));
    }

    const rowSearch = document.getElementById('row-search');
    if (rowSearch) {
        rowSearch.addEventListener('input', (event) => {
            rowSearchQuery = event.target.value || '';
            renderCurrentView();
        });
    }

    const resetColumnsButton = document.getElementById('reset-columns');
    if (resetColumnsButton) {
        resetColumnsButton.addEventListener('click', resetColumnSelection);
    }

    initMetricTooltips();

    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-button').forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
                b.setAttribute('tabindex', '-1');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            btn.setAttribute('tabindex', '0');
            const tab = btn.getAttribute('data-tab');
            document.querySelectorAll('[data-tab-panel]').forEach(panel => {
                const isActive = panel.getAttribute('data-tab-panel') === tab;
                panel.classList.toggle('hidden', !isActive);
                panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
            });
        });
    });
});
