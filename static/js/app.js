/**
 * Options-Technical Hybrid Scanner
 * Main JavaScript file for the web interface
 */

// Global variables
let emaChart = null;
let levelsChart = null;
let riskRewardChart = null;
let gammaChart = null;
let greeksChart = null;
let scanResults = [];
let scanInProgress = false;
let currentSortColumn = 'confidence'; // Default sort for results table
let currentSortDirection = 'desc'; // Default direction for results table
let dashboardTableFilter = 'all'; // Filter for the main results table ('all', 'bullish', 'bearish', 'neutral')

// DOM elements
const navLinks = document.querySelectorAll('.nav-link');
const sections = document.querySelectorAll('section');
const scanButton = document.getElementById('scanButton');
const scannerForm = document.getElementById('scannerForm');
const analyzeButton = document.getElementById('analyzeButton');
const analysisSymbol = document.getElementById('analysisSymbol');
const analysisResults = document.getElementById('analysisResults');
const resultsTable = document.getElementById('resultsTable');
const progressBarElement = document.querySelector('.progress-bar');
const alertsTableBody = document.getElementById('alertsTableBody'); // Added
const addAlertForm = document.getElementById('addAlertForm'); // Added
const alertHistoryTableBody = document.getElementById('alertHistoryTableBody'); // Added

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    // Set up navigation
    setupNavigation();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load initial data
    loadResults();
    loadAlerts(); // Load alerts on initial load
    loadAlertHistory(); // Load history on initial load

    // Request notification permission on load
    requestNotificationPermission();
});

/**
 * Request browser notification permission
 */
function requestNotificationPermission() {
    if (!("Notification" in window)) {
        console.warn("This browser does not support desktop notification");
    } else if (Notification.permission !== "denied") {
         // We need to ask the user for permission
         // Note: Browsers often require user interaction (like a click) to request permission.
         // It might be better to trigger this request from a button click later.
         // For now, we request it on load, but it might be blocked by the browser.
        Notification.requestPermission().then((permission) => {
            if (permission === "granted") {
                console.log("Notification permission granted.");
                // Optionally show a confirmation notification
                // new Notification("Notifications Enabled!");
            } else {
                 console.log("Notification permission denied or dismissed.");
            }
        });
    } else {
         console.log("Notification permission was previously denied.");
    }
}

/**
 * Display a browser notification
 */
function showBrowserNotification(alertData) {
    if (!("Notification" in window)) {
        console.warn("Browser does not support notifications.");
        return;
    }

    if (Notification.permission === "granted") {
        const title = `Scanner Alert: ${alertData.symbol || 'N/A'}`;
        const options = {
            body: alertData.message || `Alert '${alertData.name || 'Unnamed'}' triggered.`,
            icon: '/static/images/icon.png' // Optional: Add an icon
            // Add other options like requireInteraction, tag, etc. if needed
        };
        
        // Create and show the notification
        const notification = new Notification(title, options);

        // Optional: Handle notification click
        notification.onclick = () => {
             console.log("Notification clicked");
             // Example: Focus the window and navigate to the analysis page for the symbol
             window.focus();
             if (alertData.symbol) {
                  // Navigate to analysis section
                  navLinks.forEach(l => l.classList.remove('active'));
                  document.querySelector('a[href="#analysis"]').classList.add('active');
                  sections.forEach(section => section.classList.add('d-none'));
                  document.getElementById('analysis').classList.remove('d-none');
                  // Set symbol and trigger analysis
                  analysisSymbol.value = alertData.symbol;
                  analyzeSymbol(alertData.symbol);
             }
        };

    } else if (Notification.permission !== "denied") {
        // Ask again? Or just log. Asking again might be annoying.
        console.log("Notification permission not granted yet.");
        // Optionally, prompt the user to enable notifications via a UI element
    } else {
         console.log("Notification permission denied.");
    }
}


/**
 * Set up navigation between sections
 */
function setupNavigation() {
    // Re-select navLinks here in case new ones were added dynamically (though not in this case)
    const currentNavLinks = document.querySelectorAll('.nav-link');
    currentNavLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Remove active class from all links
            currentNavLinks.forEach(l => l.classList.remove('active'));
            
            // Add active class to clicked link
            link.classList.add('active');
            
            // Hide all sections
            const currentSections = document.querySelectorAll('section'); // Re-select sections
            currentSections.forEach(section => section.classList.add('d-none'));
            
            // Show the target section
            const targetId = link.getAttribute('href').substring(1);
            const targetSection = document.getElementById(targetId);
            if (targetSection) {
                 targetSection.classList.remove('d-none');
                 // If navigating to alerts, refresh the list and history
                 if (targetId === 'alerts') {
                      loadAlerts();
                      loadAlertHistory(); // Also load history
                 }
            } else {
                 console.error(`Navigation target section not found: ${targetId}`);
                 // Optionally show a default section like dashboard
                 document.getElementById('dashboard').classList.remove('d-none');
                 document.querySelector('a[href="#dashboard"]').classList.add('active');
            }
        });
    });
}

/**
 * Load and display user alerts
 */
function loadAlerts() {
    fetch('/api/alerts')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayAlerts(data.alerts);
            } else {
                console.error('Error loading alerts:', data.error);
                alertsTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Error loading alerts</td></tr>';
            }
        })
        .catch(error => {
            console.error('Error fetching alerts:', error);
            alertsTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Failed to fetch alerts</td></tr>';
        });
}

/**
 * Display alerts in the table
 */
function displayAlerts(alerts) {
    alertsTableBody.innerHTML = ''; // Clear existing rows
    if (!alerts || alerts.length === 0) {
        alertsTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No alerts defined.</td></tr>';
        return;
    }

    alerts.forEach(alert => {
        const row = document.createElement('tr');
        
        // Format conditions for readability
        let conditionsFormatted = '';
        try {
             conditionsFormatted = Object.entries(alert.conditions).map(([key, value]) => {
                  let valueStr = Array.isArray(value) ? value.join(', ') : value;
                  // Simple formatting for known keys
                  if (key === 'min_confidence' || key === 'max_confidence') valueStr += '%';
                  if (key === 'rsi_min' || key === 'rsi_max' || key === 'stoch_rsi_min' || key === 'stoch_rsi_max') valueStr = `${key.split('_')[1]}: ${valueStr}`;
                  else if (key.endsWith('_min')) valueStr = `Min ${key.replace('_min','')}: ${valueStr}`;
                  else if (key.endsWith('_max')) valueStr = `Max ${key.replace('_max','')}: ${valueStr}`;
                  else valueStr = `${key}: ${valueStr}`;
                  return escapeHtml(valueStr);
             }).join('<br>'); // Use line breaks for readability
        } catch (e) {
             console.error("Error formatting alert conditions:", e, alert.conditions);
             conditionsFormatted = escapeHtml(JSON.stringify(alert.conditions)); // Fallback to JSON string
        }

        const methodsStr = alert.methods.join(', ');
        const createdDate = new Date(alert.created_at).toLocaleString();

        row.innerHTML = `
            <td>${escapeHtml(alert.name)}</td>
            <td>${conditionsFormatted}</td> <!-- Use formatted string -->
            <td>${escapeHtml(methodsStr)}</td>
            <td>${escapeHtml(createdDate)}</td>
            <td>
                <button class="btn btn-sm btn-danger delete-alert-btn" data-alert-id="${alert.id}">
                    <i class="bi bi-trash"></i> Delete
                </button>
            </td>
        `;
        alertsTableBody.appendChild(row);
    });

    // Add event listeners to new delete buttons
    document.querySelectorAll('.delete-alert-btn').forEach(button => {
        button.addEventListener('click', handleDeleteAlert);
   });
}

