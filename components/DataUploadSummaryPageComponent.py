from base64 import b64encode

from dash import html, dcc, Input, Output, State, no_update, ALL, MATCH
from components import DataTableNative, MapboxScatterPlot
import dash
import dash_mantine_components as dmc
from auth import AppIDAuthProvider


def get_upload_summary(data_type, data_frame, session):
    col_subset = []

    if data_type == 'OBSERVATORY_DATA':
        pass
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

    summary_df = data_frame[col_subset].describe(exclude=[object])\
        .reset_index()\
        .rename(columns={'index': 'Statistic'})

    return dmc.Stack(children=[
        DataTableNative.get_native_datable(summary_df, datatable_id='dataset-summary-df'),
        get_data_specific_plot(data_frame, session[AppIDAuthProvider.DATASET_TYPE_SELECTED])

    ], align='stretch', justify='space-around')


def get_data_specific_content(summary_df):
    pass


def get_data_specific_plot(df, selected_dataset, render_option='plot'):
    fig = MapboxScatterPlot.get_mapbox_plot(df=df,
                                            df_name=selected_dataset,
                                            col_to_plot='Magnetic_Field',
                                            sampling_frequency=100)

    if render_option == 'image':
        fig.update_coloraxes(showscale=False)
        img_bytes = fig.to_image(format="png")
        encoding = b64encode(img_bytes).decode()
        img_b64 = "data:image/png;base64," + encoding
        return dmc.Image(src=img_b64, width='100%', height=500, withPlaceholder=True)

    if render_option == 'plot':
        return dcc.Graph(id='data-upload-summary-region-plot', figure=fig, style={'width': '100%'})

