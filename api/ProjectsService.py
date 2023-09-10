import uuid
from typing import List

import requests
from pydantic.tools import parse_obj_as

import AppConfig
from FlaskCache import cache
from api.DatasetService import DatasetService
from api.dto import CreateProjectDTO, ProjectsOutput, UpdateProjectTagsDTO, CreateNewDatasetDTO, CreateDatasetDTO
from auth import AppIDAuthProvider
from utils.AzureContainerHelper import BlobConnector


class ProjectService:
    URL_PREFIX = 'api/v1/projects'

    @classmethod
    def create_new_project(cls, project: CreateProjectDTO, session) -> ProjectsOutput:
        bearer_token = session['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        create_project_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}"
        create_project_response = requests.post(create_project_endpoint, json=project.dict(), headers=headers)
        create_project_response.raise_for_status()

        created_project = create_project_response.json()
        created_project = parse_obj_as(ProjectsOutput, created_project)

        return created_project

    @classmethod
    def delete_project(cls, session, project_id):
        bearer_token = session['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}
        delete_project_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{project_id}"

        delete_project_response = requests.delete(delete_project_endpoint, headers=headers)
        delete_project_response.raise_for_status()
        return True

    @classmethod
    @cache.memoize(timeout=50000, args_to_ignore=['session'])
    def get_project_by_id(cls, session, project_id) -> ProjectsOutput:
        print('get_project_by_id is getting called now === ')
        bearer_token = session['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        get_project_by_id_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{project_id}"
        project_response = requests.get(get_project_by_id_endpoint, headers=headers)
        project_response.raise_for_status()

        project = project_response.json()
        project = parse_obj_as(ProjectsOutput, project)
        return project

    @classmethod
    def update_project_tags(cls, session, project_id, project_tags: UpdateProjectTagsDTO):
        print('update_project_tags is getting called now === ')
        bearer_token = session['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        update_project_tags_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{project_id}"
        project_response = requests.put(update_project_tags_endpoint, json=project_tags.dict(), headers=headers)
        project_response.raise_for_status()

        project = project_response.json()
        project = parse_obj_as(ProjectsOutput, project)
        cache.delete_memoized(ProjectService.get_project_by_id)
        return project

    @classmethod
    @cache.memoize(timeout=500000, args_to_ignore=['session_store'])
    def fetch_projects(cls, session_store, params, offset=0, limit=10) -> List[ProjectsOutput]:
        print('fetch_projects is getting called now === ')
        bearer_token = session_store['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        params['offset'] = offset
        params['limit'] = limit

        fetch_projects_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}"
        projects_response = requests.get(fetch_projects_endpoint, headers=headers, params=params)
        projects_response.raise_for_status()

        projects = projects_response.json()
        projects = parse_obj_as(List[ProjectsOutput], projects)

        return projects

    @classmethod
    def link_dataset_to_project(cls, project_id, dataset_id,
                                session_store,
                                link_state='LINKED'):
        bearer_token = session_store['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        active_project = ProjectService.get_project_by_id(project_id=project_id, session=session_store)
        for dataset in active_project.datasets:
            if dataset.dataset.parent_dataset_id == dataset_id:
                return "NO_UPDATE"

        existing_dataset = DatasetService.get_dataset_by_id(dataset_id, session_store=session_store)
        azr_path = existing_dataset.path

        new_dataset_id = str(uuid.uuid4())
        new_dataset: CreateNewDatasetDTO = CreateNewDatasetDTO(
            dataset=CreateDatasetDTO(
                parent_dataset_id=dataset_id,
                id=new_dataset_id,
                name=existing_dataset.name,
                dataset_type_id=existing_dataset.dataset_type.id,
                project_id=project_id,
                path=f"datasets/{session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID]}/{new_dataset_id}.csv",
                tags={'state': link_state}
            ),
            project_dataset_state=link_state
        )

        try:
            created_dataset = DatasetService.create_new_dataset(dataset=new_dataset, session=session_store)
            BlobConnector.copy_blob_between_containers(source_blob_path=azr_path,
                                                       target_blob_path=created_dataset.path,
                                                       copy_from_container=AppConfig.DATASETS_CONTAINER,
                                                       copy_to_container=AppConfig.DATASETS_CONTAINER)
            cache.delete_memoized(DatasetService.get_dataset_by_id)
            cache.delete_memoized(ProjectService.get_project_by_id)
            return "UPDATED"
        except Exception as e:
            return "NO_UPDATE"