/**
* Load and display triggered alert history
*/
function loadAlertHistory() {
    if (!alertHistoryTableBody) return; // Element might not exist if HTML is old

    alertHistoryTableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Loading history...</td></tr>';

    fetch('/api/alerts/history')
         .then(response => response.json())
         .then(data => {
              if (data.success) {
                   displayAlertHistory(data.history);
              } else {
                   console.error('Error loading alert history:', data.error);
                   alertHistoryTableBody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Error loading history</td></tr>';
              }
         })
         .catch(error => {
              console.error('Error fetching alert history:', error);
              alertHistoryTableBody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Failed to fetch history</td></tr>';
         });
}

/**
* Display alert history in the table
*/
function displayAlertHistory(history) {
    if (!alertHistoryTableBody) return;
    
    alertHistoryTableBody.innerHTML = ''; // Clear existing rows
    if (!history || history.length === 0) {
         alertHistoryTableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No alert history found.</td></tr>';
         return;
    }

    // History is returned newest first from backend
    history.forEach(entry => {
         const row = document.createElement('tr');
         const timestamp = new Date(entry.timestamp).toLocaleString();
         // Safely access nested details
         const details = entry.details || {};
         const detailsStr = `Setup: ${details.setup || 'N/A'}, Conf: ${details.confidence !== undefined ? details.confidence.toFixed(1) + '%' : 'N/A'}, Price: ${details.price !== undefined ? '$' + details.price.toFixed(2) : 'N/A'}`;

         row.innerHTML = `
              <td>${escapeHtml(timestamp)}</td>
              <td>${escapeHtml(entry.alert_name)}</td>
              <td>${escapeHtml(entry.symbol)}</td>
              <td>${escapeHtml(detailsStr)}</td>
         `;
         alertHistoryTableBody.appendChild(row);
    });
}

// Helper function to escape HTML characters (basic version)
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return unsafe; // Return non-strings as is
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
 }

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Scan button
    scanButton.addEventListener('click', () => {
        // Navigate to scanner section
        navLinks.forEach(l => l.classList.remove('active'));
        document.querySelector('a[href="#scanner"]').classList.add('active');
        
        // Hide all sections
        sections.forEach(section => section.classList.add('d-none'));
        
        // Show scanner section
        document.getElementById('scanner').classList.remove('d-none');
    });
    
    // Scanner form
    scannerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        // Navigate to dashboard immediately
        navLinks.forEach(l => l.classList.remove('active'));
        document.querySelector('a[href="#dashboard"]').classList.add('active');
        sections.forEach(section => section.classList.add('d-none'));
        document.getElementById('dashboard').classList.remove('d-none');
        
        // Run the scan
        runScan();
    });
    
    // Analyze button
    analyzeButton.addEventListener('click', () => {
        const symbol = analysisSymbol.value.trim().toUpperCase();
        if (symbol) {
            analyzeSymbol(symbol);
        } else {
            alert('Please enter a valid symbol');
        }
    });
    
    // Analysis symbol input (enter key)
    analysisSymbol.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            analyzeButton.click();
        }
    });

    // Add Alert Form Submission
    if (addAlertForm) { // Check if element exists
         addAlertForm.addEventListener('submit', handleAddAlert);
    } else {
         console.error("Add Alert Form not found.");
    }
    
    // Add Table Header Sort Listeners (Dashboard Results Table)
    document.querySelectorAll('#dashboard table thead th[data-sort-key]').forEach(th => {
         th.addEventListener('click', () => {
              const sortKey = th.getAttribute('data-sort-key');
              if (!sortKey) return; // Ignore headers without data-sort-key

              if (currentSortColumn === sortKey) {
                   // Toggle direction
                   currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
              } else {
                   // Sort by new column, default to desc
                   currentSortColumn = sortKey;
                   currentSortDirection = 'desc';
              }
              updateResultsTable(); // Re-render table with new sort
         });
    });

    // Note: Delete button listeners are added dynamically in displayAlerts
}

/**
 * Handle Add Alert form submission
 */
