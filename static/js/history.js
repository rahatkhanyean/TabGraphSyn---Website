/**
 * TabGraphSyn History Page JavaScript
 * Handles real-time job status polling and progress display
 */

(function () {
    'use strict';

    // ========================================================================
    // Utility Functions
    // ========================================================================

    const getCookie = (name) => {
        const value = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
        return value ? decodeURIComponent(value[1]) : null;
    };

    // ========================================================================
    // Configuration
    // ========================================================================

    const config = {
        csrfToken: getCookie('csrftoken'),
        pollInterval: 2000, // Poll every 2 seconds
        activeJobs: new Map(), // Map of token -> polling timer
    };

    // ========================================================================
    // Job Status Tracking
    // ========================================================================

    const createProgressBar = (percentage, stage, message) => {
        const statusText = stage ? stage.replace(/_/g, ' ').replace(/^(.)/, (match) => match.toUpperCase()) : 'Running';
        return `
            <div class="job-progress">
                <div class="job-progress-header">
                    <span class="job-progress-stage">${statusText}</span>
                    <span class="job-progress-percentage">${percentage}%</span>
                </div>
                <div class="job-progress-bar">
                    <div class="job-progress-fill" style="width: ${percentage}%"></div>
                </div>
                <div class="job-progress-message">${message || 'Processing...'}</div>
            </div>
        `;
    };

    const updateJobStatus = (token, row) => {
        fetch(`/api/run-status/${token}/`, {
            headers: { 'Cache-Control': 'no-store' }
        })
            .then(response => response.json())
            .then(data => {
                const progressCell = row.querySelector('.job-progress-cell');
                if (!progressCell) return;

                const percentage = data.progressPercentage || 0;
                const stage = data.stage || 'queued';
                const message = data.message || 'Processing...';

                // Update progress bar
                progressCell.innerHTML = createProgressBar(percentage, stage, message);

                // If job is completed or failed, stop polling
                if (stage === 'completed' || stage === 'failed') {
                    stopPolling(token);

                    // If completed, reload the page once to remove active job section
                    if (stage === 'completed' && data.resultToken) {
                        setTimeout(() => {
                            window.location.reload();
                        }, 1500);
                    } else if (stage === 'completed') {
                        // Job completed but no result token yet, keep the progress bar visible
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    }
                }
            })
            .catch(error => {
                console.error(`Error polling job ${token}:`, error);
                // Don't stop polling on error, might be temporary
            });
    };

    const startPolling = (token, row) => {
        if (config.activeJobs.has(token)) return; // Already polling

        // Initial update
        updateJobStatus(token, row);

        // Set up interval
        const timerId = setInterval(() => {
            updateJobStatus(token, row);
        }, config.pollInterval);

        config.activeJobs.set(token, timerId);
    };

    const stopPolling = (token) => {
        const timerId = config.activeJobs.get(token);
        if (timerId) {
            clearInterval(timerId);
            config.activeJobs.delete(token);
        }
    };

    // ========================================================================
    // Initialization
    // ========================================================================

    const init = () => {
        // Find all rows that might have active jobs
        const rows = document.querySelectorAll('[data-job-token]');

        rows.forEach(row => {
            const token = row.dataset.jobToken;
            if (token) {
                startPolling(token, row);
            }
        });
    };

    // ========================================================================
    // Page Load
    // ========================================================================

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Clean up on page unload
    window.addEventListener('beforeunload', () => {
        config.activeJobs.forEach((timerId, token) => {
            clearInterval(timerId);
        });
        config.activeJobs.clear();
    });
})();
