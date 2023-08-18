import csv
import os
from datetime import date

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from flask_caching import Cache

from digitaltwin import settings

external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]


class Label:
    def __init__(self):
        pass

    def label_case1(self):
        # Initialize dash application
        app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
        app.title = "TRS Digital Twin Label Tool Case1"

        # Cache
        cache = Cache(app.server, config={"CACHE_TYPE": "simple"})

        @cache.memoize()
        def cache_data():
            """
            Slice entire dataframe by (1) COMB_ID and (2) date
            and store slices in dict for faster access
            """

            df = self.get_df()
            df_dict = dict()
            for COMB_ID in df["COMB_ID"].unique():
                df_i = df.loc[df["COMB_ID"] == COMB_ID, :]
                df_dict[COMB_ID] = dict()
                for date_i in df_i["Date"].unique():
                    df_ii = df_i.loc[df_i["Date"] == date_i, :]
                    df_dict[COMB_ID][date_i] = df_ii
            return df_dict

        df_dict = cache_data()

        def get_df_dict():
            return cache_data()

        # Filters
        filter_comb_id = list(sorted(df_dict.keys()))
        filter_dates = []

        app.layout = html.Div(
            [
                # Title
                html.H4("TRS Digital Twin Label Tool Case1"),
                html.Hr(),
                # Combination ID
                html.P("COMB_ID"),
                dcc.Loading(
                    dcc.Dropdown(filter_comb_id, id="filter_comb_id"),
                    color="#119DFF",
                    type="circle",
                    fullscreen=True,
                ),
                # Dates
                html.P("Date"),
                html.Div(
                    [
                        dcc.Loading(
                            html.Div(dcc.Dropdown(filter_dates, id="filter_date")),
                            color="#119DFF",
                            type="circle",
                            fullscreen=True,
                        ),
                        html.Div(
                            html.Button(
                                "Previous Date", id="submit_prev_date", n_clicks=0
                            ),
                            style={"display": "inline-block"},
                        ),
                        html.Div(
                            html.Button("Next Date", id="submit_next_date", n_clicks=0),
                            style={"display": "inline-block"},
                        ),
                    ],
                    style={"width": "30%", "display": "inline-block"},
                ),
                html.Hr(),
                # Graph
                html.P("Timeline"),
                dcc.Loading(
                    dcc.Graph(id="timeline_chart"),
                    color="#119DFF",
                    type="circle",
                    fullscreen=True,
                ),
                html.Hr(),
                # Selected data
                html.P("Selected data"),
                html.Div(id="selected-data"),
                html.Hr(),
            ]
        )

        # Update dates once COMB_ID is chosen
        @app.callback(
            output=[Output("filter_date", "options")],
            inputs=[Input("filter_comb_id", "value")],
        )
        def update_dates(filter_comb_id):
            if filter_comb_id is None:
                raise PreventUpdate()

            df_dict_c = get_df_dict()[filter_comb_id]
            return [list(df_dict_c.keys())]

        # Previous and next date
        @callback(
            [
                Output("filter_date", "value"),
                Output("submit_prev_date", "n_clicks"),
                Output("submit_next_date", "n_clicks"),
            ],
            [
                Input("submit_prev_date", "n_clicks"),
                Input("submit_next_date", "n_clicks"),
            ],
            [
                State("filter_comb_id", "value"),
                State("filter_date", "value"),
            ],
        )
        def update_prev_date(
            submit_prev_date, submit_next_date, filter_comb_id, filter_date
        ):
            if filter_comb_id is None or filter_date is None:
                raise PreventUpdate()
            if submit_prev_date == 0 and submit_next_date == 0:
                raise PreventUpdate()

            # Get dates
            df_dict_c = get_df_dict()[filter_comb_id]
            dates = list(df_dict_c.keys())

            # Find index of currently selected date
            index = dates.index(
                date(
                    int(filter_date[0:4]), int(filter_date[5:7]), int(filter_date[8:10])
                )
            )

            new_date = None
            if submit_prev_date > 0:
                if (index - 1) >= 0:
                    new_date = dates[index - 1]
            if submit_next_date > 0:
                if (index + 1) <= (len(dates) - 1):
                    new_date = dates[index + 1]

            if new_date is None:
                raise PreventUpdate()
            else:
                return [new_date, 0, 0]

        # Update graph once COMB_ID and date are chosen
        @app.callback(
            output=[Output("timeline_chart", "figure")],
            inputs=[Input("filter_comb_id", "value"), Input("filter_date", "value")],
        )
        def update_graph(filter_comb_id, filter_date):
            if filter_comb_id is None or filter_date is None:
                raise PreventUpdate()

            df_i = get_df_dict()[filter_comb_id][
                date(
                    int(filter_date[0:4]), int(filter_date[5:7]), int(filter_date[8:10])
                )
            ]

            # Figure
            fig = go.Figure()
            color_code_iter = iter(["orange", "blue"] + 100 * ["red"])
            for pos_i in ["up_to_down", "down"] + [
                x
                for x in sorted(df_i["Position"].unique())
                if x not in ["up_to_down", "down"]
            ]:
                df_ii = df_i.loc[(df_i["Position"] == pos_i), :]

                fig.add_trace(
                    go.Scatter(
                        x=df_ii["TimeUtc"],
                        y=df_ii["Area_m2"],
                        marker=dict(size=3),
                        name=pos_i,
                        mode="lines+markers",
                        line=dict(width=0.5, color=next(color_code_iter)),
                        stackgroup=pos_i,
                    )
                )

            fig.update_layout(
                title=f"Total material flow for machine combination {df_i['COMB_ID'].values[0]}    Date: {filter_date}",
                xaxis_title="TimeUtc",
                yaxis_title="Area_m2",
                dragmode="lasso",
            )

            fig.update_layout(clickmode="event+select")

            fig.update_traces(marker_size=2)

            return [fig]

        @callback(
            Output("selected-data", "children"),
            [Input("timeline_chart", "selectedData"), State("filter_comb_id", "value")],
        )
        def display_selected_data(selectedData, filter_comb_id):
            # If there is no selection, don't update
            if selectedData is None:
                raise PreventUpdate

            label_file_name = "AnomalyLabels_Case1.csv"

            # Create header if necessary
            if not os.path.isfile(settings.path_labels.joinpath(label_file_name)):
                with open(
                    settings.path_labels.joinpath(label_file_name), "w", newline="\n"
                ) as f:
                    writer = csv.writer(f)
                    writer.writerows([["GUID", "Track", "TimeUtc"]])

            labels = []
            pos_dict = {0: "UP", 1: "DOWN"}
            for p in selectedData["points"]:
                GUID = settings.dts.COMB_ID_dict[filter_comb_id][
                    f"""{pos_dict[p["curveNumber"]]}_GUID"""
                ]
                Track = settings.dts.COMB_ID_dict[filter_comb_id][
                    f"""{pos_dict[p["curveNumber"]]}_Track"""
                ]
                TimeUtc = p["x"]
                labels.append([GUID, Track, TimeUtc])

            with open(
                settings.path_labels.joinpath(label_file_name), "a", newline="\n"
            ) as f:
                writer = csv.writer(f)
                writer.writerows(labels)

            return [html.Div(f"""{x[0]}, {x[1]}, {x[2]}""") for x in labels]

        # Run app
        app.run(debug=True, use_reloader=False)

    def get_df(self):
        # Input data
        df = pd.read_pickle(
            settings.path_work.joinpath(
                f"MS_UP_DOWN_{settings.dts.file_name_suffix}.pkl"
            )
        )
        df = df.reset_index(drop=True)

        """
        COMB_IDs
        "Wellman - Spijk____UP_BOS31_-1____DOWN_BOS32_-1____Eject",
        "Wellman - Spijk____UP_BOS51_-1____DOWN_BOS52_-1____Eject",
        "Wellman - Spijk____UP_BOS52_-1____DOWN_BOS53_-1____Eject",
        "Visy - Smithfield____UP_OS6_-1____DOWN_OS7_-1____Drop",
        "Visy - Smithfield____UP_OS8_-1____DOWN_OS9_-1____Drop",
        "Visy - Smithfield____UP_OS3_-1____DOWN_OS4_-1____Drop",
        "Visy - Smithfield____UP_OS4_-1____DOWN_OS5_-1____Drop",
        "Renewi - Ghent____UP_NIR1 (Cleaner)_-1____DOWN_NIR2 (Wood)_-1____Eject",
        "Renewi - Ghent____UP_NIR2 (Wood)_-1____DOWN_NIR3 (MIX Plastics)_-1____Drop",
        "Renewi - Ghent____UP_NIR9 (Cardboard)_-1____DOWN_NIR10 (Cardboard)_-1____Eject",
        """

        # DEV
        df = df.loc[
            df["COMB_ID"].isin(
                [
                    "Wellman - Spijk____UP_BOS31_-1____DOWN_BOS32_-1____Eject",
                    "Wellman - Spijk____UP_BOS51_-1____DOWN_BOS52_-1____Eject",
                    "Wellman - Spijk____UP_BOS52_-1____DOWN_BOS53_-1____Eject",
                ]
            ),
            :,
        ]
        # df = df.loc[df["TimeUtc"] > "2023-01-07", :]
        # df = df.loc[df["TimeUtc"] < "2023-02-01", :]

        # Aggregate all materials
        df = df.loc[df["Position"].isin(["up_to_down", "down"]), :]
        df = (
            df.groupby(["COMB_ID", "TimeUtc", "Position"])["Area_m2"]
            .sum()
            .reset_index()
        )

        df["Date"] = df["TimeUtc"].dt.date

        # Negative area values for DOWN
        df.loc[df["Position"] == "down", "Area_m2"] *= -1

        return df


if __name__ == "__main__":
    label = Label()
    label.label_case1()