from base64 import b64encode

import dash_mantine_components as dmc
from dash import dcc
from dash import callback, Input, Output, State, no_update, Patch, callback_context

from api.DatasetTypeService import DatasetTypeService
from auth import AppIDAuthProvider
from components import DataTableNative, MapboxScatterPlot
from dataservices import InMermoryDataService
import datetime
import pandas as pd
import os
from dash_iconify import DashIconify
import plotly.express as px
from utils import Consts


def get_upload_summary(data_type, data_frame, session):
    col_subset = []

    if data_type == 'OBSERVATORY_DATA':
        if 'bx' in data_frame.columns and 'by' in data_frame.columns and 'bz' in data_frame.columns:
            col_subset += ['bx', 'by', 'bz']
        if 'Magnetic_Field' in data_frame.columns:
            col_subset += ['Magnetic_Field']
        if 'Datetime' in data_frame.columns:
            col_subset += ['Datetime']
    elif data_type == 'SURVEY_DATA':
        col_subset += ['Magnetic_Field', 'Datetime']
        if 'Latitude' and 'Longitude' in data_frame.columns:
            col_subset += ['Latitude', 'Longitude']
        if 'Easting' and 'Northing' in data_frame.columns:
            col_subset += ['Easting', 'Northing']
        if 'Depth' in data_frame.columns:
            col_subset += ['Depth']
        if 'Altitude' in data_frame.columns:
            col_subset += ['Altitude']

    summary_df = data_frame[col_subset].describe(exclude=[object]) \
        .reset_index() \
        .rename(columns={'index': 'Statistic'})

    return dmc.Stack(children=[
        DataTableNative.get_native_datable(summary_df, datatable_id='dataset-summary-df'),
        get_data_specific_plot(data_frame, session[AppIDAuthProvider.DATASET_TYPE_SELECTED], session)

    ], align='stretch', justify='space-around')


def get_data_specific_content(summary_df):
    pass


def get_data_specific_plot(df, selected_dataset, session_store, render_option='plot'):
    dataset_type = DatasetTypeService.get_dataset_type_by_id(dataset_type_id=selected_dataset, session=session_store)

    if dataset_type.name == 'SURVEY_DATA':

        fig = MapboxScatterPlot.get_mapbox_plot(df=df,
                                                df_name=selected_dataset,
                                                col_to_plot='Magnetic_Field',
                                                sampling_frequency=100)

        fig.update_coloraxes(showscale=False)
        if render_option == 'image':
            img_bytes = fig.to_image(format="png")
            encoding = b64encode(img_bytes).decode()
            img_b64 = "data:image/png;base64," + encoding
            return dmc.Image(src=img_b64, width='100%', height=500, withPlaceholder=True)

        if render_option == 'plot':
            return dmc.Stack(children=[
                dmc.Center(
                    dmc.Text("Data Region Plot",
                             variant="gradient",
                             gradient={"from": "red", "to": "yellow", "deg": 45},
                             style={"fontSize": 20})),
                dcc.Graph(id='data-upload-summary-region-plot', figure=fig, style={'width': '100%'})
            ])
    elif dataset_type.name == 'OBSERVATORY_DATA':

        ret_val = dmc.Stack(
            children=[
                dmc.Center(
                    dmc.Text("Observatory Plot",
                             variant="gradient",
                             gradient={"from": "red", "to": "yellow", "deg": 45},
                             style={"fontSize": 20})),

                dmc.Center(
                    dmc.Group(children=[
                        dmc.DatePicker(
                            id={'type': 'datepicker', 'idx': "observatory-data-upload-date-picker"},
                            label="Observation Date",
                            # disabledDates=df['Date'].unique(),
                            description="Provide the observation date that you want to plot",
                            minDate=pd.to_datetime(df['Datetime'].min(), format='%Y-%m-%d %H:%M:%S').date(),
                            maxDate=pd.to_datetime(df['Datetime'].max(), format='%Y-%m-%d %H:%M:%S').date(),
                            placeholder='Select a Date',
                            clearable=True,
                            value=pd.to_datetime(df['Datetime'].min()).date(),
                            dropdownType="modal",
                            style={"maxWidth": '50%'},
                        ),
                        dmc.Select(
                            id={'type': 'select', 'idx': 'observatory-data-upload-dropdown'},
                            label='Plot Type',
                            description='Choose either to plot the Residuals or the Raw Total Field',
                            data=['Daily Residual', 'Raw Magnetic Field'],
                            value='Raw Magnetic Field',
                            required=False,
                            searchable=False,
                            clearable=False
                        )
                    ])),

                dmc.LoadingOverlay(
                    dcc.Graph(id={'type': 'plotly-plot', 'idx': 'data-upload-summary-obs-plot'},
                              style={'width': '100%'}),
                    loaderProps={"variant": "dots", "color": "orange", "size": "xl"}
                )
            ], align='stretch')

        return ret_val


@callback(
    Output({'type': 'plotly-plot', 'idx': 'data-upload-summary-obs-plot'}, 'figure'),
    Input({'type': 'datepicker', 'idx': "observatory-data-upload-date-picker"}, 'value'),
    Input({'type': 'select', 'idx': 'observatory-data-upload-dropdown'}, 'value'),
    State('local', 'data')
)
def get_observatory_plot(date_val, input_select, session_store):
    print(date_val)
    saved_path = os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\processed"
    dataset_name = session_store[AppIDAuthProvider.DATASET_NAME]
    df = InMermoryDataService.DatasetsService.get_dataset_by_path(f'{saved_path}\\{dataset_name}.csv')
    plot_df = df[::50]

    min_date = date_val
    max_date = (pd.to_datetime(date_val, format='%Y-%m-%d') + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    plot_df = plot_df[(plot_df['Datetime'] >= min_date) & (plot_df['Datetime'] < max_date)]

    y_plot = 'Magnetic_Field' if input_select == 'Raw Magnetic Field' else 'Baseline'

    obs_plot = px.line(plot_df, x='Datetime', y=y_plot, hover_data={"Datetime": "|%B %d, %Y %I:%M"})
    obs_plot.update_layout(hovermode='x unified')
    obs_plot.update_layout(template='plotly_dark')

    return obs_plot
