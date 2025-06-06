/**
 * Enhanced Field Editor for Document Template Mapping
 */

// Main editor class
class FieldEditor {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container with ID ${containerId} not found`);
            return;
        }

        // Initialize options with defaults
        this.options = Object.assign({
            documentId: null,
            templateId: null,
            documentType: null, // Document type code for standard fields
            ajaxUrls: {
                getDocumentImage: '/documents/ajax/get-document-image/',
                getDocumentOcrData: '/documents/ajax/get-document-ocr-data/',
                saveFieldCoordinates: '/documents/ajax/save-field-coordinates/',
                extractFieldValue: '/documents/ajax/extract-field-value/',
                getStandardFields: '/documents/ajax/get-standard-fields/' // API for standard fields
            },
            csrfToken: document.querySelector('meta[name="csrf-token"]')?.getAttribute('content'),
            onFieldSaved: null,
            onFieldExtracted: null
        }, options);

        // Check required options
        if (!this.options.documentId) {
            console.error('Document ID is required');
            return;
        }

        // Editor state
        this.state = {
            currentPage: 1,
            totalPages: 1,
            scale: 1,
            drawing: false,
            currentField: null,
            fields: options.fields || [],
            mode: 'view', // 'view', 'create', 'edit'
            standardFields: [] // Array to store standard fields by document type
        };

        // DOM elements
        this.elements = {
            canvasContainer: null,
            canvas: null,
            context: null,
            imageLayer: null,
            fieldLayer: null,
            ocrLayer: null,
            controls: null,
            pageControls: null,
            fieldControls: null,
            zoomControls: null
        };

        // OCR data
        this.ocrData = null;

        // Document dimensions
        this.documentDimensions = {
            width: 0,
            height: 0
        };

        // Store the current text selection from rectangle
        this.selectedText = '';

        // Make the editor instance available globally
        window.editorInstance = this;

        // Initialize the editor
        this.init();
    }

    /**
     * Initialize the editor components
     */
    init() {
        // Create the editor structure
        this.createEditorStructure();

        // Initialize event listeners
        this.initEventListeners();

        // Load the document
        this.loadDocument();

        // Load existing fields if template ID is provided
        if (this.options.templateId && this.state.fields.length === 0) {
            this.loadFields();
        }
    }

    /**
     * Create the editor DOM structure
     */
    createEditorStructure() {
        // Clear the container
        this.container.innerHTML = '';

        // Add editor classes
        this.container.classList.add('document-field-editor');

        // Create canvas container
        this.elements.canvasContainer = document.createElement('div');
        this.elements.canvasContainer.className = 'editor-canvas-container';
        this.container.appendChild(this.elements.canvasContainer);

        // Create layers
        this.createImageLayer();
        this.createFieldLayer();
        this.createOcrLayer();

        // Create controls
        this.createControls();
    }

    /**
     * Create the image layer for displaying the document
     */
    createImageLayer() {
        this.elements.imageLayer = document.createElement('div');
        this.elements.imageLayer.className = 'editor-layer image-layer';
        this.elements.canvasContainer.appendChild(this.elements.imageLayer);

        // Create image element
        const img = document.createElement('img');
        img.className = 'editor-document-image';
        img.alt = 'Document page';
        this.elements.imageLayer.appendChild(img);
    }

    /**
     * Create the field layer for displaying and editing fields
     */
    createFieldLayer() {
        this.elements.fieldLayer = document.createElement('div');
        this.elements.fieldLayer.className = 'editor-layer field-layer';
        this.elements.canvasContainer.appendChild(this.elements.fieldLayer);

        // Create canvas for drawing
        this.elements.canvas = document.createElement('canvas');
        this.elements.canvas.className = 'editor-canvas';
        // Make sure the canvas covers the entire area
        this.elements.canvas.style.width = "100%";
        this.elements.canvas.style.height = "100%";
        this.elements.fieldLayer.appendChild(this.elements.canvas);

        // Get context
        this.elements.context = this.elements.canvas.getContext('2d');
    }

    /**
     * Create the OCR layer for displaying OCR data
     */
    createOcrLayer() {
        this.elements.ocrLayer = document.createElement('div');
        this.elements.ocrLayer.className = 'editor-layer ocr-layer';
        this.elements.canvasContainer.appendChild(this.elements.ocrLayer);
    }

    /**
     * Create the editor controls
     */
    createControls() {
        this.elements.controls = document.createElement('div');
        this.elements.controls.className = 'editor-controls';
        this.container.appendChild(this.elements.controls);

        // Create page controls
        this.createPageControls();

        // Create field controls
        this.createFieldControls();

        // Create zoom controls
        this.createZoomControls();
    }

    /**
     * Create page navigation controls
     */
    createPageControls() {
        this.elements.pageControls = document.createElement('div');
        this.elements.pageControls.className = 'editor-page-controls';
        this.elements.controls.appendChild(this.elements.pageControls);

        // Previous page button
        const prevButton = document.createElement('button');
        prevButton.type = 'button';
        prevButton.className = 'btn btn-outline-secondary btn-sm';
        prevButton.innerHTML = '<i class="bi bi-chevron-left"></i> Previous';
        prevButton.addEventListener('click', () => this.previousPage());
        this.elements.pageControls.appendChild(prevButton);

        // Page indicator
        const pageIndicator = document.createElement('span');
        pageIndicator.className = 'page-indicator mx-2';
        pageIndicator.textContent = `Page ${this.state.currentPage} of ${this.state.totalPages}`;
        this.elements.pageControls.appendChild(pageIndicator);

        // Next page button
        const nextButton = document.createElement('button');
        nextButton.type = 'button';
        nextButton.className = 'btn btn-outline-secondary btn-sm';
        nextButton.innerHTML = 'Next <i class="bi bi-chevron-right"></i>';
        nextButton.addEventListener('click', () => this.nextPage());
        this.elements.pageControls.appendChild(nextButton);
    }

    /**
     * Create field editing controls
     */
    createFieldControls() {
        this.elements.fieldControls = document.createElement('div');
        this.elements.fieldControls.className = 'editor-field-controls';
        this.elements.controls.appendChild(this.elements.fieldControls);

        // Create new field button
        const newFieldButton = document.createElement('button');
        newFieldButton.type = 'button';
        newFieldButton.className = 'btn btn-primary btn-sm';
        newFieldButton.innerHTML = '<i class="bi bi-plus-lg"></i> Add Field';
        newFieldButton.addEventListener('click', () => this.startFieldCreation());
        this.elements.fieldControls.appendChild(newFieldButton);

        // Toggle OCR overlay button
        const toggleOcrButton = document.createElement('button');
        toggleOcrButton.type = 'button';
        toggleOcrButton.className = 'btn btn-outline-info btn-sm ms-2';
        toggleOcrButton.innerHTML = '<i class="bi bi-text-paragraph"></i> Toggle OCR';
        toggleOcrButton.addEventListener('click', () => this.toggleOcrOverlay());
        this.elements.fieldControls.appendChild(toggleOcrButton);

        // Field selector
        const fieldSelector = document.createElement('select');
        fieldSelector.className = 'form-select form-select-sm ms-2';
        fieldSelector.style.width = '200px';
        fieldSelector.style.display = 'inline-block';
        fieldSelector.innerHTML = '<option value="">-- Select Field --</option>';
        fieldSelector.addEventListener('change', (e) => {
            const fieldId = e.target.value;
            if (fieldId) {
                this.selectField(fieldId);
            } else {
                this.deselectField();
            }
        });
        this.elements.fieldControls.appendChild(fieldSelector);

        // Field info panel (shown when a field is selected)
        const fieldInfoPanel = document.createElement('div');
        fieldInfoPanel.className = 'field-info-panel mt-2';
        fieldInfoPanel.style.display = 'none';
        this.elements.fieldControls.appendChild(fieldInfoPanel);
    }

    /**
     * Create zoom controls
     */
    createZoomControls() {
        this.elements.zoomControls = document.createElement('div');
        this.elements.zoomControls.className = 'editor-zoom-controls';
        this.elements.controls.appendChild(this.elements.zoomControls);

        // Zoom out button
        const zoomOutButton = document.createElement('button');
        zoomOutButton.type = 'button';
        zoomOutButton.className = 'btn btn-outline-secondary btn-sm';
        zoomOutButton.innerHTML = '<i class="bi bi-zoom-out"></i>';
        zoomOutButton.addEventListener('click', () => this.zoomOut());
        this.elements.zoomControls.appendChild(zoomOutButton);

        // Zoom indicator
        const zoomIndicator = document.createElement('span');
        zoomIndicator.className = 'zoom-indicator mx-2';
        zoomIndicator.textContent = `${Math.round(this.state.scale * 100)}%`;
        this.elements.zoomControls.appendChild(zoomIndicator);

        // Zoom in button
        const zoomInButton = document.createElement('button');
        zoomInButton.type = 'button';
        zoomInButton.className = 'btn btn-outline-secondary btn-sm';
        zoomInButton.innerHTML = '<i class="bi bi-zoom-in"></i>';
        zoomInButton.addEventListener('click', () => this.zoomIn());
        this.elements.zoomControls.appendChild(zoomInButton);

        // Fit to width button
        const fitWidthButton = document.createElement('button');
        fitWidthButton.type = 'button';
        fitWidthButton.className = 'btn btn-outline-secondary btn-sm ms-2';
        fitWidthButton.innerHTML = '<i class="bi bi-arrows-angle-expand"></i> Fit';
        fitWidthButton.addEventListener('click', () => this.fitToWidth());
        this.elements.zoomControls.appendChild(fitWidthButton);
    }

    /**
     * Initialize event listeners
     */
    initEventListeners() {
        // Canvas mouse events for drawing fields
        this.elements.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.elements.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.elements.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));

        // Window resize event
        window.addEventListener('resize', () => this.handleResize());
    }

    /**
 * Extract text from OCR data within a region
 * @param {number} x1 - Left coordinate (0-1)
 * @param {number} y1 - Top coordinate (0-1)
 * @param {number} x2 - Right coordinate (0-1)
 * @param {number} y2 - Bottom coordinate (0-1)
 * @returns {string} - Extracted text
 */
extractTextFromRegion(x1, y1, x2, y2) {
    if (!this.ocrData || !this.ocrData.words || this.ocrData.words.length === 0) {
        return '';
    }

    // Find all words that are entirely or partially within the region
    const wordsInRegion = this.ocrData.words.filter(word => {
        // Consider a word if its center point is in the region
        const wordCenterX = word.x + (word.w / 2);
        const wordCenterY = word.y + (word.h / 2);

        return (
            wordCenterX >= x1 &&
            wordCenterX <= x2 &&
            wordCenterY >= y1 &&
            wordCenterY <= y2
        );
    });

    // If no words found, return empty string
    if (wordsInRegion.length === 0) {
        return '';
    }

    // Sort words by vertical position first, then horizontal
    wordsInRegion.sort((a, b) => {
        // Group words on similar vertical position (within 1.5x height of average)
        const avgHeight = (a.h + b.h) / 2;
        const threshold = avgHeight * 1.5;

        // If y-coordinates are close enough, consider them on same line
        if (Math.abs(a.y - b.y) < threshold) {
            return a.x - b.x; // Sort horizontally on same line
        }

        return a.y - b.y; // Otherwise sort by vertical position
    });

    // Group words into lines
    const lines = [];
    let currentLine = [];
    let prevY = -1;

    wordsInRegion.forEach(word => {
        if (prevY === -1) {
            // First word
            currentLine.push(word);
        } else {
            const avgHeight = word.h; // Use current word height as reference
            const threshold = avgHeight * 1.5;

            // If vertical difference is small, same line
            if (Math.abs(word.y - prevY) < threshold) {
                currentLine.push(word);
            } else {
                // New line
                lines.push([...currentLine]);
                currentLine = [word];
            }
        }

        prevY = word.y;
    });

    // Add last line
    if (currentLine.length > 0) {
        lines.push(currentLine);
    }

    // Combine words into text, line by line
    const text = lines.map(line => {
        return line.map(word => word.text).join(' ');
    }).join('\n');

    return text;
}

    /**
     * Add a standard field to the template
     * This creates a new field from a standard field definition
     */
    addStandardField(standardField) {
        console.log("Adding standard field with code:", standardField.code);
        // Enter create mode
        this.state.mode = 'create';
        this.elements.canvasContainer.classList.remove('view-mode', 'edit-mode');
        this.elements.canvasContainer.classList.add('create-mode');

        // Show instruction
        const message = document.createElement('div');
        message.className = 'alert alert-info mt-2';
        message.innerHTML = `<i class="bi bi-info-circle"></i> Draw a rectangle on the document to place the <strong>${standardField.name}</strong> field`;

        const fieldInfoPanel = this.elements.fieldControls.querySelector('.field-info-panel');
        if (fieldInfoPanel) {
            fieldInfoPanel.style.display = 'block';
            fieldInfoPanel.innerHTML = '';
            fieldInfoPanel.appendChild(message);
        }

        // Set up the new field with standard field properties
        this.state.currentField = {
            id: `new_field_${Date.now()}`,
            name: standardField.name,
            code: standardField.code,
            field_type: standardField.field_type,
            extraction_method: standardField.extraction_method || 'label_based',
            search_pattern: standardField.search_pattern || '',
            is_key_field: standardField.is_key_field || false,
            is_required: standardField.is_required || false,
            page: this.state.currentPage,
            // Coordinates will be set by the drawing process
            x1: 0,
            y1: 0,
            x2: 0,
            y2: 0
        };

        // We'll wait for the user to draw the field position
        // The rest of the process continues in handleMouseUp
    }

    /**
     * Get color for a field type
     */
    getFieldColor(fieldType) {
        const colors = {
            'text': '#28a745',       // Green
            'number': '#dc3545',     // Red
            'date': '#fd7e14',       // Orange
            'currency': '#6f42c1',   // Purple
            'boolean': '#20c997',    // Teal
            'list': '#17a2b8',       // Cyan
            'table': '#6610f2'       // Indigo
        };

        return colors[fieldType] || '#6c757d';  // Default gray
    }

    /**
     * Convert field type to Bootstrap color class
     */
    getBootstrapColor(fieldType) {
        const colors = {
            'text': 'success',
            'number': 'danger',
            'date': 'warning',
            'currency': 'primary',
            'boolean': 'info',
            'list': 'secondary',
            'table': 'dark'
        };
        return colors[fieldType] || 'secondary';
    }

    /**
     * Load the document image
     */
    loadDocument() {
        // Construct the URL correctly
        const url = `${this.options.ajaxUrls.getDocumentImage}?page=${this.state.currentPage}`;

        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    console.error('Error loading document:', data.error);
                    return;
                }

                // Update state
                this.state.totalPages = data.total_pages;
                this.documentDimensions.width = data.width;
                this.documentDimensions.height = data.height;

                // Update page indicator
                const pageIndicator = this.elements.pageControls.querySelector('.page-indicator');
                if (pageIndicator) {
                    pageIndicator.textContent = `Page ${this.state.currentPage} of ${this.state.totalPages}`;
                }

                // Load image
                const img = this.elements.imageLayer.querySelector('img');
                img.onload = () => {
                    // Auto-fit to container width at initial load
                    this.fitToContainer();
                    this.resizeCanvas();
                    this.drawFields();

                    // Load OCR data
                    this.loadOcrData();
                };
                img.src = data.image;
            })
            .catch(error => {
                console.error('Error fetching document:', error);
                this.showError(`Failed to load document: ${error.message}`);
            });
    }

    /**
     * Fit document to container width (initial scaling)
     */
    fitToContainer() {
        // Get container width
        const containerWidth = this.container.clientWidth;

        // Scale document to fit container width with some margin
        this.state.scale = (containerWidth - 40) / this.documentDimensions.width;

        // Ensure minimum scale
        if (this.state.scale < 0.2) this.state.scale = 0.2;
        // Ensure maximum scale
        if (this.state.scale > 1.0) this.state.scale = 1.0;
    }

    /**
     * Show error message in the editor
     */
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger m-3';
        errorDiv.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${message}`;