function handleAddAlert(event) {
    event.preventDefault();
    const nameInput = document.getElementById('alertName');
    const symbolInput = document.getElementById('alertSymbol');
    const setupBullish = document.getElementById('alertSetupBullish');
    const setupBearish = document.getElementById('alertSetupBearish');
    const setupNeutral = document.getElementById('alertSetupNeutral');
    const minConfidenceInput = document.getElementById('alertMinConfidence');
    const methodBrowser = document.getElementById('alertMethodBrowser');
    const methodEmail = document.getElementById('alertMethodEmail');

    // Basic check if elements exist
    if (!nameInput || !symbolInput || !setupBullish || !setupBearish || !setupNeutral || !minConfidenceInput || !methodBrowser || !methodEmail) {
         console.error("One or more alert form elements not found.");
         alert("Error: Alert form elements missing.");
         return;
    }

    const name = nameInput.value.trim();
    const conditions = {};

    // Process Symbol(s)
    const symbols = symbolInput.value.trim().toUpperCase().split(',').map(s => s.trim()).filter(s => s); // Split by comma, trim, remove empty
    if (symbols.length > 0) {
        conditions.symbol = symbols;
    }

    // Process Setup Type(s)
    const setupTypes = [];
    if (setupBullish.checked) setupTypes.push('bullish');
    if (setupBearish.checked) setupTypes.push('bearish');
    if (setupNeutral.checked) setupTypes.push('neutral');
    if (setupTypes.length > 0) {
        conditions.setup = setupTypes;
    }

    // Process Min Confidence
    const minConfidence = minConfidenceInput.value.trim();
    if (minConfidence !== '') {
        const confidenceVal = parseInt(minConfidence);
        if (!isNaN(confidenceVal) && confidenceVal >= 0 && confidenceVal <= 100) {
            conditions.min_confidence = confidenceVal;
        } else {
            alert('Minimum Confidence must be a number between 0 and 100.');
            return;
        }
    }
    
    // Add logic here to read other condition fields if they were added to the HTML

    // Validate that at least one condition was set
    if (Object.keys(conditions).length === 0) {
         alert('Please specify at least one condition for the alert.');
         return;
    }

    const methods = [];
    if (methodBrowser.checked) methods.push('browser');
    if (methodEmail.checked) methods.push('email');
    // Add webhook if checkbox exists

    if (!name || Object.keys(conditions).length === 0 || methods.length === 0) {
        alert('Please fill in name, provide valid conditions, and select at least one notification method.');
        return;
    }

    // Disable button temporarily
    const submitButton = addAlertForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.textContent = 'Adding...';

    // Send POST request to create alert
    fetch('/api/alerts', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name, conditions, methods }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Alert added successfully!');
            addAlertForm.reset(); // Clear the form
            loadAlerts(); // Refresh the table
        } else {
            alert(`Error adding alert: ${data.error || 'Unknown error'}`);
        }
    })
    .catch(error => {
        console.error('Error adding alert:', error);
        alert('Failed to add alert. Check console for details.');
    })
    .finally(() => {
         // Re-enable button
         submitButton.disabled = false;
         submitButton.textContent = 'Add Alert';
    });
}

/**
 * Handle Delete Alert button click
 */
function handleDeleteAlert(event) {
     // Use currentTarget to ensure we get the button, even if icon is clicked
    const button = event.currentTarget;
    const alertId = button.getAttribute('data-alert-id');
    
    if (!alertId) {
        console.error('Could not find alert ID on delete button.');
        return;
    }

    if (confirm(`Are you sure you want to delete alert "${alertId}"?`)) {
         // Disable button temporarily
         button.disabled = true;
         button.innerHTML = '<i class="bi bi-hourglass-split"></i> Deleting...';

        fetch(`/api/alerts/${alertId}`, {
            method: 'DELETE',
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // alert('Alert deleted successfully!'); // Maybe skip alert for delete
                loadAlerts(); // Refresh the table
            } else {
                alert(`Error deleting alert: ${data.error || 'Unknown error'}`);
                 // Re-enable button on failure
                 button.disabled = false;
                 button.innerHTML = '<i class="bi bi-trash"></i> Delete';
            }
        })
        .catch(error => {
            console.error('Error deleting alert:', error);
            alert('Failed to delete alert. Check console for details.');
             // Re-enable button on failure
             button.disabled = false;
             button.innerHTML = '<i class="bi bi-trash"></i> Delete';
        });
    }
}


/**
 * Load scan results
 */
function loadResults() {
    // Show loading state
    resultsTable.innerHTML = '<tr><td colspan="9" class="text-center">Loading results...</td></tr>';
    
    // Fetch results from API
    fetch('/api/results')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                scanResults = data.results;
                updateDashboard();
            } else {
                resultsTable.innerHTML = '<tr><td colspan="9" class="text-center">No results available</td></tr>';
            }
        })
        .catch(error => {
            console.error('Error loading results:', error);
            resultsTable.innerHTML = '<tr><td colspan="9" class="text-center">Error loading results</td></tr>';
        });
}

/**
 * Update dashboard with scan results
 */
function updateDashboard() {
    // Count setups by type
    const bullishSetups = scanResults.filter(r => r.setup.startsWith('bullish'));
    const bearishSetups = scanResults.filter(r => r.setup.startsWith('bearish'));
    const neutralSetups = scanResults.filter(r => r.setup.startsWith('neutral'));
    
    // Update counts
    document.getElementById('bullishCount').textContent = bullishSetups.length;
    document.getElementById('bearishCount').textContent = bearishSetups.length;
    document.getElementById('neutralCount').textContent = neutralSetups.length;
    
    // Update setup lists
    updateSetupList('bullishList', bullishSetups, 'bullish');
    updateSetupList('bearishList', bearishSetups, 'bearish');
    updateSetupList('neutralList', neutralSetups, 'neutral');
    
    // Update results table
    updateResultsTable();

    // Add click listeners to setup list headers for filtering main table
    // Need to ensure the card headers have these specific IDs in index.html
    addFilterListener('bullishListCardHeader', 'bullish');
    addFilterListener('bearishListCardHeader', 'bearish');
    addFilterListener('neutralListCardHeader', 'neutral');
    // Add listener to main results header to clear filter
    addFilterListener('resultsCardHeader', 'all');
}

/**
 * Helper function to add filter click listeners
 */
function addFilterListener(elementId, filterType) {
     const headerElement = document.getElementById(elementId);
     if (headerElement) {
          headerElement.style.cursor = 'pointer'; // Indicate clickable
          headerElement.addEventListener('click', () => {
               // Remove active filter class from all headers first
               document.querySelectorAll('.list-filter-header').forEach(el => el.classList.remove('active-filter'));
               
               dashboardTableFilter = filterType;
               updateResultsTable(); // Re-render table with filter
               
               // Add active filter class to the clicked header
               headerElement.classList.add('active-filter');
               console.log(`Dashboard table filter set to: ${filterType}`);
          });
     } else {
          console.warn(`Filter listener element not found: ${elementId}`);
     }
}


/**
 * Update setup list
 */
