import math
import os
import time

import pandas as pd
import rasterio
import verde as vd
import numpy as np
from joblib import Parallel, delayed
import rasterio as rio
from matplotlib import pyplot as plt
from rasterio.transform import from_origin
from rasterio.plot import show

import AppConfig
from FlaskCache import cache
from dataservices.RedisQueue import RedisQueue
from utils.Consts import Consts


@cache.memoize(timeout=5000)
def verde_interpolate(df, col_to_interpolate, interpolation_type, spacing, tiff_name):
    redis_queue = RedisQueue(name='app-notifications')
    start_time = time.time()

    coordinates = (np.array(df['Easting']), np.array(df['Northing']))
    region = vd.get_region((df.Easting, df.Northing))

    redis_queue.put(f'interpolation;show__{Consts.LOADING_DISPLAY_STATE};Fitting;Fitting Interpolator to Data!')

    fitted_interpolator = fit_interpolator(interpolation_type=interpolation_type,
                                           spacing=spacing,
                                           coordinates=coordinates,
                                           interpolation_values=df[col_to_interpolate])

    redis_queue.put(
        f'interpolation;update__{Consts.LOADING_DISPLAY_STATE};Generating Grid;Generating Interpolation Grid with spacing {spacing}!')

    time.sleep(2)

    grid = extract_grid(col_to_interpolate, fitted_interpolator, region, spacing)

    redis_queue.put(
        f'interpolation;update__{Consts.LOADING_DISPLAY_STATE};Masking;Generating Convex Hull to mask points!')

    grid = vd.convexhull_mask(coordinates, grid=grid)

    df_convex_hulled = grid.to_dataframe()
    df_convex_hulled = df_convex_hulled.dropna(subset=[col_to_interpolate])

    df_splits = split_dataframe(df_convex_hulled)

    redis_queue.put(
        f'interpolation;update__{Consts.LOADING_DISPLAY_STATE}; Masking; Masking extrapolated points with a distance filter')

    grid_list = Parallel(n_jobs=6, backend="threading")(
        delayed(process_sub_grid)(df_i, coordinates, 400) for df_i in df_splits)

    total_grid_df = pd.concat([grid.to_dataframe().dropna() for grid in grid_list])
    uq, lq = df[col_to_interpolate].max(), df[col_to_interpolate].min()
    total_grid_df_filtered = total_grid_df[(total_grid_df[col_to_interpolate] >= lq) & \
                                           (total_grid_df[col_to_interpolate] <= uq)]

    total_grid = total_grid_df_filtered.to_xarray()

    end_time = time.time()

    diff = end_time - start_time

    redis_queue.put(
        f'interpolation;update__{Consts.LOADING_DISPLAY_STATE}; Grid Generated; Interpolated {len(total_grid_df_filtered)} points in  {diff} seconds')

    save_path = export_to_tiff(region=region, spacing=spacing,
                               grid=total_grid[col_to_interpolate], tiff_name=tiff_name)

    plt.style.use('dark_background')
    fig = plt.figure()
    ax = fig.gca()

    fig_raster = show(rasterio.open(save_path), with_bounds=True, contour=False, title=f'{col_to_interpolate} Raster',
                      ax=ax, cmap='RdBu_r')
    im = fig_raster.get_images()[0]
    fig_raster.set_ylabel('Northing')
    fig_raster.set_xlabel('Easting')
    fig.colorbar(im, ax=ax)

    df_save_path = os.path.join(
        AppConfig.PROJECT_ROOT,
        "data",
        tiff_name.split('----')[1],
        "downloads",
        f"{tiff_name.split('----')[0]}-{tiff_name.split('----')[2]}.csv"
    )

    redis_queue.put(
        f'interpolation;update__{Consts.FINISHED_DISPLAY_STATE}; Done;Grid Generated')

    total_grid_df_filtered.reset_index().to_csv(df_save_path)
    return fig


@cache.memoize(timeout=5000)
def extract_grid(col_to_interpolate, fitted_interpolator, region, spacing):
    grid = fitted_interpolator.grid(spacing=spacing,
                                    region=region,
                                    dims=["Northing", "Easting"],
                                    data_names=col_to_interpolate)
    return grid


@cache.memoize(timeout=5000)
def split_dataframe(df):
    MAX_INDICES_SINGLE_LOOP = 500000
    split_dfs = []
    for i in range(math.ceil(df.shape[0] / MAX_INDICES_SINGLE_LOOP)):
        start = i * MAX_INDICES_SINGLE_LOOP
        end = min(start + MAX_INDICES_SINGLE_LOOP, df.shape[0])
        split_dfs.append(df.iloc[start:end])
    return split_dfs


@cache.memoize(timeout=5000)
def process_sub_grid(grid_df, coordinates, max_distance=400):
    grid = grid_df.to_xarray()
    grid = vd.distance_mask(coordinates, maxdist=max_distance, grid=grid)
    return grid


@cache.memoize(timeout=5000)
def fit_interpolator(interpolation_type, spacing, coordinates, interpolation_values):
    interpolator = get_interpolator(interpolation_type, spacing)
    interpolator.fit(coordinates, interpolation_values)
    return interpolator


@cache.memoize(timeout=5000)
def get_interpolator(interpolation_type, spacing):
    if interpolation_type == 'Linear':
        interpolator = vd.Chain([
            ("trend", vd.Trend(degree=2)),
            ("reduce", vd.BlockReduce(np.mean, spacing=spacing)),
            ("interpolation", vd.Linear())
        ])
    else:
        interpolator = vd.Chain([
            ("trend", vd.Trend(degree=2)),
            ("reduce", vd.BlockReduce(np.mean, spacing=spacing)),
            ("interpolation", vd.Cubic())
        ])
    return interpolator


def export_to_tiff(region, spacing, grid, tiff_name):
    tiff_name = tiff_name.split('----')
    save_path = os.path.join(
        AppConfig.PROJECT_ROOT,
        'data',
        tiff_name[1],
        'downloads',
        f'{tiff_name[0]}-{tiff_name[2]}'
    )

    meta = {
        "count": 1,
        "dtype": "float32",
        "height": grid.shape[0],
        "width": grid.shape[1],
        "transform": from_origin(
            region[0], region[3], spacing, spacing
        ),
    }

    # Save the interpolated points to a GeoTIFF file
    with rio.open(f'{save_path}.tiff', "w", **meta) as dst:
        dst.write(np.flip(grid, 0), 1)

    return f'{save_path}.tiff'