        // Clear container and show error
        this.container.innerHTML = '';
        this.container.appendChild(errorDiv);
    }

    /**
     * Load OCR data for the current page
     */
    loadOcrData() {
        const url = `${this.options.ajaxUrls.getDocumentOcrData}?page=${this.state.currentPage}`;

        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    console.error('Error loading OCR data:', data.error);
                    this.showMessage("Could not load OCR data: " + data.error, "danger");
                    return;
                }

                if (!data.words || data.words.length === 0) {
                    this.showMessage("This document has no OCR data. Please process the document first.", "warning");
                    return;
                }

                this.ocrData = data;
                this.showOcrOverlay();
            })
            .catch(error => {
                console.error('Error fetching OCR data:', error);
                this.showMessage("Error loading OCR data. Please ensure the document has been processed.", "danger");
            });
    }

    /**
     * Show a message to the user
     */
    showMessage(message, type = "info") {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} mt-3`;
        alertDiv.innerHTML = message;

        // Find a place to show the message
        const targetElement = this.elements.fieldControls.querySelector('.field-info-panel') || this.elements.controls;
        if (targetElement) {
            targetElement.style.display = 'block';
            targetElement.innerHTML = '';
            targetElement.appendChild(alertDiv);
        }
    }

    /**
     * Display text selected in the rectangle
     */
    showSelectedText(text) {
        if (!text) return;

        // Store the selected text
        this.selectedText = text;
        console.log("Selected text from region:", text);

        // Visual feedback for selection
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'alert alert-info position-fixed';
        feedbackDiv.style.bottom = '20px';
        feedbackDiv.style.right = '20px';
        feedbackDiv.style.zIndex = '9999';
        feedbackDiv.style.maxWidth = '300px';
        feedbackDiv.style.maxHeight = '150px';
        feedbackDiv.style.overflow = 'auto';
        feedbackDiv.innerHTML = `<strong>Text extracted:</strong> "${text}"`;

        document.body.appendChild(feedbackDiv);

        // Remove feedback after 3 seconds
        setTimeout(() => {
            document.body.removeChild(feedbackDiv);
        }, 3000);
    }

    /**
     * Load existing fields for the template
     */
    loadFields() {
        // In a real application, you would fetch fields from the server
        // For now, we'll use any fields passed in options
        if (this.options.fields && Array.isArray(this.options.fields)) {
            this.state.fields = this.options.fields;
            this.updateFieldSelector();
        }
    }

    /**
     * Update the field selector dropdown with current fields
     */
    updateFieldSelector() {
        const fieldSelector = this.elements.fieldControls.querySelector('select');
        if (!fieldSelector) return;

        // Keep the first option
        const firstOption = fieldSelector.options[0];
        fieldSelector.innerHTML = '';
        fieldSelector.appendChild(firstOption);

        // Add fields
        this.state.fields.forEach(field => {
            const option = document.createElement('option');
            option.value = field.id;
            option.textContent = field.name;
            fieldSelector.appendChild(option);
        });
    }

    /**
     * Resize the canvas to match the image dimensions
     */
    resizeCanvas() {
        const img = this.elements.imageLayer.querySelector('img');
        if (!img) return;

        const scale = this.state.scale;
        const width = this.documentDimensions.width * scale;
        const height = this.documentDimensions.height * scale;

        // Set canvas dimensions to actual pixels
        this.elements.canvas.width = width;
        this.elements.canvas.height = height;

        // Set container dimensions to match
        this.elements.canvasContainer.style.minWidth = `${width}px`;
        this.elements.canvasContainer.style.minHeight = `${height}px`;

        // Set image dimensions
        img.style.width = `${width}px`;
        img.style.height = `${height}px`;

        // Update zoom indicator
        const zoomIndicator = this.elements.zoomControls.querySelector('.zoom-indicator');
        if (zoomIndicator) {
            zoomIndicator.textContent = `${Math.round(scale * 100)}%`;
        }

        // Redraw fields
        this.drawFields();
    }

    /**
     * Draw fields on the canvas
     */
    drawFields() {
        const ctx = this.elements.context;
        if (!ctx) return;

        const scale = this.state.scale;

        // Clear canvas
        ctx.clearRect(0, 0, this.elements.canvas.width, this.elements.canvas.height);

        // Draw fields
        this.state.fields.forEach(field => {
            // Only draw fields for the current page
            if (field.page && field.page !== this.state.currentPage) {
                return;
            }

            const selected = this.state.currentField && this.state.currentField.id === field.id;

            // Set styles based on field type and selection state
            ctx.lineWidth = selected ? 3 : 2;
            ctx.strokeStyle = selected ? '#007bff' : this.getFieldColor(field.field_type);
            ctx.fillStyle = selected ? 'rgba(0, 123, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)';

            // Draw rectangle
            const x = field.x1 * scale;
            const y = field.y1 * scale;
            const width = (field.x2 - field.x1) * scale;
            const height = (field.y2 - field.y1) * scale;

            ctx.fillRect(x, y, width, height);
            ctx.strokeRect(x, y, width, height);

            // Draw field name
            ctx.font = '12px Arial';
            ctx.fillStyle = selected ? '#007bff' : '#000';
            ctx.fillText(field.name, x + 5, y + 15);
        });

        // Draw the current rectangle if drawing
        if (this.state.drawing && this.state.currentField) {
            const field = this.state.currentField;

            ctx.lineWidth = 2;
            ctx.strokeStyle = '#28a745';
            ctx.fillStyle = 'rgba(40, 167, 69, 0.2)';

            const x = field.x1 * scale;
            const y = field.y1 * scale;
            const width = (field.x2 - field.x1) * scale;
            const height = (field.y2 - field.y1) * scale;

            ctx.fillRect(x, y, width, height);
            ctx.strokeRect(x, y, width, height);
        }
    }

    /**
     * Show OCR overlay
     */
    showOcrOverlay() {
        if (!this.ocrData || !this.ocrData.words) {
            return;
        }

        // Clear previous overlay
        this.elements.ocrLayer.innerHTML = '';

        // Set layer as active
        this.elements.ocrLayer.classList.add('active');

        // Get current document dimensions
        const docWidth = this.documentDimensions.width;
        const docHeight = this.documentDimensions.height;
        const scale = this.state.scale;

        // Create and append all word elements at once
        const fragment = document.createDocumentFragment();

        this.ocrData.words.forEach(word => {
            const wordElement = document.createElement('div');
            wordElement.className = 'ocr-word';

            // Convert normalized coordinates (0-1) to absolute pixel values
            const x = word.x * docWidth * scale;
            const y = word.y * docHeight * scale;
            const width = word.w * docWidth * scale;
            const height = word.h * docHeight * scale;

            wordElement.style.left = `${x}px`;
            wordElement.style.top = `${y}px`;
            wordElement.style.width = `${width}px`;
            wordElement.style.height = `${height}px`;

            wordElement.textContent = word.text;
            wordElement.title = `${word.text} (Confidence: ${word.conf}%)`;

            fragment.appendChild(wordElement);
        });

        this.elements.ocrLayer.appendChild(fragment);
    }

    /**
     * Hide OCR overlay
     */
    hideOcrOverlay() {
        this.elements.ocrLayer.classList.remove('active');
        this.elements.ocrLayer.innerHTML = '';
    }

    /**
     * Toggle OCR overlay
     */
    toggleOcrOverlay() {
        if (this.elements.ocrLayer.classList.contains('active')) {
            this.hideOcrOverlay();
        } else {
            this.showOcrOverlay();
        }
    }

    /**
     * Handle mouse down event for drawing fields
     */
    handleMouseDown(e) {
        // Only allow drawing in create mode
        if (this.state.mode !== 'create') {
            return;
        }

        this.state.drawing = true;

        // Get mouse position relative to canvas
        const x = e.offsetX / this.state.scale;
        const y = e.offsetY / this.state.scale;

        // If currentField is already defined (i.e., from addStandardField),
        // update only the coordinates
        if (this.state.currentField) {
            this.state.currentField.x1 = x;
            this.state.currentField.y1 = y;
            this.state.currentField.x2 = x;
            this.state.currentField.y2 = y;
        } else {
            // Create new field
            this.state.currentField = {
                id: `new_field_${Date.now()}`,
                name: 'New Field',
                field_type: 'text',
                page: this.state.currentPage,
                x1: x,
                y1: y,
                x2: x,
                y2: y
            };
        }
    }

    /**
     * Handle mouse move event for drawing fields
     */
    handleMouseMove(e) {
        if (!this.state.drawing || !this.state.currentField) {
            return;
        }

        // Get mouse position relative to canvas
        const x = e.offsetX / this.state.scale;
        const y = e.offsetY / this.state.scale;

        // Update field dimensions
        this.state.currentField.x2 = x;
        this.state.currentField.y2 = y;

        // Redraw
        this.drawFields();
    }

    /**
     * Handle mouse up event for drawing fields
     */
    handleMouseUp(e) {
        if (!this.state.drawing || !this.state.currentField) {
            return;
        }

        this.state.drawing = false;

        // Normalize coordinates (make sure x1 < x2 and y1 < y2)
        const field = this.state.currentField;
        const x1 = Math.min(field.x1, field.x2);
        const y1 = Math.min(field.y1, field.y2);
        const x2 = Math.max(field.x1, field.x2);
        const y2 = Math.max(field.y1, field.y2);

        // Only create field if it has some size
        if (x2 - x1 < 0.01 || y2 - y1 < 0.01) {
            this.state.currentField = null;
            this.drawFields();
            return;
        }

        // Update field coordinates
        field.x1 = x1;
        field.y1 = y1;
        field.x2 = x2;
        field.y2 = y2;

        // Extract text from the selected region
        this.selectedText = this.extractTextFromRegion(x1, y1, x2, y2);

        // Show the extracted text to the user
        if (this.selectedText) {
            this.showSelectedText(this.selectedText);
        }

        // Show field creation dialog
        this.showFieldDialog(field);
    }

    /**
     * Handle window resize
     */
    handleResize() {
        this.resizeCanvas();
    }

    /**
     * Show dialog for creating or editing a field
     */
    showFieldDialog(field) {
        // Create modal dialog (handled by parent page in this implementation)
        if (typeof window.showFieldModal === 'function') {
            window.showFieldModal(field, (updatedField) => {
                this.saveField(updatedField);
            });
            return;
        }

        // If no external modal function, implement simple prompt
        const name = prompt('Enter field name:', field.name);
        if (name) {
            field.name = name;
            field.code = this.generateFieldCode(name);
            this.saveField(field);
        } else {
            // Cancel
            if (field.id.startsWith('new_field')) {
                // Remove new field if cancelled
                this.state.currentField = null;
                this.drawFields();
            }
        }
    }

    /**
     * Generate field code from field name
     */
    generateFieldCode(name) {
        // Convert name to lowercase, replace spaces with underscores,
        // remove any characters that are not letters, numbers, or underscores
        return name.toLowerCase()
            .replace(/\s+/g, '_')
            .replace(/[^a-z0-9_]/g, '')
            .substring(0, 50);  // Limit length
    }

    /**
     * Save field to server
     */
    saveField(field) {
        const isNewField = field.id.startsWith('new_field');

        console.log("Saving field with code:", field.code);

        // Create payload with ALL field properties
        const payload = {
            template_id: this.options.templateId,
            field_id: isNewField ? null : field.id,
            field_name: field.name,
            field_code: field.code,
            field_type: field.field_type,
            extraction_method: field.extraction_method || 'exact',
            search_pattern: field.search_pattern || '',
            is_key_field: !!field.is_key_field,  // Ensure boolean
            is_required: !!field.is_required,    // Ensure boolean
            coordinates: {
                x1: field.x1,
                y1: field.y1,
                x2: field.x2,
                y2: field.y2
            }
        };
        console.log("Sending payload:", payload);

        // Send to server
        fetch(this.options.ajaxUrls.saveFieldCoordinates, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.options.csrfToken
            },
            body: JSON.stringify(payload)
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    console.error('Error saving field:', data.error);
                    return;
                }

                // Update field ID for new fields
                if (isNewField) {
                    const index = this.state.fields.findIndex(f => f.id === field.id);
                    if (index >= 0) {
                        this.state.fields[index].id = data.field_id;
                    }
                }

                // If this is a new field, add it to the fields array
                if (isNewField) {
                    field.id = data.field_id;
                    this.state.fields.push(field);
                }

                // Reset the currentField and mode
                this.state.currentField = null;
                this.state.mode = 'view';
                this.elements.canvasContainer.classList.remove('create-mode', 'edit-mode');
                this.elements.canvasContainer.classList.add('view-mode');

                // Select the field
                this.selectField(data.field_id);

                // Update field selector
                this.updateFieldSelector();

                // Callback
                if (this.options.onFieldSaved) {
                    this.options.onFieldSaved(data);
                }
            })
            .catch(error => {
                console.error('Error saving field:', error);
            });
    }

    /**
     * Select a field
     */
    selectField(fieldId) {
        const field = this.state.fields.find(f => f.id == fieldId);
        if (!field) return;

        this.state.currentField = field;
        this.state.mode = 'edit';

        // Update field selector
        const fieldSelector = this.elements.fieldControls.querySelector('select');
        if (fieldSelector) {
            fieldSelector.value = fieldId;
        }

        // Show field info panel
        this.showFieldInfo(field);

        // Redraw fields
        this.drawFields();
    }

    /**
     * Deselect the current field
     */
    deselectField(changeMode = true) {
        this.state.currentField = null;
        if (changeMode) {
            this.state.mode = 'view';
        }

        // Update field selector
        const fieldSelector = this.elements.fieldControls.querySelector('select');
        if (fieldSelector) {
            fieldSelector.value = '';
        }

        // Hide field info panel
        const fieldInfoPanel = this.elements.fieldControls.querySelector('.field-info-panel');
        if (fieldInfoPanel) {
            fieldInfoPanel.style.display = 'none';
        }

        // Redraw fields
        this.drawFields();
    }

    /**
     * Show field info panel
     */
    showFieldInfo(field) {
        if (!field) return;

        const fieldInfoPanel = this.elements.fieldControls.querySelector('.field-info-panel');
        if (!fieldInfoPanel) return;

        // Show the panel
        fieldInfoPanel.style.display = 'block';

        // Set content
        fieldInfoPanel.innerHTML = `
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">${field.name}</h6>
                    <div>
                        <button type="button" class="btn btn-sm btn-outline-primary edit-field-btn">
                            <i class="bi bi-pencil"></i> Edit
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-danger delete-field-btn">
                            <i class="bi bi-trash"></i> Delete
                        </button>
                    </div>
                </div>
                <div class="card-body">
                    <div><strong>Code:</strong> ${field.code}</div>
                    <div><strong>Type:</strong> ${field.field_type}</div>
                    <div><strong>Coordinates:</strong> (${field.x1.toFixed(2)}, ${field.y1.toFixed(2)}) - (${field.x2.toFixed(2)}, ${field.y2.toFixed(2)})</div>
                    <div class="mt-2">
                        <button type="button" class="btn btn-sm btn-outline-info extract-field-btn">
                            <i class="bi bi-eye"></i> Extract Value
                        </button>
                        <span class="extracted-value ms-2"></span>
                    </div>
                </div>
            </div>
        `;

        // Add event listeners
        const editBtn = fieldInfoPanel.querySelector('.edit-field-btn');
        const deleteBtn = fieldInfoPanel.querySelector('.delete-field-btn');
        const extractBtn = fieldInfoPanel.querySelector('.extract-field-btn');

        editBtn.addEventListener('click', () => {
            this.showFieldDialog(field);
        });

        deleteBtn.addEventListener('click', () => {
            this.deleteField(field);
        });

        extractBtn.addEventListener('click', () => {
            this.extractFieldValue(field);
        });
    }

    /**
     * Delete a field
     */
    deleteField(field) {
        // Confirm deletion
        if (!confirm(`Are you sure you want to delete the field "${field.name}"?`)) {
            return;
        }

        // Remove field from array
        const index = this.state.fields.findIndex(f => f.id === field.id);
        if (index >= 0) {
            this.state.fields.splice(index, 1);
        }

        // Deselect field
        this.deselectField();

        // Update field selector
        this.updateFieldSelector();

        // Redraw fields
        this.drawFields();

        // In a real application, you would delete from server too
        // For now, we'll just log it
        console.log('Delete field from server:', field.id);
    }

    /**
     * Extract field value from document
     */
    extractFieldValue(field) {
        // Create payload
        const payload = {
            document_id: this.options.documentId,
            field_id: field.id
        };

        // Send to server
        fetch(this.options.ajaxUrls.extractFieldValue, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.options.csrfToken
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                console.error('Error extracting field value:', data.error);
                return;
            }

            // Show the extracted value
            const valueSpan = this.elements.fieldControls.querySelector('.extracted-value');
            if (valueSpan) {
                valueSpan.textContent = data.value || 'No value found';
            }

            // Callback
            if (this.options.onFieldExtracted) {
                this.options.onFieldExtracted(data);
            }
        })
        .catch(error => {
            console.error('Error extracting field value:', error);
        });
    }

    /**
     * Start field creation mode
     */
    startFieldCreation() {
        // Set the mode first
        this.state.mode = 'create';

        // Deselect any selected field
        const origMode = this.state.mode;
        this.deselectField(false); // Pass false to indicate don't change mode
        this.state.mode = origMode; // Restore the original mode

        // Add create mode class to container
        this.elements.canvasContainer.classList.remove('view-mode', 'edit-mode');
        this.elements.canvasContainer.classList.add('create-mode');

        // Show instruction message
        const message = document.createElement('div');
        message.className = 'alert alert-info mt-2';
        message.innerHTML = '<i class="bi bi-info-circle"></i> Draw a rectangle on the document to create a field';

        const fieldInfoPanel = this.elements.fieldControls.querySelector('.field-info-panel');
        if (fieldInfoPanel) {
            fieldInfoPanel.style.display = 'block';
            fieldInfoPanel.innerHTML = '';
            fieldInfoPanel.appendChild(message);
        }
    }

    /**
     * Go to previous page
     */
    previousPage() {
        if (this.state.currentPage > 1) {
            this.state.currentPage--;
            this.loadDocument();
        }
    }

    /**
     * Go to next page
     */
    nextPage() {
        if (this.state.currentPage < this.state.totalPages) {
            this.state.currentPage++;
            this.loadDocument();
        }
    }

    /**
     * Zoom in
     */
    zoomIn() {
        this.state.scale *= 1.2;
        this.resizeCanvas();
    }

    /**
     * Zoom out
     */
    zoomOut() {
        this.state.scale /= 1.2;
        this.resizeCanvas();
    }

    /**
     * Fit document to width
     */
    fitToWidth() {
        const containerWidth = this.container.clientWidth;

        // Set scale to fit container width with some margin
        this.state.scale = (containerWidth - 40) / this.documentDimensions.width;

        // Ensure minimum scale
        if (this.state.scale < 0.2) this.state.scale = 0.2;

        this.resizeCanvas();
    }
}

// Initialize field editor when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if editor container exists
    const editorContainer = document.getElementById('field-editor');
    if (!editorContainer) return;

    // Get options from data attributes
    const documentId = editorContainer.dataset.documentId;
    const templateId = editorContainer.dataset.templateId;
    const documentType = editorContainer.dataset.documentType;

    if (!documentId) {
        console.error('Document ID is required');
        return;
    }

    // Initialize editor
    const editor = new FieldEditor('field-editor', {
        documentId: documentId,
        templateId: templateId,
        documentType: documentType,
        csrfToken: document.querySelector('meta[name="csrf-token"]')?.getAttribute('content'),
        ajaxUrls: {
            getDocumentImage: '/documents/ajax/get-document-image/' + documentId + '/',
            getDocumentOcrData: '/documents/ajax/get-document-ocr-data/' + documentId + '/',
            saveFieldCoordinates: '/documents/ajax/save-field-coordinates/',
            extractFieldValue: '/documents/ajax/extract-field-value/',
            getStandardFields: '/documents/ajax/get-standard-fields/'
        },
        onFieldSaved: function(data) {
            console.log('Field saved:', data);
        },
        onFieldExtracted: function(data) {
            console.log('Field extracted:', data);
        }
    });
});