function updateSetupList(elementId, setups, setupType) {
    const listElement = document.getElementById(elementId);
    listElement.innerHTML = '';
    
    // Sort by confidence
    setups.sort((a, b) => b.confidence - a.confidence);
    
    // Take top 5
    const topSetups = setups.slice(0, 5);
    
    if (topSetups.length === 0) {
        listElement.innerHTML = '<div class="text-muted">No setups found</div>';
        return;
    }
    
    
    // Create list items
    topSetups.forEach((setup, index) => { // Added index for unique canvas ID
        const item = document.createElement('div');
        item.className = `setup-item ${setupType}`;
        // Create a unique ID for the canvas
        const canvasId = `sparkline-${setupType}-${setup.symbol}-${index}`;
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-center w-100">
                 <div>
                      <span class="symbol">${setup.symbol}</span>
                      <span class="confidence">${setup.confidence.toFixed(1)}%</span>
                 </div>
                 <canvas id="${canvasId}" class="sparkline-canvas" width="80" height="25"></canvas>
            </div>
        `;
        
        // Add click event to navigate to analysis (attach to the whole item)
        item.addEventListener('click', () => { // Moved listener attachment here
            // Navigate to analysis section
            navLinks.forEach(l => l.classList.remove('active'));
            document.querySelector('a[href="#analysis"]').classList.add('active');
            
            // Hide all sections
            sections.forEach(section => section.classList.add('d-none'));
            
            // Show analysis section
            document.getElementById('analysis').classList.remove('d-none');
            
            // Set symbol and trigger analysis
            analysisSymbol.value = setup.symbol;
            analyzeSymbol(setup.symbol);
        }); // Moved listener attachment here
        
        listElement.appendChild(item);

        // Render sparkline after element is added to DOM
        const sparklineData = setup.sparkline_data;
        if (sparklineData && sparklineData.length > 1) {
             const sparklineCtx = document.getElementById(canvasId).getContext('2d');
             // Determine line color based on trend (start vs end price)
             const startPrice = sparklineData[0];
             const endPrice = sparklineData[sparklineData.length - 1];
             const lineColor = endPrice >= startPrice ? 'rgba(40, 167, 69, 0.8)' : 'rgba(220, 53, 69, 0.8)'; // Green or Red

             new Chart(sparklineCtx, {
                  type: 'line',
                  data: {
                       labels: sparklineData.map((_, i) => i), // Simple index labels
                       datasets: [{
                            data: sparklineData,
                            borderColor: lineColor,
                            borderWidth: 1.5,
                            pointRadius: 0, // No points
                            tension: 0.2 // Smoother curve
                       }]
                  },
                  options: {
                       responsive: true,
                       maintainAspectRatio: false,
                       scales: {
                            x: { display: false }, // Hide axes
                            y: { display: false }
                       },
                       plugins: {
                            legend: { display: false }, // Hide legend
                            tooltip: { enabled: false } // Disable tooltips
                       },
                       layout: {
                            padding: { top: 2, bottom: 2 } // Minimal padding
                       }
                  }
             });
        } else {
             console.warn(`No or insufficient sparkline data for ${setup.symbol}`);
             // Optionally hide the canvas if no data
             const canvasEl = document.getElementById(canvasId);
             if(canvasEl) canvasEl.style.display = 'none';
        }
    });
}
/**
 * Update results table with sorting
 */
function updateResultsTable() {
    const tableBody = document.getElementById('resultsTable'); // Target tbody
    const tableHead = document.querySelector('#dashboard table thead tr'); // Get header row
    if (!tableBody || !tableHead) return; // Exit if elements not found

    tableBody.innerHTML = ''; // Clear existing body rows

    // --- Filtering Logic ---
    let resultsToDisplay = scanResults;
    if (dashboardTableFilter !== 'all') {
         resultsToDisplay = scanResults.filter(r => r.setup.startsWith(dashboardTableFilter));
    }
    // --- End Filtering Logic ---
    
    // --- Sorting Logic ---
    const sortKey = currentSortColumn;
    const sortDir = currentSortDirection === 'asc' ? 1 : -1;

    // Create a sortable copy using the filtered results
    const sortedResults = [...resultsToDisplay].sort((a, b) => {
         let valA = a[sortKey];
         let valB = b[sortKey];

         // Handle nested properties if needed later (e.g., market_context.rsi)
         // if (sortKey.includes('.')) { ... }

         // Basic type handling for sorting
         if (typeof valA === 'string') valA = valA.toLowerCase();
         if (typeof valB === 'string') valB = valB.toLowerCase();
         // Handle null/undefined (treat as lowest value)
         if (valA == null) return -1 * sortDir;
         if (valB == null) return 1 * sortDir;

         if (valA < valB) return -1 * sortDir;
         if (valA > valB) return 1 * sortDir;
         return 0;
    });
    // --- End Sorting Logic ---

    if (sortedResults.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No results available</td></tr>';
        return;
    }
    
    // --- Update Header Indicators ---
    tableHead.querySelectorAll('th[data-sort-key]').forEach(th => {
         th.classList.remove('sort-asc', 'sort-desc');
         const key = th.getAttribute('data-sort-key');
         if (key === currentSortColumn) {
              th.classList.add(currentSortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
         }
    });
    // --- End Header Update ---

    // Create table rows
    sortedResults.forEach(result => {
        const row = document.createElement('tr');
        
        // Determine setup class
        let setupClass = '';
        let setupText = result.setup;
        
        if (result.setup.startsWith('bullish')) {
            setupClass = 'text-success';
            setupText = result.setup.replace('bullish', 'Bullish');
        } else if (result.setup.startsWith('bearish')) {
            setupClass = 'text-danger';
            setupText = result.setup.replace('bearish', 'Bearish');
        } else if (result.setup.startsWith('neutral')) {
            setupClass = 'text-secondary';
            setupText = result.setup.replace('neutral', 'Neutral');
        }
        
        // Determine entry signal class
        let entrySignalClass = '';
        let entrySignalText = '';
        
        if (result.entry_signal) {
            entrySignalClass = 'yes';
            entrySignalText = 'Yes';
        } else {
            entrySignalClass = 'no';
            entrySignalText = 'No';
        }
        
        row.innerHTML = `
            <td><strong>${result.symbol}</strong></td>
            <td class="${setupClass}">${setupText}</td>
            <td>${result.confidence.toFixed(1)}%</td>
            <td><span class="signal-badge ${entrySignalClass}">${entrySignalText}</span></td>
            <td>$${result.current_price.toFixed(2)}</td>
            <td>$${result.target_price.toFixed(2)}</td>
            <td>$${result.stop_loss.toFixed(2)}</td>
            <td>${result.risk_reward.toFixed(2)}</td>
            <td>
                <button class="btn btn-sm btn-primary analyze-btn" data-symbol="${result.symbol}">
                    <i class="bi bi-graph-up"></i> Analyze
                </button>
            </td>
        `;
        
        tableElement.appendChild(row);
    });
    
    // Add event listeners to analyze buttons
    document.querySelectorAll('.analyze-btn').forEach(button => {
        button.addEventListener('click', () => {
            const symbol = button.getAttribute('data-symbol');
            
            // Navigate to analysis section
            navLinks.forEach(l => l.classList.remove('active'));
            document.querySelector('a[href="#analysis"]').classList.add('active');
            
            // Hide all sections
            sections.forEach(section => section.classList.add('d-none'));
            
            // Show analysis section
            document.getElementById('analysis').classList.remove('d-none');
            
            // Set symbol and trigger analysis
            analysisSymbol.value = symbol;
            analyzeSymbol(symbol);
        });
    });
}

/**
 * Run scanner with custom filters
 */
function runScan() {
    // Prevent multiple scans from running simultaneously
    if (scanInProgress) {
        alert('A scan is already in progress. Please wait for it to complete.');
        return;
    }
    
    scanInProgress = true;
    
    // Show loading state
    resultsTable.innerHTML = '<tr><td colspan="9" class="text-center">Running scan...</td></tr>';

    // Reset and show progress bar
    progressBarElement.style.width = '0%';
    progressBarElement.setAttribute('aria-valuenow', '0');
    progressBarElement.innerHTML = '<span class="progress-text">0%</span>';
    progressBarElement.parentElement.classList.remove('d-none');
    
    // Get filter values
    const trendBullish = document.getElementById('trendBullish').checked;
    const trendBearish = document.getElementById('trendBearish').checked;
    const trendNeutral = document.getElementById('trendNeutral').checked;
    const pcrMin = parseFloat(document.getElementById('pcrMin').value);
    const pcrMax = parseFloat(document.getElementById('pcrMax').value);
    const rsiMin = parseInt(document.getElementById('rsiMin').value);
    const rsiMax = parseInt(document.getElementById('rsiMax').value);
    const stochRsiMin = parseInt(document.getElementById('stochRsiMin').value);
    const stochRsiMax = parseInt(document.getElementById('stochRsiMax').value);
    const minConfidence = parseInt(document.getElementById('minConfidence').value);
    const symbol = document.getElementById('symbolInput').value.trim().toUpperCase();
    const sentimentMin = parseFloat(document.getElementById('sentimentMin').value); // Added
    const sentimentImproving = document.getElementById('sentimentImproving').checked; // Added
    const sentimentStable = document.getElementById('sentimentStable').checked; // Added
    const sentimentDeclining = document.getElementById('sentimentDeclining').checked; // Added
    
    // Build trend array
    const trend = [];
    if (trendBullish) trend.push('bullish');
    if (trendBearish) trend.push('bearish');
    if (trendNeutral) trend.push('neutral');
    
    // Build filters object
    const filters = {
        trend,
        pcr_min: pcrMin,
        pcr_max: pcrMax,
        rsi_min: rsiMin,
        rsi_max: rsiMax,
        stoch_rsi_min: stochRsiMin,
        stoch_rsi_max: stochRsiMax,
        min_confidence: minConfidence,
        sentiment_min: sentimentMin, // Added
        sentiment_trend: [] // Added (will populate next)
    };

    // Populate sentiment_trend based on checkboxes
    if (sentimentImproving) filters.sentiment_trend.push('improving');
    if (sentimentStable) filters.sentiment_trend.push('stable');
    if (sentimentDeclining) filters.sentiment_trend.push('declining');
    
    // Add symbol if provided
    if (symbol) {
        filters.symbols = [symbol];
    }

    // Initialize progress bar
    const progressBar = progressBarElement;
    progressBar.style.width = '0%';
    progressBar.classList.remove('bg-danger', 'bg-success');
    progressBar.setAttribute('aria-valuenow', 0);
    progressBar.querySelector('.progress-text').textContent = 'Initializing scan...';
    progressBar.parentElement.classList.remove('d-none');

    let eventSource = null;
    let scanTimeout = null;

    const handleScanError = (error) => {
        console.error('Scan error:', error);
        progressBar.classList.add('bg-danger');
        progressBar.querySelector('.progress-text').textContent = `Error: ${error}`;
        scanInProgress = false;
        if (eventSource) {
            eventSource.close();
        }
        if (scanTimeout) {
            clearTimeout(scanTimeout);
        }
    };

    const handleScanComplete = (results) => {
        scanResults = results;
        scanInProgress = false;
        progressBar.classList.add('bg-success');
        progressBar.style.width = '100%';
        progressBar.setAttribute('aria-valuenow', 100);
        progressBar.querySelector('.progress-text').textContent = 'Scan Complete!';

        // Navigate to dashboard immediately
        navLinks.forEach(l => l.classList.remove('active'));
        document.querySelector('a[href="#dashboard"]').classList.add('active');
        sections.forEach(section => section.classList.add('d-none'));
        document.getElementById('dashboard').classList.remove('d-none');
        updateDashboard();
    };

    try {
        // Set scan timeout
        scanTimeout = setTimeout(() => {
            handleScanError('Scan timed out after 30 seconds');
        }, 30000);

        // Create EventSource for progress updates
        const url = new URL('/api/scan', window.location.origin);
        url.searchParams.append('filters', JSON.stringify(filters));
        eventSource = new EventSource(url.toString());

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                // Clear timeout on any message
                if (scanTimeout) {
                    clearTimeout(scanTimeout);
                    // Reset timeout for inactivity during scan? Maybe not needed if progress updates are frequent.
                }
                
                // Check if it's an alert message
                if (data.type === 'alert') {
                     showBrowserNotification(data);
                     // Don't treat alert as final completion or error
                     return;
                }

                // Handle progress updates (if not an alert)
                if (data.progress !== undefined) {
                    const progress = Math.min(100, Math.max(0, data.progress));
                    progressBar.style.width = `${progress}%`;
                    progressBar.setAttribute('aria-valuenow', progress);
                    progressBar.querySelector('.progress-text').textContent =
                        `${progress}% Complete`;
                }

                // Handle errors
                if (data.error) {
                    handleScanError(data.error);
                    return;
                }

                // Handle completion
                if (data.success && data.results) {
                    eventSource.close();
                    handleScanComplete(data.results);
                }
            } catch (error) {
                handleScanError(`Failed to parse server message: ${error.message}`);
            }
        };

        eventSource.onerror = (error) => {
            handleScanError('Connection to scan server failed');
        };

    } catch (error) {
        handleScanError(`Failed to start scan: ${error.message}`);
    }
}

/**
 * Fetch options metrics for a symbol
 */
function fetchOptionsMetrics(symbol) {
    fetch(`/api/options_metrics/${symbol}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                createGammaChart(data.metrics);
                createGreeksChart(data.metrics);
                createGexChart(data.metrics); // Added call for GEX chart
            } else {
                console.error(`Error fetching options metrics: ${data.error}`);
            }
        })
        .catch(error => {
            console.error(`Error fetching options metrics:`, error);
        });
}

