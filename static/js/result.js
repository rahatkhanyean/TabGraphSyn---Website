// Interactive features for the result page

let umapData = null;
let currentHoveredRow = null;
let allDataRows = [];
let datasetHeaders = [];
let selectedColumns = new Set();
let columnSelectorInitialized = false;

// Initialize interactive UMAP plot with Plotly
function initializeInteractiveUMAP(umapCoordinates, labels) {
    if (!umapCoordinates || umapCoordinates.length === 0) {
        console.warn('No UMAP coordinates available for interactive plot');
        return;
    }

    umapData = umapCoordinates;

    // Separate real and synthetic data points
    const realPoints = umapCoordinates.filter(point => point.type === 'real');
    const syntheticPoints = umapCoordinates.filter(point => point.type === 'synthetic');

    const realTrace = {
        x: realPoints.map(p => p.x),
        y: realPoints.map(p => p.y),
        mode: 'markers',
        type: 'scatter',
        name: 'Real Data',
        marker: {
            color: '#3b82f6',
            size: 8,
            opacity: 0.6,
            line: {
                color: '#1e40af',
                width: 1
            }
        },
        hovertemplate: '<b>Real Data</b><br>Index: %{customdata}<br>x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>',
        customdata: realPoints.map(p => p.index)
    };

    const syntheticTrace = {
        x: syntheticPoints.map(p => p.x),
        y: syntheticPoints.map(p => p.y),
        mode: 'markers',
        type: 'scatter',
        name: 'Synthetic Data',
        marker: {
            color: '#22c55e',
            size: 8,
            opacity: 0.6,
            line: {
                color: '#15803d',
                width: 1
            }
        },
        hovertemplate: '<b>Synthetic Data</b><br>Row: %{customdata}<br>x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>',
        customdata: syntheticPoints.map(p => p.index),
        ids: syntheticPoints.map(p => `synthetic-${p.index}`)
    };

    const layout = {
        title: {
            text: 'UMAP Projection - Real vs Synthetic Data',
            font: {
                family: 'Inter, sans-serif',
                size: 18,
                weight: 600
            }
        },
        xaxis: {
            title: 'UMAP Dimension 1',
            gridcolor: 'rgba(148, 163, 184, 0.1)',
            zeroline: false
        },
        yaxis: {
            title: 'UMAP Dimension 2',
            gridcolor: 'rgba(148, 163, 184, 0.1)',
            zeroline: false
        },
        hovermode: 'closest',
        showlegend: true,
        legend: {
            x: 1,
            xanchor: 'right',
            y: 1,
            bgcolor: 'rgba(255, 255, 255, 0.9)',
            bordercolor: 'rgba(148, 163, 184, 0.3)',
            borderwidth: 1
        },
        plot_bgcolor: '#ffffff',
        paper_bgcolor: '#ffffff',
        margin: {
            l: 60,
            r: 20,
            t: 60,
            b: 60
        }
    };

    const config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        displaylogo: false
    };

    const plotDiv = document.getElementById('interactive-umap-plot');
    if (plotDiv) {
        Plotly.newPlot(plotDiv, [realTrace, syntheticTrace], layout, config);
    }
}

// Highlight a specific point in the UMAP plot
function highlightUMAPPoint(rowIndex) {
    if (!umapData || rowIndex === null) {
        return;
    }

    const syntheticPoint = umapData.find(p => p.type === 'synthetic' && p.index === rowIndex);

    if (!syntheticPoint) {
        return;
    }

    const highlightTrace = {
        x: [syntheticPoint.x],
        y: [syntheticPoint.y],
        mode: 'markers',
        type: 'scatter',
        name: 'Highlighted',
        marker: {
            color: '#f59e0b',
            size: 16,
            opacity: 1,
            line: {
                color: '#d97706',
                width: 3
            },
            symbol: 'star'
        },
        hovertemplate: '<b>Highlighted Row</b><br>Row: %{customdata}<br>x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>',
        customdata: [rowIndex],
        showlegend: false
    };

    const plotDiv = document.getElementById('interactive-umap-plot');
    if (plotDiv && plotDiv.data) {
        // Remove previous highlight (trace index 2 if exists)
        if (plotDiv.data.length > 2) {
            Plotly.deleteTraces(plotDiv, 2);
        }
        // Add new highlight
        Plotly.addTraces(plotDiv, highlightTrace);
    }
}

// Remove highlight from UMAP plot
function removeUMAPHighlight() {
    const plotDiv = document.getElementById('interactive-umap-plot');
    if (plotDiv && plotDiv.data && plotDiv.data.length > 2) {
        Plotly.deleteTraces(plotDiv, 2);
    }
}

// Attach hover event listeners to table rows
function attachTableHoverListeners() {
    const tableBody = document.querySelector('.data-preview-table tbody');
    if (!tableBody) return;

    const rows = tableBody.querySelectorAll('tr');
    rows.forEach((row, index) => {
        row.addEventListener('mouseenter', function() {
            currentHoveredRow = index;
            this.classList.add('row-highlighted');
            highlightUMAPPoint(index);
        });

        row.addEventListener('mouseleave', function() {
            currentHoveredRow = null;
            this.classList.remove('row-highlighted');
            removeUMAPHighlight();
        });
    });
}

function getVisibleColumnIndices() {
    return datasetHeaders
        .map((header, index) => (selectedColumns.has(header) ? index : null))
        .filter(index => index !== null);
}

