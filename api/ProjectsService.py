from typing import List

import requests
from pydantic.tools import parse_obj_as

import AppConfig
from FlaskCache import cache
from api.dto import CreateProjectDTO, ProjectsOutput, UpdateProjectTagsDTO


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
    @cache.memoize(timeout=500000, args_to_ignore=['session'])
    def get_project_by_id(cls, session, project_id):
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
        return project