/**
 * Create Gamma chart
 */
function createGammaChart(metrics) {
    if (gammaChart) {
        gammaChart.destroy();
    }

    const ctx = document.getElementById('gammaChart').getContext('2d');
    gammaChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: metrics.strikes.map(s => `$${s.toFixed(2)}`),
            datasets: [{
                label: 'Gamma',
                data: metrics.gamma,
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                borderWidth: 2
            }]
        },
        options: {
             responsive: true,
             maintainAspectRatio: false,
             plugins: {
                  zoom: { // Enable zoom plugin
                       pan: { enabled: true, mode: 'xy' },
                       zoom: {
                            wheel: { enabled: true },
                            pinch: { enabled: true },
                            mode: 'xy',
                       }
                  },
                  legend: { position: 'top' },
                  tooltip: { mode: 'index', intersect: false }
             },
            scales: {
                 x: { ticks: { maxTicksLimit: 15, autoSkip: true } },
                 y: { beginAtZero: false }
            }
        }
    });
}

/**
 * Create Greeks chart
 */
function createGreeksChart(metrics) {
    if (greeksChart) {
        greeksChart.destroy();
    }

    const ctx = document.getElementById('greeksChart').getContext('2d');
    greeksChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: metrics.strikes.map(s => `$${s.toFixed(2)}`),
            datasets: [
                {
                    label: 'Charm',
                    data: metrics.charm,
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    borderWidth: 1
                },
                {
                    label: 'Vanna',
                    data: metrics.vanna,
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    borderWidth: 1
                },
                {
                    label: 'Vomma',
                    data: metrics.vomma,
                    borderColor: '#6c757d',
                    backgroundColor: 'rgba(108, 117, 125, 0.1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
             responsive: true,
             maintainAspectRatio: false,
             plugins: {
                  zoom: { // Enable zoom plugin
                       pan: { enabled: true, mode: 'xy' },
                       zoom: {
                            wheel: { enabled: true },
                            pinch: { enabled: true },
                            mode: 'xy',
                       }
                  },
                  legend: { position: 'top' },
                  tooltip: { mode: 'index', intersect: false }
             },
            scales: {
                 x: { ticks: { maxTicksLimit: 15, autoSkip: true } },
                 y: { beginAtZero: false } // Allow negative values for Greeks
            }
        }
    });
}

