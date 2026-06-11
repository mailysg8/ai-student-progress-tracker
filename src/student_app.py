"""Standalone Shiny app — Student Dashboard (Student view).

Hybrid design:
  * Shiny handles login, tab navigation, and logout (matches Mailys's stack)
  * The Student Summary content is the rich interactive HTML mockup
    (clickable KPI cards, unit tiles with drill-down modals, sort toggle,
    class comparison panel) generated per-student by build_student_summary.py
    and embedded in an iframe.
  * "My Practice Plan" tab is a placeholder for Godsgift's branch.

Run locally:
    conda activate pybkt-demo
    shiny run --reload student_app.py

Data: reads data/raw/final_data.xlsx + data/raw/mkc_mapping_pack_v1.0..xlsx
(per team convention — place locally before running).
"""
import base64
from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
from training_agenda_utils import *

# build_html generates the per-student HTML mockup; scores DataFrame gives us
# the list of valid student IDs.
from build_student_summary import build_html, scores


VALID_IDS = sorted(scores["student_id"].unique())


# ─── UI fragments ─────────────────────────────────────────────────────────────
def login_card_ui():
    return ui.div(
        ui.h2(
            "Welcome to the Student Portal",
            style="margin-bottom:8px;color:#263744;font-family:Georgia,serif;",
        ),
        ui.p(
            "Enter your student ID to view your dashboard.",
            style="color:#888780;margin-bottom:20px;",
        ),
        ui.input_text("login_id", "", placeholder="e.g., S019"),
        ui.div(
            ui.input_action_button(
                "login_btn",
                "Log in",
                style=(
                    "background:#EE6055;color:#fff;border:0;border-radius:6px;"
                    "padding:8px 18px;font-weight:600;cursor:pointer;"
                ),
            ),
            style="margin-top:12px;",
        ),
        ui.div(
            ui.output_text("login_msg"),
            style="color:#EE6055;font-size:13px;margin-top:10px;",
        ),
        style=(
            "max-width:380px;margin:80px auto;padding:32px 36px;"
            "background:#fff;border:1px solid #E5E9EE;border-radius:10px;"
            "box-shadow:0 4px 20px rgba(15,27,38,0.06);"
        ),
    )


def practice_plan_ui():
    metric_row = ui.layout_columns(
        ui.output_ui("kc_box"), ui.output_ui("readiness_box"),
        ui.output_ui("level_box"), ui.output_ui("blocked_box"),
        col_widths=(3, 3, 3, 3), fill=False, class_="metric-row")

    graph_card = ui.card(
        ui.card_header(
            ui.div("KC Prerequisite Graph: Your Mastery at a Glance",
                ui.input_select("kc_view", None, choices=[OVERVIEW_LABEL] + UNIT_LIST,
                                selected=OVERVIEW_LABEL, width="240px"),
                class_="kc-head")),
        output_widget("sankey", fillable=True),
        class_="section-card", height="380px", full_screen=True, fill=True)

    agenda_card = ui.card(
        ui.card_header("🌟 Your Personalized Next Steps & Training Agenda"),
        ui.output_ui("agenda"),
        class_="section-card", height="440px", full_screen=True)

    return ui.div(metric_row, graph_card, agenda_card, style="padding:16px 24px;")


# ─── App UI ───────────────────────────────────────────────────────────────────
app_ui = ui.page_navbar(
    ui.nav_panel("Student Summary",  ui.output_ui("summary_panel")),
    ui.nav_panel("My Practice Plan", ui.output_ui("practice_panel")),
    ui.nav_spacer(),
    ui.nav_control(
        ui.output_ui("logout_area")  # dynamic: hidden when not logged in
    ),
    ui.head_content(
        ui.tags.style(
            """
            .navbar-nav .nav-link,
            .navbar-nav .nav-link.active   { color: #F5F7FA !important; }
            .nav-tabs .nav-link            { color: #8B9DBB !important; }
            .nav-tabs .nav-link.active     { color: #263744 !important; font-weight: 500; }
            /* Make the iframe content fill the page without margins */
            .quarto-grid-container,
            .nav-tabs + .tab-content,
            .tab-pane                      { padding: 0 !important; }
            """
        ),
        custom_css, 
        ui.tags.script("""
            window.addEventListener('message', function(e) {
            if (e.data === 'go-practice-plan') {
            Shiny.setInputValue('jump_to_plan', Date.now());
            }
            });
        """),
    ),
    title=ui.tags.span("Stellar Education — Student Portal", style="color:white;"),
    navbar_options=ui.navbar_options(bg="#263744"),
    id="main_navbar",
)


