from shiny import App, ui, render


custom_css = ui.tags.style(
    """
    /* App background */
    body { background-color: #263744; }
 
    /* Dark banner header inside the dashboard page */
    .dash-banner {
        background-color: #263744;
        color: #ffffff;
        padding: 18px 24px;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    .dash-banner h1 {
        font-size: 34px;
        font-weight: 800;
        margin: 0;
    }
    .brand { text-align: right; }
    .brand .brand-name { font-size: 20px; font-weight: 800; }
    .brand .brand-bars { margin-top: 6px; }
    .brand .bar {
        display: inline-block;
        height: 6px;
        border-radius: 4px;
        vertical-align: middle;
    }
    .brand .bar-red   { width: 46px; background:#EE6055; }
    .brand .bar-yellow{ width: 34px; background:#FFD97D; margin-left:6px; }
    .brand .bar-dot   { width: 6px;  background:#ffffff; margin-left:6px; }
 
    /* Metric value boxes */
    .metric-card .card-title { font-size: 20px; font-weight: 700; }
 
    /* Section cards */
    .section-card .card-header {
        font-size: 22px;
        font-weight: 700;
        background-color: #ffffff;
        border-bottom: none;
    }
    """
)
 