/**
 * Create GEX Profile chart
 */
function createGexChart(metrics) {
     // Destroy existing chart if it exists
     // Assuming a global variable gexChart exists, similar to others
     if (window.gexChart) {
          window.gexChart.destroy();
     }

     const ctx = document.getElementById('gexChart').getContext('2d');
     
     const gexData = metrics.gex_by_strike || [];
     if (gexData.length === 0) {
          console.warn("GEX profile data not found or empty.");
          // Optionally clear or display message
          return;
     }

     // Prepare labels (strikes) and data (total_gex)
     const labels = gexData.map(item => `$${item.strike.toFixed(2)}`);
     const data = gexData.map(item => item.total_gex);

     // Determine bar colors based on positive/negative GEX
     const backgroundColors = data.map(gex => gex >= 0 ? 'rgba(40, 167, 69, 0.6)' : 'rgba(220, 53, 69, 0.6)'); // Green for positive, Red for negative
     const borderColors = data.map(gex => gex >= 0 ? 'rgba(40, 167, 69, 1)' : 'rgba(220, 53, 69, 1)');

     window.gexChart = new Chart(ctx, {
          type: 'bar',
          data: {
               labels: labels,
               datasets: [{
                    label: 'GEX per Strike',
                    data: data,
                    backgroundColor: backgroundColors,
                    borderColor: borderColors,
                    borderWidth: 1
               }]
          },
          options: {
               responsive: true,
               maintainAspectRatio: false,
               plugins: {
                    legend: {
                         display: false // Hide legend as color indicates sign
                    },
                    tooltip: {
                         callbacks: {
                              label: function(context) {
                                   let label = 'GEX: ';
                                   if (context.parsed.y !== null) {
                                        // Format GEX value (e.g., with commas, units if needed)
                                        label += context.parsed.y.toLocaleString(undefined, { maximumFractionDigits: 0 });
                                   }
                                   return label;
                              }
                         }
                    }
               },
               scales: {
                    x: {
                         title: {
                              display: true,
                              text: 'Strike Price'
                         },
                         ticks: {
                              maxTicksLimit: 15,
                              autoSkip: true,
                         }
                    },
                    y: {
                         title: {
                              display: true,
                              text: 'Gamma Exposure (GEX)'
                         },
                         ticks: {
                              callback: function(value, index, values) {
                                   // Format large numbers (e.g., K for thousands, M for millions)
                                   if (Math.abs(value) >= 1e6) return (value / 1e6).toFixed(1) + 'M';
                                   if (Math.abs(value) >= 1e3) return (value / 1e3).toFixed(0) + 'K';
                                   return value.toFixed(0);
                              }
                         }
                    }
               }
          }
     });
}


/**
 * Analyze a specific symbol
 */
