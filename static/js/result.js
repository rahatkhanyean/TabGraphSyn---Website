// Interactive features for the result page (no page scroll layout)

let umapData = null;
let umapRealPoints = [];
let umapSyntheticPoints = [];
let currentHoveredRow = null;
let allDataRows = [];
let allHeaders = [];
let selectedHeaders = [];
let currentDisplayMode = 'all';
const PREVIEW_ROW_COUNT = 20;
let statsSelectedColumn = null;
let rowSearchQuery = '';
let activeFilters = [];
let filteredRows = null;
let filteredRowIndexes = null;
let nextFilterId = 1;

const FILTER_OPERATORS = [
    { value: 'contains', label: 'contains', type: 'text' },
    { value: 'equals', label: 'equals', type: 'both' },
    { value: 'not_equals', label: 'not equals', type: 'both' },
    { value: 'gt', label: 'greater than', type: 'number' },
    { value: 'gte', label: 'greater or equal', type: 'number' },
    { value: 'lt', label: 'less than', type: 'number' },
    { value: 'lte', label: 'less or equal', type: 'number' },
    { value: 'between', label: 'between', type: 'number' },
    { value: 'is_empty', label: 'is empty', type: 'both', noValue: true },
    { value: 'not_empty', label: 'is not empty', type: 'both', noValue: true }
];