function renderTable() {
    const tableHeadRow = document.querySelector('.data-preview-table thead tr');
    const tableBody = document.querySelector('.data-preview-table tbody');

    if (!tableHeadRow || !tableBody || !datasetHeaders.length) return;

    const visibleIndices = getVisibleColumnIndices();
    const hasVisibleColumns = visibleIndices.length > 0;

    tableHeadRow.innerHTML = '';
    if (!hasVisibleColumns) {
        const th = document.createElement('th');
        th.textContent = 'No columns selected';
        tableHeadRow.appendChild(th);
    } else {
        visibleIndices.forEach(index => {
            const th = document.createElement('th');
            th.textContent = datasetHeaders[index];
            tableHeadRow.appendChild(th);
        });
    }

    tableBody.innerHTML = '';
    allDataRows.forEach(row => {
        const tr = document.createElement('tr');
        if (hasVisibleColumns) {
            visibleIndices.forEach(index => {
                const td = document.createElement('td');
                td.textContent = row[index] ?? '';
                tr.appendChild(td);
            });
        } else {
            const td = document.createElement('td');
            td.textContent = 'Select at least one column to view data.';
            td.colSpan = Math.max(datasetHeaders.length, 1);
            tr.appendChild(td);
        }
        tableBody.appendChild(tr);
    });

    updateRowCountDisplay();
    attachTableHoverListeners();
}

// Update the row count display
function updateRowCountDisplay() {
    const cardTitle = document.querySelector('.data-card .card-title');
    const columnCountBadge = document.getElementById('column-selector-count');
    if (!cardTitle) return;

    const totalRows = allDataRows.length;
    cardTitle.innerHTML = `Preview (${totalRows} rows)`;

    if (columnCountBadge) {
        const count = selectedColumns.size;
        columnCountBadge.textContent = count === datasetHeaders.length ? 'All' : `${count} selected`;
    }
}

// Load full dataset via API
async function loadFullDataset(token) {
    try {
        const response = await fetch(`/synthetic/api/dataset/${token}/`);
        if (!response.ok) {
            throw new Error('Failed to load full dataset');
        }
        const data = await response.json();
        datasetHeaders = data.headers || [];
        allDataRows = data.rows || [];
        selectedColumns = new Set(datasetHeaders);
        buildColumnSelector(datasetHeaders);
        renderTable();
    } catch (error) {
        console.error('Error loading full dataset:', error);
    }
}

function initializeFromExistingTable() {
    const headerCells = document.querySelectorAll('.data-preview-table thead th');
    datasetHeaders = Array.from(headerCells).map(cell => cell.textContent.trim());
    if (datasetHeaders.length) {
        selectedColumns = new Set(datasetHeaders);
    }

    const rowElements = document.querySelectorAll('.data-preview-table tbody tr');
    allDataRows = Array.from(rowElements).map(row => Array.from(row.querySelectorAll('td')).map(cell => cell.textContent));
}

function buildColumnSelector(headers) {
    const menu = document.getElementById('column-selector-menu');
    const optionsContainer = menu ? menu.querySelector('.column-selector-options') : null;
    if (!menu || !optionsContainer) return;

    optionsContainer.innerHTML = '';
    headers.forEach(header => {
        const label = document.createElement('label');
        label.className = 'column-selector-option';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.name = 'column';
        checkbox.value = header;
        checkbox.checked = true;
        const span = document.createElement('span');
        span.textContent = header;
        label.appendChild(checkbox);
        label.appendChild(span);
        optionsContainer.appendChild(label);
    });

    attachColumnSelectorEvents();
    updateRowCountDisplay();
}

function attachColumnSelectorEvents() {
    const menu = document.getElementById('column-selector-menu');
    const toggle = document.getElementById('column-selector-toggle');
    const selectAllBtn = document.getElementById('column-select-all');
    const clearAllBtn = document.getElementById('column-clear-all');

    if (!menu || !toggle || columnSelectorInitialized) return;
    columnSelectorInitialized = true;

    toggle.addEventListener('click', () => {
        const isExpanded = menu.getAttribute('aria-expanded') === 'true';
        menu.setAttribute('aria-expanded', (!isExpanded).toString());
    });

    document.addEventListener('click', event => {
        if (!menu.contains(event.target) && !toggle.contains(event.target)) {
            menu.setAttribute('aria-expanded', 'false');
        }
    });

    menu.addEventListener('change', event => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;

        if (!target.checked && selectedColumns.size <= 1) {
            target.checked = true;
            return;
        }

        if (target.checked) {
            selectedColumns.add(target.value);
        } else {
            selectedColumns.delete(target.value);
        }
        renderTable();
    });

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            selectedColumns = new Set(datasetHeaders);
            menu.querySelectorAll('input[type="checkbox"]').forEach(input => {
                input.checked = true;
            });
            renderTable();
        });
    }

    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', () => {
            if (!datasetHeaders.length) return;
            selectedColumns = new Set([datasetHeaders[0]]);
            menu.querySelectorAll('input[type="checkbox"]').forEach((input, index) => {
                input.checked = index === 0;
            });
            renderTable();
        });
    }
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the result page
    const resultPage = document.querySelector('.result-layout');
    if (!resultPage) return;

    // Get the run token from the page
    const tokenElement = document.querySelector('[data-run-token]');
    const runToken = tokenElement ? tokenElement.getAttribute('data-run-token') : null;

    // Load UMAP data if available
    const umapDataElement = document.getElementById('umap-data');
    if (umapDataElement) {
        try {
            const umapCoordinates = JSON.parse(umapDataElement.textContent);
            initializeInteractiveUMAP(umapCoordinates);
        } catch (error) {
            console.error('Error parsing UMAP data:', error);
        }
    }

    initializeFromExistingTable();
    buildColumnSelector(datasetHeaders);
    attachTableHoverListeners();

    if (runToken) {
        loadFullDataset(runToken);
    }
});