# ─── Server ───────────────────────────────────────────────────────────────────
def server(input, output, session):
    logged_in = reactive.value(None)  # holds the student_id or None

    # ── login / logout handlers ─────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.login_btn)
    def _do_login():
        sid = (input.login_id() or "").strip().upper()
        if sid in VALID_IDS:
            logged_in.set(sid)

    @reactive.effect
    @reactive.event(input.logout_btn, ignore_none=True, ignore_init=True)
    def _do_logout():
        logged_in.set(None)

    @render.text
    def login_msg():
        if input.login_btn() and logged_in.get() is None:
            return (
                f"Student ID not found. Valid IDs run from "
                f"{VALID_IDS[0]} to {VALID_IDS[-1]}."
            )
        return ""

    # ── logout button: only show when logged in (single instance) ───────────
    @render.ui
    def logout_area():
        if logged_in.get() is None:
            return ui.span("")
        return ui.div(
            ui.span(
                f"Logged in as: ",
                style="color:#B0BFD0;font-size:13px;margin-right:8px;",
            ),
            ui.span(
                logged_in.get(),
                style="color:#F5F7FA;font-weight:600;margin-right:12px;",
            ),
            ui.input_action_button(
                "logout_btn",
                "Log out",
                style=(
                    "background:transparent;color:#F5F7FA;"
                    "border:1px solid #5B7271;border-radius:6px;"
                    "padding:4px 12px;font-size:12px;cursor:pointer;"
                ),
            ),
            style="display:flex;align-items:center;padding-right:8px;",
        )

    # ── Student Summary tab: login form or embedded dashboard ───────────────
    @render.ui
    def summary_panel():
        sid = logged_in.get()
        if sid is None:
            return login_card_ui()

        # Generate the rich HTML mockup for THIS student
        html = build_html(picks=[(sid, "")])
        b64 = base64.b64encode(html.encode()).decode()

        return ui.HTML(
            f'<iframe '
            f'  src="data:text/html;base64,{b64}" '
            f'  style="width:100%;height:calc(100vh - 60px);border:0;display:block;background:#fff;" '
            f'  title="Student Summary">'
            f'</iframe>'
        )

    # ── Training Agenda Tab ────────────────────────────────────────────────
    @render.ui
    def practice_panel():
        sid = logged_in.get()
        if sid is None:
            return ui.div(ui.p("Please log in from the Student Summary tab first.",
                            style="margin:40px;color:#888780;text-align:center;"))
        return practice_plan_ui()
    
    @reactive.effect
    @reactive.event(input.jump_to_plan)
    def _jump():
        ui.update_navs("main_navbar", selected="My Practice Plan")

    @reactive.calc
    def tbl():
        sid = logged_in.get()              
        if sid is None:
            return student_mkc_table(None) 
        return student_mkc_table(sid)

    @reactive.calc
    def mastery_map():
        t = tbl()
        return dict(zip(t["modeling_kc_id"], t["mastery"]))

    @reactive.calc
    def readiness():
        return exam_readiness(tbl())

    def vbox(title, value, bg):
        return ui.value_box(title, value,
                            theme=ui.value_box_theme(bg=bg, fg="white"), max_height="92px")

    @render.ui
    def kc_box():
        n = int((tbl()["mastery"] >= MASTERY_THRESHOLD).sum())
        return vbox("KCs mastered", f"{n} / {TOTAL_MKCS}", "#0E7C86")

    @render.ui
    def readiness_box():
        band, bg = level_band(readiness());  return vbox("Exam Readiness", f"{readiness():.0%}", bg)

    @render.ui
    def level_box():
        band, bg = level_band(readiness());  return vbox("Your Level", band, bg)

    @render.ui
    def blocked_box():
        nb = len(find_blocked(mastery_map()))
        bg = "#60D394" if nb == 0 else "#EE6055"
        return vbox("Blocked KCs", str(nb), bg)

    @render_widget
    def sankey():
        v = input.kc_view()
        if not v or v == OVERVIEW_LABEL:
            return build_unit_sankey(mastery_map())
        return build_unit_detail_sankey(v, mastery_map())

    @render.ui
    def agenda():
        return ui.HTML(render_agenda_html(tbl()))   

app = App(app_ui, server)
