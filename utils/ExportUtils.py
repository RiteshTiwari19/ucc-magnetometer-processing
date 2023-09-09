import os.path
import uuid
import shutil

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import AppConfig
from api.DatasetService import DatasetService
from utils.AzureContainerHelper import BlobConnector
from auth import AppIDAuthProvider


class ExportUtils:

    @classmethod
    def export_csv(cls, dataset_id, dataset_path, session):
        file_path = cls.download_data_if_not_exists(dataset_path=dataset_path, dataset_id=dataset_id, session=session)
        file_path = file_path.split('/')[-1].split('.')[0]
        return file_path

    @classmethod
    def download_data_if_not_exists(cls, dataset_path, dataset_id, session):
        dataset_name = dataset_path.split('/')[-1]
        dataset_format = dataset_name.split('.')[-1]
        # file_path = f"{AppConfig.PROJECT_ROOT}\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\processed\\{dataset_name}"
        file_dir = os.path.join(AppConfig.PROJECT_ROOT, 'data', session[AppIDAuthProvider.APPID_USER_NAME],
                                 'downloads')

        file_path = os.path.join(file_dir, f'{dataset_id}.{dataset_format}')

        if not os.path.exists(file_dir):
            os.mkdir(file_dir)

        if not os.path.exists(file_path):
            file_path = os.path.join(file_dir, f'{dataset_id}.{dataset_format}')
            linked = True if AppConfig.PROJECTS_CONTAINER in dataset_path else False
            BlobConnector.download_blob(blob_name=dataset_path, download_location=file_path, linked=linked)
        return file_path

    @classmethod
    def export_shp_file(cls, dataset_id, dataset_path, session):

        columns_to_extract = None

        dataset_name = dataset_path.split('/')[-1].split('.')[0]
        file_path = cls.download_data_if_not_exists(dataset_path=dataset_path, dataset_id=dataset_id, session=session)

        export_path = f"{AppConfig.PROJECT_ROOT}\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\processed\\exported"
        export_file_name = f"{export_path}\\{dataset_name}.shp"
        zip_path = f'{dataset_name}.zip'

        if os.path.exists(f"{export_path}\\{dataset_name}.zip"):
            return '\\exported', zip_path

        df = pd.read_csv(file_path, usecols=columns_to_extract)

        df['Latitude'] = df['Latitude'].astype('float')
        df['Longitude'] = df['Longitude'].astype('float')

        geometry = [Point(xy) for xy in zip(df['Longitude'], df['Latitude'])]
        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry=geometry)

        if not os.path.exists(export_path):
            os.mkdir(export_path)

        gdf.to_file(export_file_name)
        file_name = shutil.make_archive(dataset_name, 'zip', export_path, export_path)

        shutil.move(file_name, os.path.join(export_path, f'{dataset_name}.zip'))

        return '\\exported', zip_path