function analyzeSymbol(symbol) {
    // Show loading state
    analysisResults.classList.add('d-none');
    
    // Fetch analysis from API
    fetch(`/api/analyze/${symbol}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayAnalysis(data.result);
            } else {
                alert(`Error analyzing ${symbol}: ${data.error}`);
            }
        })
        .catch(error => {
            console.error(`Error analyzing ${symbol}:`, error);
            alert(`Error analyzing ${symbol}. Please try again.`);
        });
}

/**
 * Display analysis results
 */
function displayAnalysis(result) {
    // Market Context
    document.getElementById('trendValue').textContent = result.market_context.trend;
    document.getElementById('trendValue').className = `trend-${result.market_context.trend}`;
    
    document.getElementById('sentimentValue').textContent = result.market_context.sentiment;
    document.getElementById('momentumValue').textContent = result.market_context.momentum;
    document.getElementById('pcrValue').textContent = result.market_context.pcr.toFixed(2);
    document.getElementById('rsiValue').textContent = result.market_context.rsi.toFixed(2);
    document.getElementById('stochRsiValue').textContent = result.market_context.stoch_rsi.toFixed(2);
    document.getElementById('currentPriceValue').textContent = `$${result.current_price.toFixed(2)}`;
    
    // Key Levels
    const supportLevels = document.getElementById('supportLevels');
    supportLevels.innerHTML = '';
    result.key_levels.support.forEach(level => {
        const li = document.createElement('li');
        li.textContent = `$${level.toFixed(2)}`;
        supportLevels.appendChild(li);
    });
    
    const resistanceLevels = document.getElementById('resistanceLevels');
    resistanceLevels.innerHTML = '';
    result.key_levels.resistance.forEach(level => {
        const li = document.createElement('li');
        li.textContent = `$${level.toFixed(2)}`;
        resistanceLevels.appendChild(li);
    });
    
    document.getElementById('maxPainValue').textContent = result.key_levels.max_pain ? `$${result.key_levels.max_pain.toFixed(2)}` : 'N/A';
    
    const highGammaStrikes = document.getElementById('highGammaStrikes');
    highGammaStrikes.innerHTML = '';
    
    // Check if high_gamma exists and is an array
    if (result.key_levels.high_gamma && Array.isArray(result.key_levels.high_gamma)) {
        result.key_levels.high_gamma.forEach(strike => {
            const li = document.createElement('li');
            li.textContent = `$${strike.toFixed(2)}`;
            highGammaStrikes.appendChild(li);
        });
    } else {
        // Add a placeholder if no high gamma strikes
        const li = document.createElement('li');
        li.textContent = 'No high gamma strikes found';
        li.className = 'text-muted';
        highGammaStrikes.appendChild(li);
    }
    
    // Trade Setup
    document.getElementById('setupValue').textContent = result.setup;
    document.getElementById('confidenceValue').textContent = result.confidence.toFixed(1);
    
    const setupReasons = document.getElementById('setupReasons');
    setupReasons.innerHTML = '';
    result.reasons.forEach(reason => {
        const li = document.createElement('li');
        li.textContent = reason;
        setupReasons.appendChild(li);
    });
    
    document.getElementById('entrySignalValue').textContent = result.entry_signal ? 'Yes' : 'No';
    document.getElementById('entryStrengthValue').textContent = result.entry_strength.toFixed(1);
    
    const entryReasons = document.getElementById('entryReasons');
    entryReasons.innerHTML = '';
    result.entry_reasons.forEach(reason => {
        const li = document.createElement('li');
        li.textContent = reason;
        entryReasons.appendChild(li);
    });
    
    document.getElementById('exitSignalValue').textContent = result.exit_signal ? 'Yes' : 'No';
    document.getElementById('exitStrengthValue').textContent = result.exit_strength.toFixed(1);
    
    const exitReasons = document.getElementById('exitReasons');
    exitReasons.innerHTML = '';
    result.exit_reasons.forEach(reason => {
        const li = document.createElement('li');
        li.textContent = reason;
        exitReasons.appendChild(li);
    });
    
    // Risk Management
    document.getElementById('positionSizeValue').textContent = (result.position_size * 100).toFixed(2);
    document.getElementById('stopLossValue').textContent = `$${result.stop_loss.toFixed(2)}`;
    document.getElementById('targetPriceValue').textContent = `$${result.target_price.toFixed(2)}`;
    document.getElementById('riskRewardValue').textContent = result.risk_reward.toFixed(2);

    // Options Metrics Numerical Display
    const optionsMetrics = result.options_metrics || {};
    const gexData = optionsMetrics.gex || {};
    const vwivData = optionsMetrics.vwiv || {};
    const keyLevels = result.key_levels || {};

    // Format GEX value (e.g., K for thousands, M for millions)
    let gexValueStr = 'N/A';
    if (gexData.total_gex !== undefined && gexData.total_gex !== null) {
         const gexVal = gexData.total_gex;
         if (Math.abs(gexVal) >= 1e9) gexValueStr = (gexVal / 1e9).toFixed(1) + 'B';
         else if (Math.abs(gexVal) >= 1e6) gexValueStr = (gexVal / 1e6).toFixed(1) + 'M';
         else if (Math.abs(gexVal) >= 1e3) gexValueStr = (gexVal / 1e3).toFixed(0) + 'K';
         else gexValueStr = gexVal.toFixed(0);
    }
    // Check if element exists before setting text content
    const gexValueEl = document.getElementById('gexValue');
    if (gexValueEl) gexValueEl.textContent = gexValueStr;


    // Format VWIV value (as percentage)
    let vwivValueStr = 'N/A';
     if (vwivData.vwiv !== undefined && vwivData.vwiv !== null) {
          vwivValueStr = (vwivData.vwiv * 100).toFixed(2) + '%';
     }
     const vwivValueEl = document.getElementById('vwivValue');
     if (vwivValueEl) vwivValueEl.textContent = vwivValueStr;
    
    // Max Pain (already available in key_levels) - Use the new ID
    const maxPainValueEl = document.getElementById('maxPainValue2');
    if (maxPainValueEl) maxPainValueEl.textContent = keyLevels.max_pain ? `$${keyLevels.max_pain.toFixed(2)}` : 'N/A';

    // Create charts
    createEmaChart(result);
    createLevelsChart(result);
    createRiskRewardChart(result);
    
    // Fetch and display options metrics
    fetchOptionsMetrics(result.symbol);
    
    // Show results
    analysisResults.classList.remove('d-none');
}

/**
 * Create EMA chart using historical data
 */
function createEmaChart(result) {
    // Destroy existing chart if it exists
    if (emaChart) {
        emaChart.destroy();
    }
    
    const ctx = document.getElementById('emaChart').getContext('2d');
    
    // Check if historical data exists in the result
    const chartData = result.historical_chart_data;
    if (!chartData || !chartData.dates || chartData.dates.length === 0) {
         console.warn("Historical chart data not found or empty in analysis result for EMA chart.");
         // Optionally display a message on the canvas or clear it
         // ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height); // Example clear
         // ctx.fillText("No historical data for EMA chart.", 10, 50);
         return;
    }

    // Create new chart with historical data
    emaChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.dates, // Use historical dates
            datasets: [
                {
                    label: 'Price',
                    data: chartData.price, // Use historical prices
                    borderColor: '#343a40', // Darker color for price
                    borderWidth: 2,
                    pointRadius: 0, // No points for cleaner line
                    tension: 0.1 // Slight curve
                },
                {
                    label: '10 EMA',
                    data: chartData.ema10, // Use historical EMA10
                    borderColor: '#007bff', // Blue
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.1
                },
                {
                    label: '20 EMA',
                    data: chartData.ema20, // Use historical EMA20
                    borderColor: '#fd7e14', // Orange
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.1
                },
                {
                    label: '50 EMA',
                    data: chartData.ema50, // Use historical EMA50
                    borderColor: '#dc3545', // Red
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.1
                }
            ]
        },
        options: {
             responsive: true,
             maintainAspectRatio: false, // Allow chart to fill container height
             plugins: {
                  zoom: { // Enable zoom plugin
                       pan: {
                            enabled: true,
                            mode: 'xy', // Enable panning in both directions
                       },
                       zoom: {
                            wheel: {
                                 enabled: true, // Enable zooming with mouse wheel
                            },
                            pinch: {
                                 enabled: true, // Enable zooming with pinch gesture
                            },
                            mode: 'xy', // Enable zooming in both directions
                       }
                  },
                  legend: {
                       position: 'top',
                  },
                  tooltip: {
                       mode: 'index', // Show tooltips for all datasets at the same x-index
                       intersect: false, // Tooltip appears even if not directly hovering over point
                  }
             },
            scales: {
                x: {
                     ticks: {
                          maxTicksLimit: 10, // Limit number of x-axis labels for readability
                          autoSkip: true, // Automatically skip labels if they overlap
                     }
                },
                y: {
                    beginAtZero: false,
                    ticks: {
                         // Format y-axis ticks as currency
                         callback: function(value, index, values) {
                              return '$' + value.toFixed(2);
                         }
                    }
                }
            }
        }
    });
}

/**
 * Create Levels chart
 */
function createLevelsChart(result) {
    // Destroy existing chart if it exists
    if (levelsChart) {
        levelsChart.destroy();
    }
    
    // Prepare data for scatter chart
    const datasets = [];
    const currentPrice = result.current_price;
    const supports = result.key_levels.support || [];
    const resistances = result.key_levels.resistance || [];
    const maxPain = result.key_levels.max_pain;

    // Current Price Dataset
    datasets.push({
        label: 'Current Price',
        data: [{ x: 0.5, y: currentPrice }], // Position in the middle
        backgroundColor: '#000000', // Black
        pointRadius: 6,
        pointHoverRadius: 8
    });

    // Support Levels Dataset
    datasets.push({
        label: 'Support',
        data: supports.map(level => ({ x: 0, y: level })), // Position on the left
        backgroundColor: '#28a745', // Green
        pointStyle: 'rect', // Use squares for support
        pointRadius: 5,
        pointHoverRadius: 7
    });

    // Resistance Levels Dataset
    datasets.push({
        label: 'Resistance',
        data: resistances.map(level => ({ x: 1, y: level })), // Position on the right
        backgroundColor: '#dc3545', // Red
        pointStyle: 'triangle', // Use triangles for resistance
        rotation: 180, // Point triangles down
        pointRadius: 5,
        pointHoverRadius: 7
    });
    
    // Max Pain Dataset (Optional)
    if (maxPain !== undefined && maxPain !== null) {
         datasets.push({
              label: 'Max Pain',
              data: [{ x: 0.5, y: maxPain }], // Position in the middle with price
              backgroundColor: '#6c757d', // Grey
              pointStyle: 'crossRot', // Use rotated cross
              pointRadius: 6,
              pointHoverRadius: 8
         });
    }

    // Create chart
    const ctx = document.getElementById('levelsChart').getContext('2d');
    levelsChart = new Chart(ctx, {
        type: 'scatter', // Change type to scatter
        data: {
            // No labels needed for scatter x-axis representing categories
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
             plugins: {
                  zoom: { // Enable zoom plugin
                       pan: {
                            enabled: true,
                            mode: 'y', // Only pan vertically
                       },
                       zoom: {
                            wheel: { enabled: true },
                            pinch: { enabled: true },
                            mode: 'y', // Only zoom vertically
                       }
                  },
                  legend: {
                       position: 'top',
                  },
                  tooltip: {
                       callbacks: {
                            label: function(context) {
                                 let label = context.dataset.label || '';
                                 if (label) {
                                      label += ': ';
                                 }
                                 if (context.parsed.y !== null) {
                                      label += '$' + context.parsed.y.toFixed(2);
                                 }
                                 return label;
                            }
                       }
                  }
             },
            scales: {
                x: {
                    // Hide x-axis labels and grid lines as it's categorical
                    display: false,
                    min: -0.5, // Add padding
                    max: 1.5   // Add padding
                },
                y: {
                    beginAtZero: false,
                    title: {
                         display: true,
                         text: 'Price Level'
                    },
                     ticks: {
                         callback: function(value, index, values) {
                              return '$' + value.toFixed(2);
                         }
                    }
                }
            }
        },
    });
}

/**
 * Create Risk Reward chart
 */
function createRiskRewardChart(result) {
    // Destroy existing chart if it exists
    if (riskRewardChart) {
        riskRewardChart.destroy();
    }
    
    // Prepare data for scatter chart
    const datasets = [];
    const currentPrice = result.current_price;
    const stopLoss = result.stop_loss;
    const targetPrice = result.target_price;

    // Current Price Dataset
    datasets.push({
        label: 'Current Price',
        data: [{ x: 0.5, y: currentPrice }], // Position in the middle
        backgroundColor: '#000000', // Black
        pointRadius: 6,
        pointHoverRadius: 8
    });

    // Stop Loss Dataset
    datasets.push({
        label: 'Stop Loss',
        data: [{ x: 0, y: stopLoss }], // Position on the left
        backgroundColor: '#dc3545', // Red
        pointStyle: 'rect', // Square
        pointRadius: 5,
        pointHoverRadius: 7
    });

    // Target Price Dataset
    datasets.push({
        label: 'Target Price',
        data: [{ x: 1, y: targetPrice }], // Position on the right
        backgroundColor: '#28a745', // Green
        pointStyle: 'triangle', // Triangle
        pointRadius: 5,
        pointHoverRadius: 7
    });
    
    // Create chart
    const ctx = document.getElementById('riskRewardChart').getContext('2d');
    riskRewardChart = new Chart(ctx, {
        type: 'scatter', // Change type to scatter
        data: {
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
             plugins: {
                  zoom: { // Enable zoom plugin
                       pan: {
                            enabled: true,
                            mode: 'y', // Only pan vertically
                       },
                       zoom: {
                            wheel: { enabled: true },
                            pinch: { enabled: true },
                            mode: 'y', // Only zoom vertically
                       }
                  },
                  legend: {
                       position: 'top',
                  },
                  tooltip: {
                       callbacks: {
                            label: function(context) {
                                 let label = context.dataset.label || '';
                                 if (label) {
                                      label += ': ';
                                 }
                                 if (context.parsed.y !== null) {
                                      label += '$' + context.parsed.y.toFixed(2);
                                 }
                                 return label;
                            }
                       }
                  }
             },
            scales: {
                x: {
                    // Hide x-axis labels and grid lines
                    display: false,
                    min: -0.5, // Add padding
                    max: 1.5   // Add padding
                },
                y: {
                    beginAtZero: false,
                    title: {
                         display: true,
                         text: 'Price Level'
                    },
                     ticks: {
                         callback: function(value, index, values) {
                              return '$' + value.toFixed(2);
                         }
                    }
                }
            }
        }
    });
}
