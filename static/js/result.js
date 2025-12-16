// Interactive features for the result page

let umapData = null;
let currentHoveredRow = null;
let allHeaders = [];
let allDataRows = [];
let selectedColumns = [];

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

// Capture the initially rendered preview so we have something to display before the full dataset loads
function captureInitialTableData() {
    const headerCells = document.querySelectorAll('.data-preview-table thead th');
    const bodyRows = document.querySelectorAll('.data-preview-table tbody tr');

    if (!headerCells.length || !bodyRows.length) return;

    allHeaders = Array.from(headerCells).map(cell => cell.textContent || '');
    allDataRows = Array.from(bodyRows).map(row =>
        Array.from(row.querySelectorAll('td')).map(cell => cell.textContent || '')
    );

    if (!selectedColumns.length) {
        selectedColumns = allHeaders.map((_, index) => index);
    }

    renderColumnSelector();
    updateRowCountDisplay();
}

// Render the table using the selected columns
function renderTable() {
    const table = document.querySelector('.data-preview-table');
    if (!table || !allHeaders.length) return;

    // Ensure at least one column is selected
    if (!selectedColumns.length) {
        selectedColumns = allHeaders.map((_, index) => index);
    }

    const tableHeadRow = table.querySelector('thead tr');
    const tableBody = table.querySelector('tbody');

    if (!tableHeadRow || !tableBody) return;

    tableHeadRow.innerHTML = '';
    selectedColumns.forEach(index => {
        const th = document.createElement('th');
        th.textContent = allHeaders[index];
        tableHeadRow.appendChild(th);
    });

    tableBody.innerHTML = '';
    allDataRows.forEach(row => {
        const tr = document.createElement('tr');
        selectedColumns.forEach(columnIndex => {
            const td = document.createElement('td');
            td.textContent = row[columnIndex] ?? '';
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });

    updateRowCountDisplay();
    attachTableHoverListeners();
}

// Update the row count and column selection display
function updateRowCountDisplay() {
    const rowCountDisplay = document.getElementById('row-count-display');
    if (!rowCountDisplay) return;

    const totalRows = allDataRows.length;
    const columnSummary = `${selectedColumns.length}/${allHeaders.length} columns`;
    rowCountDisplay.textContent = `Showing ${totalRows} rows • ${columnSummary}`;
}

function renderColumnSelector() {
    const menu = document.getElementById('column-selector-menu');
    if (!menu || !allHeaders.length) return;

    menu.innerHTML = '';

    allHeaders.forEach((header, index) => {
        const option = document.createElement('label');
        option.className = 'column-selector-option';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = index;
        checkbox.checked = selectedColumns.includes(index);
        checkbox.addEventListener('change', (event) => {
            updateSelectedColumns(index, event.target.checked);
        });

        const text = document.createElement('span');
        text.textContent = header;

        option.appendChild(checkbox);
        option.appendChild(text);
        menu.appendChild(option);
    });
}

function updateSelectedColumns(columnIndex, isChecked) {
    if (isChecked && !selectedColumns.includes(columnIndex)) {
        selectedColumns.push(columnIndex);
    } else if (!isChecked && selectedColumns.includes(columnIndex)) {
        if (selectedColumns.length === 1) {
            return; // Prevent removing the last remaining column
        }
        selectedColumns = selectedColumns.filter(index => index !== columnIndex);
    }

    selectedColumns.sort((a, b) => a - b);

    renderColumnSelector();
    renderTable();
}

// Load full dataset via API
async function loadFullDataset(token) {
    try {
        const response = await fetch(`/synthetic/api/dataset/${token}/`);
        if (!response.ok) {
            throw new Error('Failed to load full dataset');
        }
        const data = await response.json();
        const previousHeaders = selectedColumns.map(index => allHeaders[index]);

        allHeaders = data.headers || [];
        allDataRows = data.rows || [];

        if (previousHeaders.length) {
            selectedColumns = allHeaders.reduce((acc, header, index) => {
                if (previousHeaders.includes(header)) {
                    acc.push(index);
                }
                return acc;
            }, []);
        }

        if (!selectedColumns.length) {
            selectedColumns = allHeaders.map((_, index) => index);
        }

        renderColumnSelector();
        renderTable();
    } catch (error) {
        console.error('Error loading full dataset:', error);
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

    // Capture the initially rendered preview
    captureInitialTableData();

    // Attach hover listeners to table rows
    attachTableHoverListeners();

    // Load full dataset so the preview shows every row
    if (runToken) {
        loadFullDataset(runToken);
    }

    // Attach click handler to column selector toggle
    const columnSelector = document.getElementById('column-selector');
    const columnToggleButton = document.getElementById('column-selector-toggle');
    const columnMenu = document.getElementById('column-selector-menu');

    if (columnSelector && columnToggleButton && columnMenu) {
        columnToggleButton.addEventListener('click', (event) => {
            event.preventDefault();
            columnMenu.classList.toggle('open');
        });

        document.addEventListener('click', (event) => {
            if (!columnSelector.contains(event.target)) {
                columnMenu.classList.remove('open');
            }
        });
    }
});
