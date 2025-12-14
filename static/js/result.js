// Interactive features for the result page

let umapData = null;
let currentHoveredRow = null;
let allDataRows = [];
let currentDisplayMode = 'preview'; // 'preview' or 'all'

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

// Toggle between preview (20 rows) and all data view
function toggleDataView() {
    const tableBody = document.querySelector('.data-preview-table tbody');
    const toggleButton = document.getElementById('toggle-data-view');

    if (!tableBody || !toggleButton) return;

    if (currentDisplayMode === 'preview') {
        // Show all data
        renderAllData();
        currentDisplayMode = 'all';
        toggleButton.textContent = 'Show Preview (20 rows)';
        toggleButton.innerHTML = '<i class="fa-solid fa-compress"></i> Show Preview (20 rows)';
    } else {
        // Show preview only
        renderPreviewData();
        currentDisplayMode = 'preview';
        toggleButton.innerHTML = '<i class="fa-solid fa-expand"></i> View All Data';
    }

    // Re-attach hover listeners after re-rendering
    attachTableHoverListeners();
}

// Render all data rows in the table
function renderAllData() {
    const tableBody = document.querySelector('.data-preview-table tbody');
    if (!tableBody || !allDataRows || allDataRows.length === 0) return;

    tableBody.innerHTML = '';

    allDataRows.forEach(row => {
        const tr = document.createElement('tr');
        row.forEach(cell => {
            const td = document.createElement('td');
            td.textContent = cell;
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });

    updateRowCountDisplay();
}

// Render preview data (first 20 rows)
function renderPreviewData() {
    const tableBody = document.querySelector('.data-preview-table tbody');
    if (!tableBody || !allDataRows || allDataRows.length === 0) return;

    tableBody.innerHTML = '';

    const previewRows = allDataRows.slice(0, 20);
    previewRows.forEach(row => {
        const tr = document.createElement('tr');
        row.forEach(cell => {
            const td = document.createElement('td');
            td.textContent = cell;
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });

    updateRowCountDisplay();
}

// Update the row count display
function updateRowCountDisplay() {
    const cardTitle = document.querySelector('.data-card .card-title');
    if (!cardTitle) return;

    const totalRows = allDataRows.length;
    const displayedRows = currentDisplayMode === 'preview' ? Math.min(20, totalRows) : totalRows;

    if (currentDisplayMode === 'preview' && totalRows > 20) {
        cardTitle.innerHTML = `Preview (showing ${displayedRows} of ${totalRows} rows)`;
    } else {
        cardTitle.innerHTML = `Data Preview (${displayedRows} rows)`;
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
        allDataRows = data.rows;

        // Enable the "View All" button
        const toggleButton = document.getElementById('toggle-data-view');
        if (toggleButton && allDataRows.length > 20) {
            toggleButton.disabled = false;
            toggleButton.style.display = 'inline-flex';
        }
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

    // Attach hover listeners to table rows
    attachTableHoverListeners();

    // Load full dataset for "View All" functionality
    if (runToken) {
        loadFullDataset(runToken);
    }

    // Attach click handler to toggle button
    const toggleButton = document.getElementById('toggle-data-view');
    if (toggleButton) {
        toggleButton.addEventListener('click', toggleDataView);
    }
});
