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
    .dashboard-subtitle {
    font-size: 1rem;
    font-style: italic;
    color: #FF9B85;
    margin-top: 3px;
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


banner = ui.div(
    ui.div(
        ui.h1("Welcome to Your Progress Dashboard"),
        ui.p("Let's see what you've accomplished!", class_="dashboard-subtitle"),
    ),
    ui.div(
        ui.div("Stellar Education", class_="brand-name"),
        ui.div(
            ui.span(class_="bar bar-red"),
            ui.span(class_="bar bar-yellow"),
            ui.span(class_="bar bar-dot"),
            class_="brand-bars",
        ),
        class_="brand"
    ),
    class_="dash-banner",
)

########## This is for the KPI metric cards on the "Your Next Steps" page ##########
metric_cards = ui.layout_columns(
    ui.value_box(
        "KCs Mastered",
        ui.output_text("kcs_mastered"),
        class_="metric-card",
    ),
    ui.value_box(
        "Overall Accuracy",
        ui.output_text("overall_accuracy"),
        class_="metric-card",
    ),
    ui.value_box(
        "Prior Performance Band",
        ui.output_text("prior_performance_band"),
        class_="metric-card",
    ),
    ui.value_box(
        "Blocked KCs",
        ui.output_text("blocked_kcs"),
        class_="metric-card",
    ),
    col_widths=(3, 3, 3, 3),
    fill=False,
)


# This is for Sitting's First Page
home_page = ui.nav_panel(
    "Home",
    #banner
)



student_next_steps_page = ui.nav_panel(
    "Your Next Steps",
    banner,
    metric_cards,
)


app_ui = ui.page_navbar(
    home_page,
    student_next_steps_page,
    #title="Stellar Education",
    header=custom_css,
    fillable=True
)


def server(input, output, session):
    pass


app = App(app_ui, server)