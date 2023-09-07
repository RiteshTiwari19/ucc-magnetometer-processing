from typing import List

import requests
from pydantic.tools import parse_obj_as

import AppConfig
from api.dto import UserResponseDTO, ProjectsOutput
from FlaskCache import cache


def should_update_cache(*args, **kwargs):
    return False if kwargs['purpose'] == 'general' else True


class UserService:
    URL_PREFIX = 'api/v1/users'

    @classmethod
    def get_user_by_id(cls, session) -> UserResponseDTO:
        bearer_token = session['APPID_USER_TOKEN']

        params = {'offset': 0, 'limit': 1, 'user_email': session["APPID_USER_EMAIL"]}
        headers = {'Authorization': f"Bearer {bearer_token}"}

        filter_user_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}"
        filter_user_response = requests.get(filter_user_endpoint, headers=headers, params=params)
        filter_user_response.raise_for_status()

        users = filter_user_response.json()
        user = parse_obj_as(List[UserResponseDTO], users)[0]

        return user

    @classmethod
    def get_project_count(cls, user_id, session) -> int:
        user_projects = cls.get_projects(session, user_id=user_id)
        return len(user_projects)

    @classmethod
    def get_user_projects(cls, user_id, session, purpose='general') -> List[dict]:
        user_projects = cls.get_projects(session, user_id=user_id)
        ret_dct = [{'name': up.name,
                    'date_created': up.created_at,
                    'date_modified': up.modified_at,
                    'id': up.id
                    } for up in
                   user_projects]
        return ret_dct

    @classmethod
    @cache.memoize(timeout=500000, args_to_ignore=['session', 'purpose'])
    def get_projects(cls, session, user_id):
        print('get_projects is getting called now === ')
        bearer_token = session['APPID_USER_TOKEN']
        headers = {'Authorization': f"Bearer {bearer_token}"}

        get_user_projects_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{user_id}/projects"
        user_projects_response = requests.get(get_user_projects_endpoint, headers=headers)
        user_projects_response.raise_for_status()

        user_projects = user_projects_response.json()
        user_projects = parse_obj_as(List[ProjectsOutput], user_projects)
        return user_projects
