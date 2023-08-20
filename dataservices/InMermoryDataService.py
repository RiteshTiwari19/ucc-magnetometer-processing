import datetime
import os
import uuid

import pandas as pd
from FlaskCache import cache


class WorkspaceService:
    workspaces = [{
        'name': f'Project {i}',
        'date_modified': datetime.datetime.utcnow().strftime("%m/%d/%Y, %H:%M:%S"),
        'date_created': datetime.datetime.utcnow().strftime("%m/%d/%Y, %H:%M:%S")
    } for i in range(2)]

    @classmethod
    def add_project(cls, proj):
        if 'date_modified' not in proj:
            proj['date_modified'] = datetime.datetime.utcnow().strftime("%m/%d/%Y, %H:%M:%S")
        if 'date_created' not in proj:
            proj['date_created'] = datetime.datetime.utcnow().strftime("%m/%d/%Y, %H:%M:%S")
        cls.workspaces.insert(0, proj)

    @classmethod
    def delete_project(cls, proj_name):
        el_idx = [idx for idx, el in enumerate(cls.workspaces) if el['name'] == proj_name][0]
        del cls.workspaces[el_idx]

    @classmethod
    def get_project_by_name(cls, proj_name):
        el = [el for el in cls.workspaces if el['name'] == proj_name][0]
        return el

    @classmethod
    def set_tag_on_project(cls, proj_name, key, value):
        el = [el for el in cls.workspaces if el['name'] == proj_name][0]
        el[key] = value
        return el


class UserService:
    users = [
        {
            'id': 'riteshtiwari@hotmail.co.uk',
            'name': 'Ritesh Tiwari',
            'role': 'ADMIN'
        }
    ]


class DatasetType:
    def __init__(self, name, description, dataset_id=None):
        if dataset_id:
            self.id = dataset_id
        else:
            self.id = uuid.uuid4()
        self.name = name
        self.description = description


class Dataset:
    def __init__(self, name, projects: list, dataset_type: DatasetType, path=None):
        self.name = name.upper()
        self.path = path
        self.projects = projects
        self.typ = dataset_type
        self.date_created = datetime.datetime.utcnow().strftime("%m/%d/%Y, %H:%M:%S")
        self.date_modified = datetime.datetime.utcnow().strftime("%m/%d/%Y, %H:%M:%S")


class DatasetsService:

    dataset_types = [
        DatasetType('SURVEY_DATA', 'Datasets for marine survey, should contain columns for Index ' +
                    '(recording sequence), Latitude, Longitude, Magnetic Field, Datetime. ' +
                    '<br> If Easting and Northing are provided, then Zone must also be provided',
                    dataset_id='51767926-f1e6-4afa-a2de-501f23fa5ac5'),
        DatasetType('OBSERVATORY_DATA', 'Datasets for diurnal correction, must contain Magnetic Field readings<br> ' +
                    'Either Magnetic Field for each axis can be provided or the total Magnetic Field must be provided ' +
                    '<br>Required Columns: Magnetic Fields, Datetime',
                    dataset_id='dd1c8c46-223c-4dd1-9a98-4f046b5608bb'),
        DatasetType('BATHYMETRY_DATA', 'Datasets containing depth information of a survey area, can be used to ' +
                    'perform depth correction on the survey data. ' +
                    '<br>Required Columns: Depth, [Latitude, Longitude] or [Easting, Northing '
                    'with zone information] or both',
                    dataset_id='1bec50c8-0f71-4585-b078-08d7f410fd92')
    ]

    datasets = [Dataset(name='Sealink 16_02', projects=[],
                        path=f'{os.getcwd()}\\data\\Ritesh Tiwari\\sealink_16_02_processed.csv',
                        dataset_type=dataset_types[0]),
                Dataset(name='BOB 16_01', projects=[],
                        path=f'{os.getcwd()}\\data\\Ritesh Tiwari\\bob_16_01_processed.csv',
                        dataset_type=dataset_types[0])]

    @classmethod
    def get_existing_datasets(cls):
        return cls.datasets

    @classmethod
    def save_as_dataset(cls, dataset_type, name, projects, df):
        path = f'{os.getcwd()}\\datasets\\{name}.csv'
        dataset = Dataset(name=name, path=path,
                          dataset_type=dataset_type,
                          projects=projects)
        _ = df.to_csv(path)
        dataset.path = path
        cls.datasets.append(dataset)
        return dataset

    @classmethod
    @cache.memoize(timeout=50000)
    def get_dataset_by_name(cls, dataset_name):
        dataset = [d for d in cls.datasets if d.name == dataset_name][0]
        df = pd.read_csv(dataset.path)
        if 'Easting' in df.columns and 'Northing' in df.columns and 'Latitude' in df.columns \
                and 'Longitude' in df.columns and 'Magnetic_Field' in df.columns:
            df = df[(df['Easting'] != '*') | (df['Northing'] != '*')].dropna()

            df['Easting'] = df['Easting'].astype(float)
            df['Northing'] = df['Northing'].astype(float)
            df['Magnetic_Field'] = df['Magnetic_Field'].astype(float)
            df['Latitude'] = df['Latitude'].astype(float)
            df['Longitude'] = df['Longitude'].astype(float)

            df['Magnetic_Field'] = df['Magnetic_Field'].astype(float)

        print('Get Dataset by name got called')
        return df

    @classmethod
    def get_dataset_type_by_id(cls, dataset_id):
        print([d.id.__str__() for d in cls.dataset_types])
        dataset_type = [d for d in cls.dataset_types if d.id.__str__() == dataset_id][0]
        return dataset_type.name

    @classmethod
    def get_dataset_type_by_name(cls, dataset_type_name):
        dataset_type = [d for d in cls.dataset_types if d.name == dataset_type_name][0]
        return dataset_type

    @classmethod
    def get_dataset_types(cls):
        return cls.dataset_types
