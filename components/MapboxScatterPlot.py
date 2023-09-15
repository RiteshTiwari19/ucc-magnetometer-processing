import math

import datashader as ds
import datashader.transfer_functions as tf
import numpy as np
import pandas as pd
import plotly.express as px
from colorcet import fire
from flask import session
import plotly.graph_objects as go

import AppConfig
from FlaskCache import cache
from api import ResidualService


@cache.memoize(timeout=5000000)
def get_mapbox_plot(df,
                    df_name,
                    col_to_plot,
                    sampling_frequency=50,
                    color_scale='icefire',
                    latitude_col='Latitude',
                    longitude_col='Longitude',
                    color_column='Magnetic_Field',
                    hover_name='Magnetic_Field',
                    hover_data='Magnetic_Field',
                    points_to_clip=None):
    sampling_frequency = math.ceil(len(df) / 18000)

    print(f'Sampling at frequency: {sampling_frequency}')

    plot_df = df[::sampling_frequency].reset_index() if len(df) > 18000 else df

    plot_df = plot_df.reset_index()

    fig = px.scatter_mapbox(plot_df,
                            lat=latitude_col,
                            lon=longitude_col,
                            hover_name=hover_name,
                            hover_data=col_to_plot,
                            color=col_to_plot,
                            custom_data='index',
                            color_continuous_scale=color_scale,
                            zoom=8
                            )

    print('GET MAPBOX PLOT GOT CALLED')

    fig.update_layout(mapbox_style='open-street-map')
    fig.update_layout(margin={'r': 0, 't': 0, 'l': 0, 'b': 0})
    fig.update_layout(template='plotly_dark')
    return fig


@cache.memoize(timeout=5000000)
def get_mapbox_plot_annotated(
        df,
        col_to_plot,
        color_scale='icefire',
        latitude_col='Latitude',
        longitude_col='Longitude',
        hover_name='Residuals',
        hover_data='Type',
        selected_dataset=None,
        session_store=None):
    max_residual, min_residual = None, None

    if f'{AppConfig.ANNOTATION}__{selected_dataset}__MAX_RESIDUAL' in session:
        max_residual = session[f'{AppConfig.ANNOTATION}__{selected_dataset}__MAX_RESIDUAL']

    if f'{AppConfig.ANNOTATION}__{selected_dataset}__MIN_RESIDUAL' in session:
        min_residual = session[f'{AppConfig.ANNOTATION}__{selected_dataset}__MIN_RESIDUAL']

    if max_residual and min_residual+1:
        df = df[(abs(df['Residuals']) >= min_residual) & (abs(df['Residuals']) <= max_residual)]

    annotation_df = pd.DataFrame()

    if AppConfig.ANNOTATION in session_store and selected_dataset in session_store[AppConfig.ANNOTATION]:
        latitudes = session_store[AppConfig.ANNOTATION][selected_dataset]['Latitude']
        longitudes = session_store[AppConfig.ANNOTATION][selected_dataset]['Longitude']
        classes = session_store[AppConfig.ANNOTATION][selected_dataset]['Class']
        types = session_store[AppConfig.ANNOTATION][selected_dataset]['Type']

        annotation_df = pd.DataFrame({
            'Latitude': latitudes,
            'Longitude': longitudes,
            'Class': classes,
            'Type': types
        })

        annotation_df.drop_duplicates(subset=['Latitude', 'Longitude'], inplace=True)

    sampling_frequency = math.ceil(len(df) / 18000)

    print(f'Sampling at frequency: {sampling_frequency}')

    plot_df = df[::sampling_frequency].reset_index() if len(df) > 18000 else df

    plot_df = plot_df.reset_index()

    fig = px.scatter_mapbox(plot_df,
                            lat=latitude_col,
                            lon=longitude_col,
                            hover_name=hover_name,
                            hover_data=col_to_plot,
                            color=col_to_plot,
                            color_continuous_scale=color_scale,
                            zoom=8
                            )

    print('GET MAPBOX PLOT GOT CALLED')

    fig.update_layout(mapbox_style='open-street-map')
    fig.update_layout(margin={'r': 0, 't': 0, 'l': 0, 'b': 0})
    fig.update_layout(template='plotly_dark')

    if len(annotation_df) > 0:
        fig.add_trace(
            go.Scattermapbox(
                lat=np.array(annotation_df[latitude_col]),
                lon=np.array(annotation_df[longitude_col]),
                marker={
                    "color": "cyan",
                    "size": 6,
                },
                mode="markers",
                hovertext=np.array(annotation_df[hover_data])
            ))

    return fig


def get_mapbox_plot_raster(selected_dataset):
    df = ResidualService.ResidualService.calculate_residuals(selected_dataset).head(100000)

    cvs = ds.Canvas(plot_width=1000, plot_height=1000)
    agg = cvs.points(df, x='Longitude', y='Latitude')
    # agg is an xarray object, see http://xarray.pydata.org/en/stable/ for more details
    coords_lat, coords_lon = agg.coords['Latitude'].values, agg.coords['Longitude'].values
    # Corners of the image, which need to be passed to mapbox
    coordinates = [[coords_lon[0], coords_lat[0]],
                   [coords_lon[-1], coords_lat[0]],
                   [coords_lon[-1], coords_lat[-1]],
                   [coords_lon[0], coords_lat[-1]]]

    img = tf.shade(agg, cmap=fire)[::-1].to_pil()

    fig = px.scatter_mapbox(df[:1],
                            lat='Latitude',
                            lon='Longitude',
                            # hover_name='Magnetic_Field',
                            # hover_data=['Magnetic_Field'],
                            # color='Magnetic_Field',
                            zoom=12
                            )

    fig.update_layout(mapbox_style="open-street-map",
                      mapbox_layers=[
                          {
                              "sourcetype": "image",
                              "source": img,
                              "coordinates": coordinates
                          }]
                      )
    fig.update_layout(template='plotly_dark')

    return fig
