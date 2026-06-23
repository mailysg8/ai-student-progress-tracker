"""Student Portal — Shiny application entry point.

A hybrid Shiny app providing two views:
  * Student Summary  — embedded HTML dashboard with KPI cards, unit-level
    BKT mastery distributions, and per-skill drill-downs.
  * My Practice Plan — BKT-driven personalised recommendations with a
    prerequisite-aware Sankey graph and next-steps agenda.

Both tabs share the logged-in student via a single reactive.value.

Run locally:
    conda activate stellar-proj
    shiny run --reload student_app.py

Data files (placed locally before running):
    data/raw/final_data.xlsx
    data/raw/mkc_mapping_pack_v1.0..xlsx
    data/processed/final_student_kc_data.csv
"""
import base64
import plotly.graph_objects as go
from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget

from src.training_agenda_utils import *
from src.build_student_summary import build_html, scores


VALID_IDS = sorted(scores["student_id"].unique())


# ─── UI fragments ─────────────────────────────────────────────────────────────
def login_card_ui():
    """Build the login card shown when no student is logged in.

    Renders a single centred card containing the welcome message, a student-ID
    text input, the "Log in" button, and a placeholder for the validation
    error message (populated by the ``login_msg`` server output).

    Returns
    -------
    shiny.ui.Tag
        The login card as a Shiny UI element.
    """
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


def practice_plan_static_ui():
    """STATIC Practice Plan UI — always rendered in app_ui so the Sankey widget
    ID stays stable across logout/login. Visibility controlled by CSS injected
    from practice_plan_login_gate().
    """
    howto = ui.div(
        ui.HTML(
            "💡 <b>How these cards work:</b> These show where you stand right "
            "now and what to focus on. Each card highlights a different aspect "
            "of your current learning state."
        ),
        style=(
            "background:rgba(255,255,255,0.05);"
            "border:1px solid rgba(255,255,255,0.12);"
            "border-left:3px solid #FFD97D;"
            "border-radius:0 6px 6px 0;"
            "padding:10px 14px;font-size:12.5px;line-height:1.55;"
            "color:#D0D7DE;margin:0 0 14px 0;"
        ),
    )
    metric_row = ui.layout_columns(
        ui.output_ui("kc_box"),
        ui.output_ui("readiness_box"),
        ui.output_ui("level_box"),
        ui.output_ui("blocked_box"),
        col_widths=(3, 3, 3, 3), fill=False, class_="metric-row",
    )
    graph_card = ui.card(
        ui.card_header(
            ui.div(
                "KC Prerequisite Graph: Your Mastery at a Glance",
                ui.input_select(
                    "kc_view", None,
                    choices=[OVERVIEW_LABEL] + UNIT_LIST,
                    selected=OVERVIEW_LABEL, width="240px",
                ),
                class_="kc-head",
            )
        ),
        output_widget("sankey", fillable=True),
        class_="section-card", height="380px", full_screen=True, fill=True,
    )
    agenda_card = ui.card(
        ui.card_header("🌟 Your Personalized Next Steps & Training Agenda"),
        ui.output_ui("agenda"),
        class_="section-card", height="440px", full_screen=True,
    )
    return ui.div(
        howto, metric_row, graph_card, agenda_card,
        id="practice_plan_root",
        style="padding:16px 24px;",
    )


