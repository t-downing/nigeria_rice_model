import dash
from dash import dcc
from dash import html
import pandas as pd
import numpy as np
from datetime import datetime
from dash.dependencies import Output, Input, State
import plotly.express as px
from model_operations import *
from import_data import *


# read in external data
df_input = import_all_data()

# initialize values ONLY FOR HTML
initial_start_date, initial_stop_date = datetime(2018, 1, 1), datetime.now()
model_env, model = setup_model(initial_start_date, initial_stop_date, df_input)
variables = [str(var) for var in model.stocks] \
            + [str(var) for var in model.flows] \
            + [str(var) for var in model.converters]
min_date = serial_to_datetime(1.0)
max_date = datetime.now()

# setup app
external_stylesheets = [
    {
        "href": "https://fonts.googleapis.com/css2?"
                "family=Lato:wght@400;700&display=swap",
        "rel": "stylesheet",
    },
]
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.title = "Ethiopia Livestock SD model"
server = app.server

# app layout
app.layout = html.Div(
    # whole app
    children=[
        html.Div(
            # header
            children=[
                html.P(children="", className="header-emoji"),
                html.H1(
                    children="[DEMO] Ethiopia Livestock Model", className="header-title"
                ),
                html.P(
                    children=[
                        "Model the behaviour of the Ethiopia livestock system "
                        "using a system dynamics model.",
                        html.Br(), html.Br(),
                        "NOTE: this model is purely a demo, and not intended for "
                        "actual use. It does not use any real-world data."
                    ],
                    className="header-description"
                ),
            ],
            className="header"
        ),
        html.Div(
            # date
            children=[
                html.Div(
                    children="Date Range",
                    className="menu-title"
                ),
                dcc.DatePickerRange(
                    id="date-range",
                    min_date_allowed=min_date,
                    max_date_allowed=max_date,
                    start_date=initial_start_date,
                    end_date=initial_stop_date
                )
            ],
            className="menu",
        ),
        html.Div(
            # menu 1
            children=[
                html.Div(children="Scenario A:"),
                html.Div(
                    children=[
                        html.Div(children="Livestock health", className="menu-title"),
                        dcc.Slider(
                            id="scenario-A-var-1",
                            min=0.5,
                            max=1.0,
                            step=0.05,
                            value=1.0,
                            marks={
                                0.5: "0",
                                1: "1"
                            },
                        ),
                    ]
                ),
                html.Div(
                    children=[
                        html.Div(children="Livestock fertility (births per year)", className="menu-title"),
                        dcc.Slider(
                            id="scenario-A-var-2",
                            min=0.0,
                            max=0.5,
                            step=0.01,
                            value=0.3,
                            marks={
                                0: "0",
                                0.5: "0.5"
                            },
                        ),
                    ]
                ),
            ],
            className="menu",
        ),
        html.Div(
            # menu 2
            children=[
                html.Div(children="Scenario B:"),
                html.Div(
                    children=[
                        html.Div(children="Livestock health", className="menu-title"),
                        dcc.Slider(
                            id="scenario-B-var-1",
                            min=0.5,
                            max=1.0,
                            step=0.05,
                            value=1.0,
                            marks={
                                0.5: "0",
                                1: "1"
                            },
                        ),
                    ]
                ),
                html.Div(
                    children=[
                        html.Div(children="Livestock fertility (births per year)", className="menu-title"),
                        dcc.Slider(
                            id="scenario-B-var-2",
                            min=0.0,
                            max=0.5,
                            step=0.01,
                            value=0.3,
                            marks={
                                0: "0",
                                0.5: "0.5"
                            },
                        ),
                    ]
                ),
            ],
            className="menu",
        ),
        html.Div(
            # charts
            children=[
                html.Div(children="Plotting variable", className="menu-title"),
                dcc.Dropdown(
                    id="chart-1-y",
                    options=[
                        {"label": variable,
                         "value": variable}
                        for variable in variables
                    ],
                    clearable=False,
                    value="Producer Stock",
                    className="dropdown",
                ),
                html.Div(
                    children=dcc.Graph(
                        id="chart-1", config={"displayModeBar": False},
                    ),
                    className="card",
                ),
                # html.Div(
                #     children=dcc.Graph(
                #         id="output-chart2", config={"displayModeBar": False},
                #     ),
                #     className="card",
                # ),
            ],
            className="wrapper",
        ),
        dcc.Store(
            id="stored-runs",
        ),
    ]
)


@app.callback(
    Output("stored-runs", "data"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
    Input("scenario-A-var-1", "value"),
    Input("scenario-A-var-2", "value"),
    Input("scenario-B-var-1", "value"),
    Input("scenario-B-var-2", "value"),
    State("stored-runs", "data")
)
def run_scenario_x(
        start_date_str,
        stop_date_str,
        scenario_A_var_1,
        scenario_A_var_2,
        scenario_B_var_1,
        scenario_B_var_2,
        stored_runs
):
    ctx = dash.callback_context
    start_date = datetime.fromisoformat(start_date_str)
    stop_date = datetime.fromisoformat(stop_date_str)
    run_scenario_a, run_scenario_b = False, False
    if not ctx.triggered:
        df = run_model(model_env, model, "startup", {}, start_date, stop_date)
        trigger_variable = "date-range"
    else:
        df = pd.read_json(stored_runs, orient="split")
        trigger_variable = ctx.triggered[0]["prop_id"].split(".")[0]
    if trigger_variable == "date-range":
        run_scenario_a, run_scenario_b = True, True
    if "scenario-A" in trigger_variable: run_scenario_a = True
    if "scenario-B" in trigger_variable: run_scenario_b = True
    if run_scenario_a:
        scenario = "A"
        constants = {
            "Animal Health": scenario_A_var_1,
            "Fertility Baseline": scenario_A_var_2 / 365.0,
        }
        run_df = run_model(model_env, model, scenario, constants, start_date, stop_date)
        df.drop(df[df["Scenario"] == scenario].index, inplace=True)
        df = df.append(run_df, ignore_index=True)
    if run_scenario_b:
        scenario = "B"
        constants = {
            "Animal Health": scenario_B_var_1,
            "Fertility Baseline": scenario_B_var_2 / 365.0,
        }
        run_df = run_model(model_env, model, scenario, constants, start_date, stop_date)
        df.drop(df[df["Scenario"] == scenario].index, inplace=True)
        df = df.append(run_df, ignore_index=True)
    # terrible terrible bodge
    df.drop(df[df["Scenario"] == "startup"].index, inplace=True)
    stored_runs = df.to_json(date_format='iso', orient='split')
    return stored_runs


@app.callback(
    Output("chart-1", "figure"),
    Input("chart-1-y", "value"),
    Input("stored-runs", "data")
)
def update_chart_1(chart_1_y, stored_runs):
    df = pd.read_json(stored_runs, orient="split")
    fig = px.line(
        df.sort_values(["Scenario", "t"]),
        x="Date",
        y=chart_1_y,
        color="Scenario"
    )
    return fig


if __name__ == '__main__':
    app.run_server(debug=True)
