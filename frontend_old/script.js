document.addEventListener("DOMContentLoaded", () => {
    const dashboard = document.getElementById("dashboard");
    const initialLoading = document.getElementById("initial-loading");
    const errorToast = document.getElementById("error-message");
    const runBtn = document.getElementById("run-pipeline-btn");
    const btnText = runBtn.querySelector(".btn-text");
    const loader = runBtn.querySelector(".loader");
    
    let trendChartInstance = null;

    // Fetch initial report on load
    fetchReport();

    // Event Listener for Run Pipeline button
    runBtn.addEventListener("click", async () => {
        setLoadingState(true);
        try {
            const response = await fetch("/api/run", { method: "POST" });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || data.error || "Failed to run pipeline");
            
            updateDashboard(data.report);
            showError("Pipeline ran successfully!", true);
        } catch (err) {
            showError(err.message);
        } finally {
            setLoadingState(false);
        }
    });

    async function fetchReport() {
        try {
            const response = await fetch("/api/report");
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || data.error || "Failed to load report");
            }

            updateDashboard(data);
            
            initialLoading.classList.add("hidden");
            dashboard.classList.remove("hidden");
        } catch (err) {
            initialLoading.textContent = "No data found. Please run the pipeline.";
            showError(err.message);
        }
    }

    function updateDashboard(data) {
        if (!data || !data.risk_snapshot) return;

        // Hero Section
        const snap = data.risk_snapshot;
        document.getElementById("composite-risk").textContent = snap.composite_risk_score;
        document.getElementById("risk-date").textContent = `As of: ${snap.as_of_date}`;
        document.getElementById("weather-score").textContent = snap.weather_score;
        document.getElementById("logistics-score").textContent = snap.logistics_score;
        document.getElementById("shipment-score").textContent = snap.shipment_score;

        const badge = document.getElementById("risk-level-badge");
        badge.textContent = snap.risk_level;
        badge.className = `badge ${snap.risk_level}`;

        // Inventory
        const inv = data.inventory;
        document.getElementById("inv-critical").textContent = inv.critical_items;
        document.getElementById("inv-reorder").textContent = inv.reorder_items;
        document.getElementById("inv-overstock").textContent = inv.overstock_items;
        document.getElementById("inv-ok").textContent = inv.ok_items;

        // Exec Summary
        document.getElementById("exec-summary").textContent = data.executive_summary || "No summary available.";

        // Vendors Table
        const tbody = document.getElementById("vendor-tbody");
        tbody.innerHTML = "";
        if (data.top_vendor_risks && data.top_vendor_risks.length > 0) {
            data.top_vendor_risks.slice(0, 5).forEach(v => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${v.Vendor}</td>
                    <td><span style="color: var(--risk-high); font-weight: bold;">${v.delivery_score}</span> / 100</td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = `<tr><td colspan="2" style="text-align: center;">No high-risk vendors found.</td></tr>`;
        }

        // Chart
        updateChart(data.risk_trend_7d);
    }

    function updateChart(trend) {
        const ctx = document.getElementById("trendChart").getContext("2d");
        
        if (trendChartInstance) {
            trendChartInstance.destroy();
        }

        if (!trend || !trend.dates) return;

        // Colors
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, "rgba(59, 130, 246, 0.5)");
        gradient.addColorStop(1, "rgba(59, 130, 246, 0.0)");

        trendChartInstance = new Chart(ctx, {
            type: "line",
            data: {
                labels: trend.dates,
                datasets: [{
                    label: "Composite Risk Score",
                    data: trend.scores,
                    borderColor: "#3b82f6",
                    backgroundColor: gradient,
                    borderWidth: 3,
                    pointBackgroundColor: "#fff",
                    pointBorderColor: "#3b82f6",
                    pointRadius: 4,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: "rgba(255, 255, 255, 0.1)" },
                        ticks: { color: "#94a3b8" }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: "#94a3b8" }
                    }
                }
            }
        });
    }

    function setLoadingState(isLoading) {
        runBtn.disabled = isLoading;
        if (isLoading) {
            btnText.classList.add("hidden");
            loader.classList.remove("hidden");
        } else {
            btnText.classList.remove("hidden");
            loader.classList.add("hidden");
        }
    }

    function showError(msg, isSuccess = false) {
        errorToast.textContent = msg;
        errorToast.style.background = isSuccess ? "#22c55e" : "#ef4444";
        errorToast.classList.remove("hidden");
        setTimeout(() => {
            errorToast.classList.add("hidden");
        }, 5000);
    }
});