# ─── App UI ───────────────────────────────────────────────────────────────────
app_ui = ui.page_navbar(
    ui.nav_panel("Student Summary",  ui.output_ui("summary_panel")),
    ui.nav_panel(
        "My Practice Plan",
        ui.output_ui("practice_plan_login_gate"),  # CSS show/hide + login msg
        practice_plan_static_ui(),                  # static — widget IDs stable
    ),
    ui.nav_spacer(),
    ui.nav_control(
        ui.output_ui("logout_area")
    ),
    ui.head_content(
        ui.tags.style(
            """
            .navbar-nav .nav-link,
            .navbar-nav .nav-link.active   { color: #F5F7FA !important; }
            .nav-tabs .nav-link            { color: #8B9DBB !important; }
            .nav-tabs .nav-link.active     { color: #263744 !important; font-weight: 500; }
            .quarto-grid-container,
            .nav-tabs + .tab-content,
            .tab-pane                      { padding: 0 !important; }
            """
        ),
        custom_css,
        # JS: listen for iframe postMessage AND handle Enter key on login input
        ui.tags.script(
            """
            // Iframe's "View my practice plan →" button posts this message
            window.addEventListener('message', function(e) {
              if (e.data === 'go-practice-plan') {
                Shiny.setInputValue('jump_to_plan', Date.now());
              }
            });

            // Enter-key submits the login form. Event delegation so it works
            // even after logout/login re-renders the input. blur() forces
            // Shiny to flush the input value before the button click.
            document.addEventListener('keydown', function(e){
              if(e.target && e.target.id === 'login_id' && e.key === 'Enter'){
                e.preventDefault();
                e.target.blur();
                setTimeout(function(){
                  var btn = document.getElementById('login_btn');
                  if(btn) btn.click();
                }, 120);
              }
            });
            """
        ),
    ),
    title=ui.tags.span("Stellar Education — Student Portal", style="color:white;"),
    navbar_options=ui.navbar_options(bg="#263744"),
    id="main_navbar",
)


