/**
 * Chart Manager for EOS Connect
 * Handles chart creation, updates and display functionality
 * Extracted from legacy index.html
 */

class ChartManager {
    constructor() {
        this.chartInstance = null;
        console.log('[ChartManager] Initialized');
    }

    /**
     * Initialize chart manager
     */
    init() {
        console.log('[ChartManager] Manager initialized');
    }

    /**
     * Update existing chart with new data
     */
    updateChart(data_request, data_response) {
        if (!this.chartInstance) {
            console.warn('[ChartManager] No chart instance to update');
            return;
        }

        // Use server timestamp consistently for data processing
        const serverTime = new Date(data_response["timestamp"]);
        const currentHour = serverTime.getHours();

        // Create labels in user's local timezone - showing only hours with :00
        this.chartInstance.data.labels = Array.from({ length: data_response["result"]["Last_Wh_pro_Stunde"].length },
            (_, i) => {
                // Create a new date object for each hour label in user's timezone
                const labelTime = new Date(serverTime.getTime() + (i * 60 * 60 * 1000));
                const hour = labelTime.getHours();
                return `${hour.toString().padStart(2, '0')}:00`;
            });

        // Calculate consumption (excluding home appliances)
        this.chartInstance.data.datasets[0].data = data_response["result"]["Last_Wh_pro_Stunde"].map((value, index) => {
            const actHomeApplianceValue = data_response["result"]["Home_appliance_wh_per_hour"].map(value => value)
            return ((value - actHomeApplianceValue[index]) / 1000).toFixed(3);
        });

        // Home appliances
        this.chartInstance.data.datasets[1].data = data_response["result"]["Home_appliance_wh_per_hour"].map(value => (value / 1000).toFixed(3));

        // PV forecast
        this.chartInstance.data.datasets[2].data = data_request["ems"]["pv_prognose_wh"].slice(currentHour).concat(data_request["ems"]["pv_prognose_wh"].slice(24, 48)).map(value => (value / 1000).toFixed(3));

        // Prepare arrays for grid and AC charge with redistribution logic
        const gridData = [];
        const acChargeData = [];

        data_response["result"]["Netzbezug_Wh_pro_Stunde"].forEach((value, index) => {
            const originalAcChargeValue = data_response["ac_charge"].slice(currentHour).concat(data_response["ac_charge"].slice(24, 48))[index] * max_charge_power_w;
            let gridValue = (value - originalAcChargeValue) / 1000;
            let adjustedAcChargeValue = originalAcChargeValue / 1000;

            // Validation for invalid numbers
            if (isNaN(gridValue) || !isFinite(gridValue)) {
                console.warn(`Invalid grid calculation at index ${index}: Netzbezug=${value}, AC_charge=${originalAcChargeValue}, using 0 for grid`);
                gridValue = 0;
                adjustedAcChargeValue = (value / 1000); // Treat all as AC charge
            }
            // If calculated grid value would be negative, show actual grid data and planned AC charge
            else if (gridValue < 0) {
                console.info(`Negative calculated grid at index ${index}: ${gridValue.toFixed(3)}kW, showing actual Netzbezug=${(value / 1000).toFixed(3)}kW and planned AC charge=${(originalAcChargeValue / 1000).toFixed(3)}kW`);
                // Show actual grid consumption/feed-in from Netzbezug_Wh_pro_Stunde
                gridValue = value / 1000;
                // Show planned AC charge
                adjustedAcChargeValue = originalAcChargeValue / 1000;
            }

            gridData.push(gridValue.toFixed(3));
            acChargeData.push(adjustedAcChargeValue.toFixed(3));
        });

        // Set the calculated data
        this.chartInstance.data.datasets[3].data = gridData; // Grid consumption
        this.chartInstance.data.datasets[4].data = acChargeData; // AC charging (adjusted)

        // Rest of the datasets remain unchanged
        this.chartInstance.data.datasets[5].data = data_response["result"]["akku_soc_pro_stunde"];
        this.chartInstance.data.datasets[6].data = data_response["result"]["Kosten_Euro_pro_Stunde"];
        this.chartInstance.data.datasets[7].data = data_response["result"]["Einnahmen_Euro_pro_Stunde"];
        this.chartInstance.data.datasets[8].data = data_response["result"]["Electricity_price"].map(value => value * 1000);
        this.chartInstance.data.datasets[9].data = data_response["discharge_allowed"].slice(currentHour).concat(data_response["discharge_allowed"].slice(24, 48));

        this.chartInstance.update('none'); // Update without animation
    }

