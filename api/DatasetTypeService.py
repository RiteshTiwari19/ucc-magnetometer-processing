from typing import List

import requests
from pydantic.tools import parse_obj_as

import AppConfig
from FlaskCache import cache
from api.dto import DatasetTypesResponse
from auth import AppIDAuthProvider


class DatasetTypeService:
    URL_PREFIX = 'api/v1/dataset-type'

    @classmethod
    @cache.memoize(timeout=50000, args_to_ignore=['session'])
    def get_dataset_types(cls, session, dataset_type_name='') -> List[DatasetTypesResponse]:
        # bearer_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImtpZCI6Ii1LSTNROW5OUjdiUm9meG1lWm9YcWJIWkdldyJ9.eyJhdWQiOiJhM2NmOTRjNC1hZGUxLTQzNjUtOWY3Yy1hMGQ0ZDdmZTI4ZGMiLCJpc3MiOiJodHRwczovL2xvZ2luLm1pY3Jvc29mdG9ubGluZS5jb20vYTg2NDAxZTEtYjAxOC00Nzc1LTkxMjItYjBkZjEwMTdjMzg0L3YyLjAiLCJpYXQiOjE2OTM5NDAxMTQsIm5iZiI6MTY5Mzk0MDExNCwiZXhwIjoxNjkzOTQ0MDU2LCJhaW8iOiJBY1FBTy84VUFBQUFEdHl3OENaZkVCc2h4VmJzYm02WDE0VUp3VlpFNlJTa0pnVTNZeXpxWW5MaXV4V0NHa3VqRkwzcy9JT1dGWkJzNll4TjdmQW1FUXRQY045SisrREswdm96aDIvSVZXWlhJL0pGdVhvWU9NUm5sYUFaTXBka2lRVndQYkNuL0wxMis4bHl6M3JiQmJGbnNGbzlRMGlTMGJIRzZ5SjZLOUQzVFNWSTBqcnZNNDVYSDI0VWQ5QjhWTDhrS24rU3pNZFYvaVhuSDR4SjVZVWFmQXMwTUlVOFgwclRnVFNYOTA5KzFkOFg2THNUVy9ib3c4SzRCVzBYUk5FcU92YnhZbVdiIiwiYXpwIjoiMDliNTllMzctN2UwZS00YzcyLTk0NGEtMTJmNzhjZjMwM2JkIiwiYXpwYWNyIjoiMCIsImlkcCI6ImxpdmUuY29tIiwibmFtZSI6IlJpdGVzaCBUaXdhcmkiLCJvaWQiOiJkZDAzNDMzNi1lMDAxLTQyNTItYmZmMC0zNGNmNTNjMTZkMDUiLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJyaXRlc2h0aXdhcmlAaG90bWFpbC5jby51ayIsInJoIjoiMC5BYThBNFFGa3FCaXdkVWVSSXJEZkVCZkRoTVNVejZQaHJXVkRuM3lnMU5mLUtOeXZBR0EuIiwic2NwIjoiTWlkZGxld2FyZSIsInN1YiI6InZMS3hKR3BRYnlfSkJITUpWQ3J2cFpZOHpwYTZjek55eGhpb2tJUWp4UEUiLCJ0aWQiOiJhODY0MDFlMS1iMDE4LTQ3NzUtOTEyMi1iMGRmMTAxN2MzODQiLCJ1dGkiOiJCaGpkQ1Zma3owdS05b0RWemd3TEFBIiwidmVyIjoiMi4wIn0.bhGWCSFJ633JBciNgO86GZ8rmGsVQ531-tpMa2A_fcpEO5ZczTnwXTv3l4_OfeW7jiqeNo5cw7YUCQTOiljuZG2uEWAlUJe80FjhaJcEWdMOiNwA2LposYWElt98x04Ljp7BgTEuGBoaLwUORVCgN1wEWF9zKQhYCTf7lJMTdCyG6ikw72BkvZd1GF72W6rxW6jn2PBJqNrNs8offQAqQ7DUPPLuOxvfnnzsc02borczjZRcgzPjFMF4y4uKY-MrzTXB1GauWCw3Emndh_tCdzTvWnqxwp0__HYn14c3jG9w_Wr2SAe3CykBUNJU11jXJPrhtpirfCX75J0vh-MV1g"

        bearer_token = session[AppIDAuthProvider.APPID_USER_TOKEN]

        params = {'offset': 0, 'limit': 5}
        headers = {'Authorization': f"Bearer {bearer_token}"}

        if dataset_type_name != '':
            params['dataset_type_name'] = dataset_type_name

        dataset_types_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/"
        dataset_types_response = requests.get(dataset_types_endpoint, params=params, headers=headers)
        dataset_types_response.raise_for_status()

        dataset_types = dataset_types_response.json()
        dataset_types = parse_obj_as(List[DatasetTypesResponse], dataset_types)

        return dataset_types

    @classmethod
    @cache.memoize(timeout=50000, args_to_ignore=['session'])
    def get_dataset_type_by_id(cls, session, dataset_type_id):
        bearer_token = session[AppIDAuthProvider.APPID_USER_TOKEN]
        headers = {'Authorization': f"Bearer {bearer_token}"}

        dataset_types_endpoint = f"{AppConfig.API_BASE_URL}/{cls.URL_PREFIX}/{dataset_type_id}"
        dataset_types_response = requests.get(dataset_types_endpoint, headers=headers)
        dataset_types_response.raise_for_status()

        dataset_type = dataset_types_response.json()
        dataset_type = parse_obj_as(DatasetTypesResponse, dataset_type)

        print(f'Dataset type name: {dataset_type.name}')

        return dataset_type
