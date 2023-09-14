import os.path
import threading
import time
import uuid
import shutil

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import AppConfig
from api.DatasetService import DatasetService
from components import NotificationProvider
from dataservices.InMemoryQueue import InMemoryQueue
from utils.AzureContainerHelper import BlobConnector
from auth import AppIDAuthProvider
from utils.Consts import Consts


class ExportUtils:

    @classmethod
    def export_csv(cls, dataset_id, session, cols_to_export):
        file_path = cls.download_data_if_not_exists(dataset_id=dataset_id, session=session)
        df = pd.read_csv(file_path)
        df = df[cols_to_export]

        exported_path = os.path.join(
            AppConfig.PROJECT_ROOT,
            "data",
            session[AppIDAuthProvider.APPID_USER_NAME],
            "exported",
            f"{dataset_id}_exported.csv"
        )
        df.to_csv(exported_path)

        return f"{dataset_id}_exported.csv"

    @classmethod
    def download_data_if_not_exists(cls, dataset_id, session, dataset_path=None):
        # dataset_name = dataset_path.split('/')[-1]
        # dataset_format = dataset_name.split('.')[-1]

        dataset = DatasetService.get_dataset_by_id(dataset_id, session_store=session)
        dataset_format = dataset.path.split('/')[-1].split('.')[-1]

        file_dir = os.path.join(AppConfig.PROJECT_ROOT, 'data', session[AppIDAuthProvider.APPID_USER_NAME],
                                'downloads')

        file_path = os.path.join(file_dir, f'{dataset_id}.{dataset_format}')

        if not os.path.exists(file_dir):
            os.mkdir(file_dir)

        if not os.path.exists(file_path):
            file_path = os.path.join(file_dir, f'{dataset_id}.{dataset_format}')
            BlobConnector.download_blob(blob_name=dataset.path, download_location=file_path, linked=False)
        return file_path

    @classmethod
    def export_shp_file(cls, dataset_id, cols_to_export, session, redis_queue=None):

        file_path = cls.download_data_if_not_exists(dataset_id=dataset_id, session=session)

        export_path = os.path.join(AppConfig.PROJECT_ROOT,
                                   "data",
                                   session[AppIDAuthProvider.APPID_USER_NAME],
                                   "exported",
                                   dataset_id
                                   )
        export_file_path = os.path.join(export_path, f"{dataset_id}.shp")
        zip_path = os.path.join(dataset_id, f"{dataset_id}.zip")

        # if os.path.exists(os.path.join(export_path, f"{dataset_id}.zip")):
        #     return zip_path

        if 'Latitude' not in cols_to_export:
            cols_to_export.append('Latitude')

        if 'Longitude' not in cols_to_export:
            cols_to_export.append('Longitude')

        redis_queue.put(f'data-export;update__{Consts.LOADING_DISPLAY_STATE};Generating Geometry;Converting csv to GeoPandas Dataframe!')

        time.sleep(2)

        df = pd.read_csv(file_path, usecols=cols_to_export)

        df['Latitude'] = df['Latitude'].astype('float')
        df['Longitude'] = df['Longitude'].astype('float')

        geometry = [Point(xy) for xy in zip(df['Longitude'], df['Latitude'])]
        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry=geometry)


        redis_queue.put(f'data-export;update__{Consts.LOADING_DISPLAY_STATE};Writing; Writing shape file to disk')

        time.sleep(2)

        if not os.path.exists(export_path):
            os.mkdir(export_path)

        gdf.to_file(export_file_path)

        redis_queue.put(f'data-export;update__{Consts.LOADING_DISPLAY_STATE};Archiving; Creating archive from shape file')
        time.sleep(2)

        file_name = shutil.make_archive(dataset_id, 'zip', export_path, export_path)
        shutil.move(file_name, os.path.join(export_path, f'{dataset_id}.zip'))

        return zip_path