    /**
     * Create new chart instance
     */
    createChart(data_request, data_response) {
        const ctx = document.getElementById('energyChart').getContext('2d');
        this.chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    { label: 'Load', data: [], backgroundColor: 'rgba(75, 192, 192, 0.2)', borderColor: 'rgba(75, 192, 192, 1)', borderWidth: 1, stack: 'load' },
                    { label: 'Home Appliance', data: [], backgroundColor: 'rgba(172, 41, 0, 0.4)', borderColor: 'rgba(172, 41, 0, 1)', borderWidth: 1, stack: 'load' },
                    { label: 'PV forecast', data: [], backgroundColor: '#FFA500', borderColor: '#FF991C', borderWidth: 1, stack: 'combined' },
                    { label: 'Grid', data: [], backgroundColor: 'rgba(128, 128, 128, 0.6)', borderColor: 'rgba(211, 211, 211, 0.7)', borderWidth: 1, stack: 'combined' },
                    { label: 'AC Charge', data: [], backgroundColor: 'darkred', borderColor: 'rgba(255, 0, 0, 0.2)', borderWidth: 1, stack: 'combined' },
                    { label: 'Akku SOC', data: [], type: 'line', backgroundColor: 'blue', borderColor: 'lightblue', borderWidth: 1, yAxisID: 'y2' },
                    { label: 'Expense', data: [], type: 'line', borderColor: 'lightgreen', backgroundColor: 'green', borderWidth: 1, yAxisID: 'y1', stepped: true, hidden: true },
                    { label: 'Income', data: [], type: 'line', borderColor: 'lightyellow', backgroundColor: 'yellow', borderWidth: 1, yAxisID: 'y1', stepped: true, hidden: true },
                    { label: 'Electricity Price', data: [], type: 'line', borderColor: 'rgba(255, 69, 0, 0.8)', backgroundColor: 'rgba(255, 165, 0, 0.2)', borderWidth: 1, yAxisID: 'y1', stepped: true },
                    { label: 'Discharge Allowed', data: [], type: 'line', borderColor: 'rgba(144, 238, 144, 0.3)', backgroundColor: 'rgba(144, 238, 144, 0.05)', borderWidth: 1, fill: true, yAxisID: 'y3' }
                ]
            },
            options: {
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'Energy (kWh)', color: 'lightgray' }, grid: { color: 'rgb(54, 54, 54)' }, ticks: { color: 'lightgray' } },
                    y1: { beginAtZero: true, position: 'right', title: { display: true, text: 'Price (€)', color: 'lightgray' }, grid: { drawOnChartArea: false }, ticks: { color: 'lightgray', callback: value => value.toFixed(2) } },
                    y2: { beginAtZero: true, position: 'right', title: { display: true, text: 'Akku SOC (%)', color: 'darkgray' }, grid: { drawOnChartArea: false }, ticks: { color: 'darkgray', callback: value => value.toFixed(0) } },
                    y3: { beginAtZero: true, position: 'right', display: false, title: { display: true, text: 'AC Charge', color: 'darkgray' }, grid: { drawOnChartArea: false }, ticks: { color: 'darkgray', callback: value => value.toFixed(2) } },
                    x: { grid: { color: 'rgb(54, 54, 54)' }, ticks: { color: 'lightgray', font: { size: 10 } } }
                },
                plugins: {
                    legend: { display: !isMobile(), labels: { color: 'lightgray' } }
                },
            }
        });
        
        // Set global reference for legacy compatibility
        chartInstance = this.chartInstance;
        
        this.updateChart(data_request, data_response); // Feed the content immediately after creation
    }

    /**
     * Update legend visibility based on screen size
     */
    updateLegendVisibility() {
        if (this.chartInstance) {
            this.chartInstance.options.plugins.legend.display = !isMobile();
            if (!this.chartInstance.options.scales.y.ticks.font)
                this.chartInstance.options.scales.y.ticks.font = {};
            this.chartInstance.options.scales.y.ticks.font.size = isMobile() ? 8 : 12;

            if (!this.chartInstance.options.scales.y1.ticks.font)
                this.chartInstance.options.scales.y1.ticks.font = {};
            this.chartInstance.options.scales.y1.ticks.font.size = isMobile() ? 8 : 12;

            if (!this.chartInstance.options.scales.y2.ticks.font)
                this.chartInstance.options.scales.y2.ticks.font = {};
            this.chartInstance.options.scales.y2.ticks.font.size = isMobile() ? 8 : 12;

            if (!this.chartInstance.options.scales.x.ticks.font)
                this.chartInstance.options.scales.x.ticks.font = {};
            this.chartInstance.options.scales.x.ticks.font.size = isMobile() ? 8 : 12;

            this.chartInstance.options.scales.y.title.display = !isMobile();
            this.chartInstance.options.scales.y1.title.display = !isMobile();
            this.chartInstance.options.scales.y2.title.display = !isMobile();

            this.chartInstance.update();
        }
    }
}

// Legacy compatibility functions
function createChart(data_request, data_response) {
    if (chartManager) {
        chartManager.createChart(data_request, data_response);
    }
}

function updateChart(data_request, data_response) {
    if (chartManager) {
        chartManager.updateChart(data_request, data_response);
    }
}

function updateLegendVisibility() {
    if (chartManager) {
        chartManager.updateLegendVisibility();
    }
}
