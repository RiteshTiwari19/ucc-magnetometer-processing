from typing import List

import requests
from pydantic.tools import parse_obj_as

import AppConfig
from FlaskCache import cache
from api.dto import CreateNewDatasetDTO, DatasetsOutput, \
    DatasetFilterDTO, DatasetsWithDatasetTypeDTO


class DatasetService:
    URL_PREFIX = 'api/v1/datasets'

    @classmethod
    def create_new_dataset(cls, dataset: CreateNewDatasetDTO, session) -> DatasetsOutput:
        bearer_token = session['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        create_dataset_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}"
        create_dataset_response = requests.post(create_dataset_endpoint, json=dataset.dict(), headers=headers)
        create_dataset_response.raise_for_status()

        created_dataset = create_dataset_response.json()
        created_dataset = parse_obj_as(DatasetsOutput, created_dataset)

        return created_dataset

    @classmethod
    @cache.memoize(timeout=500000, args_to_ignore=['session'])
    def get_datasets(cls, session, datasets_filter: DatasetFilterDTO | None = None) -> List[DatasetsWithDatasetTypeDTO]:
        bearer_token = session['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        params = {}

        print('GET DATASETS IS GETTING CALLED!')

        if datasets_filter:
            if datasets_filter.dataset_name:
                params['dataset_name'] = datasets_filter.dataset_name
            if datasets_filter.dataset_type_id:
                params['dataset_type_id'] = datasets_filter.dataset_type_id
            if datasets_filter.project_id:
                params['project_id'] = datasets_filter.project_id

        get_datasets_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}"

        datasets_response = requests.get(get_datasets_endpoint, headers=headers, params=params)
        datasets_response.raise_for_status()
        datasets = datasets_response.json()

        datasets = parse_obj_as(List[DatasetsWithDatasetTypeDTO], datasets)
        return datasets

    @classmethod
    def delete_dataset(cls, dataset_id, session):
        bearer_token = session['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        delete_dataset_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{dataset_id}"
        delete_dataset_response = requests.delete(delete_dataset_endpoint, headers=headers)

        delete_dataset_response.raise_for_status()

        if delete_dataset_response.status_code == 204:
            return True
        else:
            return False