function initializeInteractiveUMAP(umapCoordinates) {
    if (!umapCoordinates || umapCoordinates.length === 0) return;
    umapData = umapCoordinates;

    const realPoints = umapCoordinates.filter(p => p.type === 'real');
    const syntheticPoints = umapCoordinates.filter(p => p.type === 'synthetic');
    umapRealPoints = realPoints;
    umapSyntheticPoints = syntheticPoints;

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
        if (activeFilters.length) {
            updateUMAPFilter();
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

function updateUMAPFilter() {
    if (!umapSyntheticPoints.length) return;
    const plotDiv = document.getElementById('interactive-umap-plot');
    if (!plotDiv || !plotDiv.data || plotDiv.data.length < 2) return;

    let filtered = umapSyntheticPoints;
    if (activeFilters.length && filteredRowIndexes) {
        const allowed = new Set(filteredRowIndexes);
        filtered = umapSyntheticPoints.filter(point => allowed.has(point.index));
    }

    Plotly.restyle(
        plotDiv,
        {
            x: [filtered.map(point => point.x)],
            y: [filtered.map(point => point.y)],
            customdata: [filtered.map(point => point.index)]
        },
        [1]
    );
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

function getBaseRows() {
    if (activeFilters.length && filteredRows && filteredRowIndexes) {
        return { rows: filteredRows, indexes: filteredRowIndexes };
    }
    return { rows: allDataRows, indexes: allDataRows.map((_, idx) => idx) };
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
    const filterCount = document.getElementById('filter-count');
    const metricsRowCount = document.getElementById('metrics-row-count');
    const metricsRowTotal = document.getElementById('metrics-row-total');
    const metricsColumnCount = document.getElementById('metrics-column-count');

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
    if (filterCount) filterCount.textContent = activeFilters.length;
    if (metricsRowCount) metricsRowCount.textContent = displayed;
    if (metricsRowTotal) metricsRowTotal.textContent = totalRows;
    if (metricsColumnCount) metricsColumnCount.textContent = selectedCount;
}

function renderCurrentView() {
    if (!allDataRows.length) return;
    const base = getBaseRows();
    const baseRows = base.rows;
    const baseIndexes = base.indexes;
    const search = rowSearchQuery.trim().toLowerCase();
    if (search) {
        const columnIndexes = getSelectedColumnIndexes();
        const searchIndexes = columnIndexes.length ? columnIndexes : allHeaders.map((_, idx) => idx);
        const matches = [];
        const matchIndexes = [];
        baseRows.forEach((row, idx) => {
            const hit = searchIndexes.some(ci => String(row[ci] ?? '').toLowerCase().includes(search));
            if (hit) {
                matches.push(row);
                matchIndexes.push(baseIndexes[idx]);
            }
        });
        const limitedRows = matches.slice(0, PREVIEW_ROW_COUNT);
        const limitedIndexes = matchIndexes.slice(0, PREVIEW_ROW_COUNT);
        renderRows(limitedRows, 0, limitedIndexes);
        updateRowCountDisplay(limitedRows.length, matches.length, activeFilters.length > 0 || search.length > 0);
    } else {
        const totalRows = baseRows.length;
        const limit = currentDisplayMode === 'preview' && totalRows > PREVIEW_ROW_COUNT;
        const rowsToShow = limit ? baseRows.slice(0, PREVIEW_ROW_COUNT) : baseRows;
        const indexesToShow = limit ? baseIndexes.slice(0, PREVIEW_ROW_COUNT) : baseIndexes;
        renderRows(rowsToShow, 0, indexesToShow);
        updateRowCountDisplay(rowsToShow.length, totalRows, activeFilters.length > 0);
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

function populateFilterColumnSelector(headers) {
    const selector = document.getElementById('filter-column');
    if (!selector || !headers.length) return;
    selector.innerHTML = '';
    headers.forEach(header => {
        const option = document.createElement('option');
        option.value = header;
        option.textContent = header;
        selector.appendChild(option);
    });
    updateFilterOperatorOptions(headers[0]);
}

function updateFilterOperatorOptions(selectedHeader) {
    const selector = document.getElementById('filter-operator');
    if (!selector) return;
    const colIndex = allHeaders.indexOf(selectedHeader);
    const numeric = colIndex >= 0 ? isNumericColumn(colIndex) : false;

    selector.innerHTML = '';
    FILTER_OPERATORS.forEach(op => {
        if (numeric && (op.type === 'number' || op.type === 'both')) {
            const option = document.createElement('option');
            option.value = op.value;
            option.textContent = op.label;
            option.dataset.noValue = op.noValue ? 'true' : 'false';
            selector.appendChild(option);
        }
        if (!numeric && (op.type === 'text' || op.type === 'both')) {
            const option = document.createElement('option');
            option.value = op.value;
            option.textContent = op.label;
            option.dataset.noValue = op.noValue ? 'true' : 'false';
            selector.appendChild(option);
        }
    });

    selector.dataset.numeric = numeric ? 'true' : 'false';
    syncFilterValueInputs();
}

function syncFilterValueInputs() {
    const selector = document.getElementById('filter-operator');
    const valueInput = document.getElementById('filter-value');
    const valueWrap = document.getElementById('filter-value-wrap');
    const maxWrap = document.getElementById('filter-value-max-wrap');
    if (!selector) return;
    const numeric = selector.dataset.numeric === 'true';
    const selectedOp = selector.value;
    const opConfig = FILTER_OPERATORS.find(op => op.value === selectedOp);
    const noValue = opConfig?.noValue ?? false;
    const isBetween = selectedOp === 'between';
    if (valueInput) valueInput.placeholder = numeric ? 'Enter number' : 'Enter value';
    if (maxWrap) maxWrap.classList.toggle('hidden', !isBetween);
    if (valueWrap) valueWrap.classList.toggle('hidden', noValue);
}

function renderActiveFilters() {
    const list = document.getElementById('active-filters');
    if (!list) return;
    list.innerHTML = '';
    if (!activeFilters.length) {
        list.innerHTML = '<div class="empty-state">No filters applied.</div>';
        return;
    }
    activeFilters.forEach(filter => {
        const item = document.createElement('div');
        item.className = 'filter-item';
        item.dataset.filterId = filter.id;
        const label = document.createElement('div');
        label.className = 'filter-item-label';
        label.textContent = `${filter.columnName} ${filter.operatorLabel}${filter.displayValue ? ` ${filter.displayValue}` : ''}`;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'filter-remove';
        button.textContent = 'Remove';
        button.setAttribute('data-filter-remove', filter.id);
        item.appendChild(label);
        item.appendChild(button);
        list.appendChild(item);
    });
}

function updateFilterPills() {
    const metricsPill = document.getElementById('metrics-filter-pill');
    const filterCount = activeFilters.length;
    if (metricsPill) {
        metricsPill.textContent = filterCount ? `Filters: ${filterCount}` : 'No filters';
    }
}

function rowMatchesFilter(row, filter) {
    const raw = row[filter.columnIndex];
    const text = String(raw ?? '').trim();
    const lower = text.toLowerCase();
    if (filter.operator === 'is_empty') return lower === '';
    if (filter.operator === 'not_empty') return lower !== '';

    if (filter.isNumeric) {
        const num = Number(raw);
        const value = Number(filter.value);
        const valueMax = Number(filter.valueMax);
        if (!Number.isFinite(num)) return false;
        switch (filter.operator) {
            case 'equals':
                return Number.isFinite(value) ? num === value : false;
            case 'not_equals':
                return Number.isFinite(value) ? num !== value : false;
            case 'gt':
                return Number.isFinite(value) ? num > value : false;
            case 'gte':
                return Number.isFinite(value) ? num >= value : false;
            case 'lt':
                return Number.isFinite(value) ? num < value : false;
            case 'lte':
                return Number.isFinite(value) ? num <= value : false;
            case 'between':
                return Number.isFinite(value) && Number.isFinite(valueMax) ? num >= value && num <= valueMax : false;
            default:
                return false;
        }
    }

    const needle = String(filter.value ?? '').toLowerCase();
    switch (filter.operator) {
        case 'contains':
            return needle ? lower.includes(needle) : false;
        case 'equals':
            return needle ? lower === needle : false;
        case 'not_equals':
            return needle ? lower !== needle : false;
        default:
            return false;
    }
}

function applyFilters() {
    if (!activeFilters.length) {
        filteredRows = null;
        filteredRowIndexes = null;
        updateFilterPills();
        removeUMAPHighlight();
        updateUMAPFilter();
        renderActiveFilters();
        const totalRows = allDataRows.length;
        currentDisplayMode = totalRows > PREVIEW_ROW_COUNT ? 'preview' : 'all';
        const toggleButton = document.getElementById('toggle-data-view');
        if (toggleButton) {
            toggleButton.innerHTML = currentDisplayMode === 'preview'
                ? '<i class="fa-solid fa-expand"></i> View all rows'
                : '<i class="fa-solid fa-compress"></i> Show Preview (20 rows)';
        }
        renderCurrentView();
        return;
    }

    const matches = [];
    const matchIndexes = [];
    allDataRows.forEach((row, idx) => {
        const pass = activeFilters.every(filter => rowMatchesFilter(row, filter));
        if (pass) {
            matches.push(row);
            matchIndexes.push(idx);
        }
    });
    filteredRows = matches;
    filteredRowIndexes = matchIndexes;
    updateFilterPills();
    removeUMAPHighlight();
    updateUMAPFilter();
    renderActiveFilters();
    const totalRows = matches.length;
    currentDisplayMode = totalRows > PREVIEW_ROW_COUNT ? 'preview' : 'all';
    const toggleButton = document.getElementById('toggle-data-view');
    if (toggleButton) {
        toggleButton.innerHTML = currentDisplayMode === 'preview'
            ? '<i class="fa-solid fa-expand"></i> View all rows'
            : '<i class="fa-solid fa-compress"></i> Show Preview (20 rows)';
    }
    renderCurrentView();
}

function addFilter() {
    const columnSelect = document.getElementById('filter-column');
    const operatorSelect = document.getElementById('filter-operator');
    const valueInput = document.getElementById('filter-value');
    const valueMaxInput = document.getElementById('filter-value-max');
    if (!columnSelect || !operatorSelect) return;
    const columnName = columnSelect.value;
    const columnIndex = allHeaders.indexOf(columnName);
    if (columnIndex < 0) return;
    const operator = operatorSelect.value;
    const operatorConfig = FILTER_OPERATORS.find(op => op.value === operator);
    const noValue = operatorConfig?.noValue ?? false;
    const value = valueInput ? valueInput.value.trim() : '';
    const valueMax = valueMaxInput ? valueMaxInput.value.trim() : '';
    const isBetween = operator === 'between';
    if (!noValue) {
        if (!value) return;
        if (isBetween && !valueMax) return;
    }
    const numeric = columnIndex >= 0 ? isNumericColumn(columnIndex) : false;
    const displayValue = noValue ? '' : (isBetween ? `${value} to ${valueMax}` : value);
    activeFilters.push({
        id: `filter-${nextFilterId++}`,
        columnIndex,
        columnName,
        operator,
        operatorLabel: operatorConfig?.label ?? operator,
        value,
        valueMax,
        isNumeric: numeric,
        displayValue
    });
    if (valueInput) valueInput.value = '';
    if (valueMaxInput) valueMaxInput.value = '';
    applyFilters();
}

function removeFilter(id) {
    activeFilters = activeFilters.filter(filter => filter.id !== id);
    applyFilters();
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
        populateFilterColumnSelector(allHeaders);
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

    const filterColumn = document.getElementById('filter-column');
    if (filterColumn) {
        filterColumn.addEventListener('change', (event) => {
            updateFilterOperatorOptions(event.target.value);
        });
    }

    const filterOperator = document.getElementById('filter-operator');
    if (filterOperator) {
        filterOperator.addEventListener('change', () => {
            syncFilterValueInputs();
        });
    }

    const addFilterButton = document.getElementById('add-filter');
    if (addFilterButton) {
        addFilterButton.addEventListener('click', addFilter);
    }

    const clearFiltersButton = document.getElementById('clear-filters');
    if (clearFiltersButton) {
        clearFiltersButton.addEventListener('click', () => {
            activeFilters = [];
            filteredRows = null;
            filteredRowIndexes = null;
            applyFilters();
        });
    }

    const activeFiltersList = document.getElementById('active-filters');
    if (activeFiltersList) {
        activeFiltersList.addEventListener('click', (event) => {
            const target = event.target.closest('[data-filter-remove]');
            if (!target) return;
            const filterId = target.getAttribute('data-filter-remove');
            if (filterId) removeFilter(filterId);
        });
    }

    initMetricTooltips();
    renderActiveFilters();
    updateFilterPills();

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
