/**
 * Product Management Workflow JavaScript
 * Handles the product discovery workflow interactions
 */

// Workflow step types
const WORKFLOW_STEPS = {
    VISION: 'vision',
    INITIATIVE: 'initiative',
    PORTFOLIO: 'portfolio',
    PRODUCT: 'product',
    FEATURE: 'feature'
};

// Workflow step configuration
const STEP_CONFIG = {
    vision: {
        icon: 'fa-eye',
        color: '#8B5CF6',
        title: 'Vision',
        description: 'Define the strategic goals and long-term vision'
    },
    initiative: {
        icon: 'fa-flag',
        color: '#3B82F6',
        title: 'Initiative',
        description: 'Break down vision into actionable initiatives'
    },
    portfolio: {
        icon: 'fa-folder',
        color: '#14B8A6',
        title: 'Portfolio',
        description: 'Organize products working toward the initiative'
    },
    product: {
        icon: 'fa-box',
        color: '#EC4899',
        title: 'Product',
        description: 'Define specific products or services'
    },
    feature: {
        icon: 'fa-puzzle-piece',
        color: '#F59E0B',
        title: 'Feature',
        description: 'Specify individual features of products'
    }
};

/**
 * Get CSRF token from cookies
 */
function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Show loading state
 */
function showLoading(element, message = 'Loading...') {
    const spinner = '<span class="spinner-border spinner-border-sm me-2"></span>';
    element.innerHTML = spinner + message;
    element.disabled = true;
}

/**
 * Reset button state
 */
function resetButton(element, originalContent) {
    element.innerHTML = originalContent;
    element.disabled = false;
}

/**
 * Display error message
 */
function showError(message) {
    alert('Error: ' + message);
}

/**
 * Display success message
 */
function showSuccess(message) {
    // You can replace this with a toast notification system
    alert(message);
}

/**
 * Format date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Validate step transition
 * Ensures workflow follows the correct order
 */
function validateStepTransition(currentStep, nextStep) {
    const stepOrder = ['vision', 'initiative', 'portfolio', 'product', 'feature'];
    const currentIndex = stepOrder.indexOf(currentStep);
    const nextIndex = stepOrder.indexOf(nextStep);

    if (nextIndex < 0) {
        return { valid: false, error: 'Invalid step type' };
    }

    // Allow creating any step for now, but warn if skipping
    if (nextIndex > currentIndex + 1) {
        return {
            valid: true,
            warning: `You are skipping ${stepOrder[currentIndex + 1]}. Consider following the workflow order.`
        };
    }

    return { valid: true };
}

/**
 * Initialize workflow visualization
 */
function initializeWorkflowVisualization() {
    const workflowSteps = document.querySelectorAll('.workflow-step');

    workflowSteps.forEach(step => {
        step.addEventListener('click', function() {
            const stepId = this.dataset.stepId;
            if (stepId) {
                window.location.href = `/product-management/workflow/${stepId}/`;
            }
        });
    });
}

/**
 * Auto-save conversation
 */
let autoSaveTimer = null;
function scheduleAutoSave(callback, delay = 3000) {
    if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
    }
    autoSaveTimer = setTimeout(callback, delay);
}

/**
 * Export workflow data
 */
function exportWorkflowData(projectId) {
    fetch(`/product-management/project/${projectId}/export/`)
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `project-${projectId}-export.json`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        })
        .catch(error => {
            showError('Failed to export workflow data: ' + error);
        });
}

// Export functions for use in templates
window.ProductManagement = {
    getCsrfToken,
    showLoading,
    resetButton,
    showError,
    showSuccess,
    formatDate,
    validateStepTransition,
    initializeWorkflowVisualization,
    exportWorkflowData,
    WORKFLOW_STEPS,
    STEP_CONFIG
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Product Management Workflow initialized');
    initializeWorkflowVisualization();
});
