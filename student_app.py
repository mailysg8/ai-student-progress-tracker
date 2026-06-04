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

# build_html generates the per-student HTML mockup; scores DataFrame gives us
# the list of valid student IDs.
from src.build_student_summary import build_html, scores


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
    return ui.div(
        ui.card(
            ui.card_header(
                ui.span(
                    "My Practice Plan",
                    style="font-size:20px;color:#263744;font-weight:600;",
                )
            ),
            ui.div(
                ui.p(
                    "Personalised practice recommendations will appear here.",
                    style="font-size:15px;color:#263744;margin-bottom:14px;",
                ),
                ui.p(
                    ui.tags.em(
                        "Coming soon — to be filled by Godsgift "
                        "(branch: feat/student_next_steps)."
                    ),
                    style="color:#888780;",
                ),
                ui.p(
                    "This page will show targeted exercises based on the weak "
                    "skills surfaced in the Student Summary tab.",
                    style="color:#888780;",
                ),
                style="padding:20px 24px;",
            ),
            style="margin:20px auto;max-width:760px;",
        ),
    )


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
        )
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

    # ── My Practice Plan tab ────────────────────────────────────────────────
    @render.ui
    def practice_panel():
        sid = logged_in.get()
        if sid is None:
            return ui.div(
                ui.p(
                    "Please log in from the Student Summary tab first.",
                    style="margin:40px;color:#888780;text-align:center;",
                )
            )
        return practice_plan_ui()


app = App(app_ui, server)
