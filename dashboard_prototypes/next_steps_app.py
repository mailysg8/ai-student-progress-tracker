from pathlib import Path
import numpy as np
import re
import pandas as pd
import networkx as nx
import plotly.graph_objects as go

from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget

from training_agenda_utils import *

####################################################################################
### UI
####################################################################################
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

dashboard_page = ui.nav_panel("Dashboard", banner, student_picker,
                            metric_row, graph_card, agenda_card)
home_page = ui.nav_panel("Home", ui.div())

app_ui = ui.page_navbar(home_page, dashboard_page,
                        title="Stellar Education", header=custom_css, fillable=True)

####################################################################################
### SERVER
####################################################################################
def server(input, output, session):

    @reactive.calc
    def tbl():
        return student_mkc_table(input.student())   # per-student entry point

    @reactive.calc
    def mastery_map():
        t = tbl()
        return dict(zip(t["modeling_kc_id"], t["mastery"]))

    @reactive.calc
    def readiness():
        return exam_readiness(tbl())

    # ---- coloured KPI cards (rendered reactively so colour reflects context) ----
    def vbox(title, value, bg):
        return ui.value_box(title, value,
                            theme=ui.value_box_theme(bg=bg, fg="white"),
                            max_height="92px")

    @render.ui
    def kc_box():
        n = int((tbl()["mastery"] >= MASTERY_THRESHOLD).sum())
        return vbox("KCs mastered", f"{n} / {TOTAL_MKCS}", "#0E7C86")

    @render.ui
    def readiness_box():
        band, bg = level_band(readiness())
        return vbox("Exam Readiness", f"{readiness():.0%}", bg)

    @render.ui
    def level_box():
        band, bg = level_band(readiness())
        return vbox("Your Level", band, bg)

    @render.ui
    def blocked_box():
        nb = len(find_blocked(mastery_map()))
        bg = "#60D394" if nb == 0 else "#EE6055" #"#a63c06" #ffd100 #"#e8c93f" #("#FFD97D" if nb <= 2 else "#EE6055")
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

