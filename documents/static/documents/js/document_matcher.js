/**
 * Document Matcher
 *
 * This script handles matching documents to purchase orders.
 */

class DocumentMatcher {
    constructor(options = {}) {
        this.options = Object.assign({
            documentId: null,
            ajaxUrl: '/documents/ajax/match-document-to-order/',
            csrfToken: document.querySelector('meta[name="csrf-token"]')?.getAttribute('content'),
            onMatch: null
        }, options);

        // Check required options
        if (!this.options.documentId) {
            console.error('Document ID is required');
            return;
        }

        this.init();
    }

    /**
     * Initialize the matcher
     */
    init() {
        // Find elements - updated to use Django-generated IDs
        this.purchaseOrderSelect = document.getElementById('id_purchase_order');
        this.matchButton = document.getElementById('match-document-button');
        this.notesTextarea = document.getElementById('id_notes');
        this.matchResult = document.getElementById('match-result');

        if (this.matchButton) {
            this.matchButton.addEventListener('click', () => this.matchDocument());
        }
    }

    /**
     * Match document to selected purchase order
     */
    matchDocument() {
        if (!this.purchaseOrderSelect) {
            console.error('Purchase order select not found');
            return;
        }

        const purchaseOrderId = this.purchaseOrderSelect.value;
        if (!purchaseOrderId) {
            this.showError('Please select a purchase order');
            return;
        }

        // Show spinner
        this.matchButton.disabled = true;
        this.matchButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Matching...';

        // Create payload
        const payload = {
            purchase_order_id: purchaseOrderId,
            notes: this.notesTextarea ? this.notesTextarea.value : ''
        };

        // Send match request
        fetch(`${this.options.ajaxUrl}${this.options.documentId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.options.csrfToken
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                this.showError(data.error);
                return;
            }

            this.showSuccess(data.purchase_order);

            // Callback
            if (this.options.onMatch) {
                this.options.onMatch(data);
            }
        })
        .catch(error => {
            this.showError('An error occurred while matching the document');
            console.error('Error matching document:', error);
        })
        .finally(() => {
            // Reset button
            this.matchButton.disabled = false;
            this.matchButton.innerHTML = '<i class="bi bi-link"></i> Match Document';
        });
    }

    /**
     * Show error message
     */
    showError(message) {
        if (this.matchResult) {
            this.matchResult.innerHTML = `
                <div class="alert alert-danger mt-3">
                    <i class="bi bi-exclamation-triangle-fill"></i> ${message}
                </div>
            `;
        }
    }

    /**
     * Show success message
     */
    showSuccess(purchaseOrder) {
        if (this.matchResult) {
            this.matchResult.innerHTML = `
                <div class="alert alert-success mt-3">
                    <i class="bi bi-check-circle-fill"></i> Document successfully matched to purchase order ${purchaseOrder}.
                </div>
            `;
        }
    }
}

// Initialize document matcher when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if matcher container exists
    const matcherContainer = document.getElementById('document-matcher');
    if (!matcherContainer) return;

    // Get document ID from data attribute
    const documentId = matcherContainer.dataset.documentId;

    if (!documentId) {
        console.error('Document ID is required');
        return;
    }

    // Initialize matcher
    const matcher = new DocumentMatcher({
        documentId: documentId,
        onMatch: function(data) {
            console.log('Document matched:', data);
            // Redirect to document detail page after a short delay
            setTimeout(() => {
                window.location.href = `/documents/${documentId}/`;
            }, 2000);
        }
    });
});