# ─── Server ───────────────────────────────────────────────────────────────────
def server(input, output, session):
    """Wire up reactive outputs for the Student Portal Shiny app.

    Maintains a single reactive ``logged_in`` value that holds the active
    student ID (or ``None``). All renderers in both tabs gate their content
    on this value so login state is the single source of truth across the
    Student Summary and My Practice Plan views.

    Parameters
    ----------
    input : shiny.module.Inputs
        Shiny input proxy.
    output : shiny.module.Outputs
        Shiny output proxy.
    session : shiny.Session
        Active Shiny session.
    """
    logged_in = reactive.value(None)  # holds the student_id or None

    # ── login / logout handlers ─────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.login_btn)
    def _do_login():
        """Validate the entered student ID and update the ``logged_in`` value.

        Triggered by a click on the "Log in" button. The input is uppercased
        and stripped before validation; if it matches a valid student ID,
        ``logged_in`` is set, which causes every downstream renderer to
        re-evaluate with the new student's data.
        """
        sid = (input.login_id() or "").strip().upper()
        if sid in VALID_IDS:
            logged_in.set(sid)

    @reactive.effect
    @reactive.event(input.logout_btn, ignore_none=True, ignore_init=True)
    def _do_logout():
        """Clear the logged-in student and return to the Student Summary tab.

        Triggered by a click on the "Log out" button. Resets ``logged_in`` to
        ``None`` and switches the active navbar tab back to Student Summary so
        the login form is immediately visible.
        """
        logged_in.set(None)
        # Auto-return to Student Summary tab so the login form is immediately visible
        ui.update_navs("main_navbar", selected="Student Summary")

    @render.text
    def login_msg():
        """Render the login error message when an invalid student ID is entered.

        Returns
        -------
        str
            An empty string while no login has been attempted, or a
            human-readable hint listing the valid student-ID range when the
            most recent attempt failed.
        """
        if input.login_btn() and logged_in.get() is None:
            return (
                f"Student ID not found. Valid IDs run from "
                f"{VALID_IDS[0]} to {VALID_IDS[-1]}."
            )
        return ""

    # ── logout button ───────────────────────────────────────────────────────
    @render.ui
    def logout_area():
        """Render the "Logged in as: <sid> [Log out]" area in the navbar.

        Returns an empty span when no one is logged in (the navbar slot
        collapses), otherwise the student ID label and a Log out button.
        """
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

    # ── Student Summary tab ────────────────────────────────────────────────
    @render.ui
    def summary_panel():
        """Render the Student Summary tab.

        Shows the login card when no one is logged in (with the navbar tabs
        hidden so the login is the only available action), otherwise embeds
        the per-student dashboard generated by ``build_html`` inside an iframe.

        The embedded HTML is encoded as a base64 ``data:`` URL so the entire
        dashboard ships as a single self-contained Shiny output with no extra
        routes or assets.
        """
        sid = logged_in.get()
        if sid is None:
            # Login screen — hide the two nav tabs too (no point showing them
            # to a logged-out user; they only confuse and the login is the
            # single thing to do here).
            return ui.TagList(
                ui.tags.style(
                    """
                    .navbar-nav,
                    .navbar .nav,
                    ul.nav.navbar-nav,
                    .nav-tabs            { display: none !important; }
                    """
                ),
                login_card_ui(),
            )
        html = build_html(picks=[(sid, "")])
        b64 = base64.b64encode(html.encode()).decode()
        return ui.HTML(
            f'<iframe '
            f'  src="data:text/html;base64,{b64}" '
            f'  style="width:100%;height:calc(100vh - 60px);border:0;display:block;background:#1F303D;" '
            f'  title="Student Summary">'
            f'</iframe>'
        )

    # ── Practice Plan: login gate via CSS show/hide ─────────────────────────
    @render.ui
    def practice_plan_login_gate():
        """Toggle Practice Plan visibility via CSS rather than dynamic UI.

        The Practice Plan tab is rendered as static UI (see
        ``practice_plan_static_ui``) so its Sankey widget keeps a stable
        ID across logout/login cycles. This output injects a CSS rule that
        hides the static tree behind a "please log in" message when the
        session has no student, and reveals it again on login.
        """
        if logged_in.get() is None:
            return ui.TagList(
                ui.tags.style("#practice_plan_root { display: none !important; }"),
                ui.div(
                    ui.p(
                        "Please log in from the Student Summary tab first.",
                        style="margin:40px;color:#888780;text-align:center;",
                    )
                ),
            )
        return ui.tags.style("#practice_plan_root { display: block; }")

    # ── Handle iframe button → switch to Practice Plan tab ─────────────────
    @reactive.effect
    @reactive.event(input.jump_to_plan)
    def _jump():
        """Switch the active tab to "My Practice Plan".

        Triggered by a postMessage from the embedded Student Summary iframe
        when the student clicks the "View my practice plan →" CTA.
        """
        ui.update_navs("main_navbar", selected="My Practice Plan")

    # ── Practice Plan reactives (handle None gracefully) ───────────────────
    @reactive.calc
    def tbl():
        """Per-student MKC table used as the source of truth for the Plan view.

        Returns
        -------
        pandas.DataFrame
            The output of ``student_mkc_table`` for the currently logged-in
            student, or an empty DataFrame when no one is logged in.
        """
        sid = logged_in.get()
        if sid is None:
            return student_mkc_table("")  # returns empty DataFrame
        return student_mkc_table(sid)

    @reactive.calc
    def mastery_map():
        """Map every modeling-KC id to the student's current mastery probability.

        Used by Sankey rendering and the "Blocked KCs" computation.

        Returns
        -------
        dict[str, float]
            ``modeling_kc_id -> mastery`` (empty dict when no student is logged in).
        """
        t = tbl()
        if t.empty:
            return {}
        return dict(zip(t["modeling_kc_id"], t["mastery"]))

    @reactive.calc
    def readiness():
        """Compute the student's weighted exam-readiness score.

        Returns
        -------
        float
            A value in ``[0, 1]`` from ``exam_readiness``, or ``0.0`` when no
            student is logged in.
        """
        t = tbl()
        if t.empty:
            return 0.0
        return exam_readiness(t)

    def vbox(title, value, subtitle, bg):
        """Value box with title, big value, and an explanatory subtitle."""
        return ui.value_box(
            title,
            value,
            ui.span(
                subtitle,
                style="font-size:11px;opacity:0.88;display:block;margin-top:2px;line-height:1.3",
            ),
            theme=ui.value_box_theme(bg=bg, fg="white"),
            max_height="110px",
        )

    @render.ui
    def kc_box():
        """Render the "KCs mastered" KPI value box.

        Shows the count of modeling KCs whose mastery has reached
        ``MASTERY_THRESHOLD``, out of the total number of KCs in the course.
        Falls back to "—" when no one is logged in.
        """
        sub = "Skills you currently know well"
        t = tbl()
        if t.empty:
            return vbox("KCs mastered", "—", sub, "#0E7C86")
        n = int((t["mastery"] >= MASTERY_THRESHOLD).sum())
        return vbox("KCs mastered", f"{n} / {TOTAL_MKCS}", sub, "#0E7C86")

    @render.ui
    def readiness_box():
        """Render the "Exam Readiness" KPI value box.

        Shows the weighted exam-readiness percentage. The background colour
        matches the readiness band (mastered / progressing / needs practice).
        """
        sub = "How ready you are for the exam"
        if logged_in.get() is None:
            return vbox("Exam Readiness", "—", sub, "#888780")
        band, bg = level_band(readiness())
        return vbox("Exam Readiness", f"{readiness():.0%}", sub, bg)

    @render.ui
    def level_box():
        """Render the "Your Level" KPI value box.

        Shows the readiness band label (e.g. "Mastered", "Progressing",
        "Needs Practice") corresponding to the current readiness score.
        """
        sub = "Your overall standing right now"
        if logged_in.get() is None:
            return vbox("Your Level", "—", sub, "#888780")
        band, bg = level_band(readiness())
        return vbox("Your Level", band, sub, bg)

    @render.ui
    def blocked_box():
        """Render the "Blocked KCs" KPI value box.

        Shows the count of KCs the student cannot productively practise yet
        because their prerequisites are not mastered. Green when zero, coral
        otherwise.
        """
        sub = "Need to clear prerequisites first"
        if logged_in.get() is None:
            return vbox("Blocked KCs", "—", sub, "#888780")
        nb = len(find_blocked(mastery_map()))
        bg = "#60D394" if nb == 0 else "#EE6055"
        return vbox("Blocked KCs", str(nb), sub, bg)

    @render_widget
    def sankey():
        """Render the KC-prerequisite Sankey diagram for the active student.

        Always returns a Plotly figure (never ``None``) so the shinywidgets
        widget keeps a stable lifecycle across login/logout cycles. When no
        student is logged in, the figure is a blank canvas with an
        explanatory annotation. When a unit is selected from the
        ``kc_view`` dropdown, the figure switches to the unit-detail Sankey.
        """
        # Always return SOME figure to keep widget alive across login/logout
        if logged_in.get() is None:
            fig = go.Figure()
            fig.update_layout(
                paper_bgcolor="white",
                plot_bgcolor="white",
                annotations=[dict(
                    text="Log in to see your prerequisite graph",
                    showarrow=False,
                    font=dict(size=14, color="#888"),
                )],
            )
            return fig
        v = input.kc_view()
        if not v or v == OVERVIEW_LABEL:
            return build_unit_sankey(mastery_map())
        return build_unit_detail_sankey(v, mastery_map())

    @render.ui
    def agenda():
        """Render the personalised "Next Steps & Training Agenda" cards.

        Falls back to a "please log in" message when no student is active.
        Otherwise delegates to ``render_agenda_html`` which produces the
        ranked-list HTML directly.
        """
        t = tbl()
        if t.empty:
            return ui.HTML(
                "<div style='padding:24px;color:#888'>"
                "Log in to see your personalised agenda.</div>"
            )
        return ui.HTML(render_agenda_html(t))


app = App(app_ui, server)
