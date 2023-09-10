from typing import List

import requests
from pydantic.tools import parse_obj_as

import AppConfig
from FlaskCache import cache
from api.dto import CreateNewDatasetDTO, DatasetsOutput, \
    DatasetFilterDTO, DatasetsWithDatasetTypeDTO
from utils.AzureContainerHelper import BlobConnector


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
            if datasets_filter.states:
                params['dataset_state_query'] = datasets_filter.states

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

        dataset_to_delete = DatasetService.get_dataset_by_id(session_store=session, dataset_id=dataset_id)
        BlobConnector.delete_blob(container_name=AppConfig.DATASETS_CONTAINER, blob_path=dataset_to_delete.path)

        delete_dataset_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{dataset_id}"
        delete_dataset_response = requests.delete(delete_dataset_endpoint, headers=headers)

        delete_dataset_response.raise_for_status()

        if delete_dataset_response.status_code == 204:
            return True
        else:
            return False

    @classmethod
    @cache.memoize(timeout=500000, args_to_ignore=['session_store'])
    def get_dataset_by_id(cls, dataset_id, session_store):
        bearer_token = session_store['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        print('GET DATASET By ID IS GETTING CALLED!')

        get_dataset_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{dataset_id}"

        dataset_response = requests.get(get_dataset_endpoint, headers=headers)
        dataset_response.raise_for_status()
        dataset = dataset_response.json()

        dataset = parse_obj_as(DatasetsWithDatasetTypeDTO, dataset)
        return dataset

    @classmethod
    def update_dataset(cls, dataset_id, session_store, dataset_update_dto) -> DatasetsWithDatasetTypeDTO:

        bearer_token = session_store['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        print('Update Dataset IS GETTING CALLED!')

        dataset_update_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{dataset_id}"

        dataset_response = requests.put(dataset_update_endpoint, json=dataset_update_dto.dict(),headers=headers)
        dataset_response.raise_for_status()
        updated_dataset = dataset_response.json()

        updated_dataset = parse_obj_as(DatasetsWithDatasetTypeDTO, updated_dataset)

        cache.delete_memoized(DatasetService.get_dataset_by_id)

        return updated_dataset
