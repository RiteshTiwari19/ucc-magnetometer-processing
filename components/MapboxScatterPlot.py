import datashader as ds
import datashader.transfer_functions as tf
import plotly.express as px
from colorcet import fire

from FlaskCache import cache
from api import ResidualService


@cache.memoize(timeout=5000000, args_to_ignore=['df'])
def get_mapbox_plot(df,
                    df_name,
                    col_to_plot,
                    sampling_frequency=50,
                    color_scale='icefire',
                    latitude_col='Latitude',
                    longitude_col='Longitude',
                    color_column='Magnetic_Field',
                    hover_name='Magnetic_Field',
                    hover_data='Magnetic_Field'):

    fig = px.scatter_mapbox(df[::sampling_frequency],
                            lat=latitude_col,
                            lon=longitude_col,
                            hover_name=hover_name,
                            hover_data=hover_data,
                            color=col_to_plot,
                            color_continuous_scale=color_scale,
                            zoom=8
                            )

    print('GET MAPBOX PLOT GOT CALLED')

    fig.update_layout(mapbox_style='open-street-map')
    fig.update_layout(margin={'r': 0, 't': 0, 'l': 0, 'b': 0})
    fig.update_layout(template='plotly_dark')
    return fig

def get_mapbox_plot_uncached(df,
                    df_name,
                    col_to_plot,
                    sampling_frequency=50,
                    color_scale='icefire',
                    latitude_col='Latitude',
                    longitude_col='Longitude',
                    color_column='Magnetic_Field',
                    hover_name='Magnetic_Field',
                    hover_data='Magnetic_Field'):

    fig = px.scatter_mapbox(df[::sampling_frequency],
                            lat=latitude_col,
                            lon=longitude_col,
                            hover_name=hover_name,
                            hover_data=hover_data,
                            color_continuous_scale=color_scale,
                            zoom=8
                            )

    print('GET MAPBOX PLOT GOT CALLED')

    fig.update_layout(mapbox_style='open-street-map')
    fig.update_layout(margin={'r': 0, 't': 0, 'l': 0, 'b': 0})
    fig.update_layout(template='plotly_dark')
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
