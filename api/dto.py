from typing import List

from pydantic import BaseModel
from datetime import datetime


class DatasetTypesResponse(BaseModel):
    name: str
    description: str
    id: str


class DatasetResponse(BaseModel):
    name: str | None
    path: str | None
    created_at: datetime | None
    dataset_type: DatasetTypesResponse | None


class ProjectsResponse(BaseModel):
    id: str
    name: str | None
    tags: dict | None
    created_at: datetime | None
    modified_at: datetime | None
    datasets: List[DatasetResponse] | None


class UserResponse(BaseModel):
    id: str | None
    first_name: str | None = ""
    last_name: str | None = ""
    display_name: str | None = first_name + " " + last_name
    email: str | None
    created_at: datetime


class UserResponseDTO(UserResponse):
    class ProjectsInner(BaseModel):
        role: str | None
        projects: List[ProjectsResponse] | None

    projects: ProjectsInner | None


class CreateDatasetDTO(BaseModel):
    name: str
    path: str
    dataset_type_id: str


class CreateProjectDTO(BaseModel):
    class CreateDatasetInnerDTO(BaseModel):
        dataset: CreateDatasetDTO | None
        project_dataset_state: str | None

    class UserRoleInnerDTO(BaseModel):
        role: str | None
        user_id: str | None

    name: str | None
    tags: dict | None
    dataset: CreateDatasetInnerDTO | None
    user_role: List[UserRoleInnerDTO] | None


class ProjectDTO(BaseModel):
    name: str | None
    tags: dict | None
    created_at: datetime | None
    modified_at: datetime | None


class ProjectUserInputDAO(BaseModel):
    role: str | None = "CONTRIBUTOR"


class ProjectUserDTO(ProjectUserInputDAO):
    project: ProjectDTO


class UserResponseDatasetsDTO(UserResponse):
    projects: List[ProjectUserDTO] | None


class UpdateProjectTagsDTO(BaseModel):
    tags: dict | None


class ProjectsOutput(BaseModel):
    class ProjectDatasetInputDAO(BaseModel):
        project_dataset_state = "INIT"

    class ProjectDatasetDTO(ProjectDatasetInputDAO):
        dataset: DatasetResponse

    class UserInProject(ProjectUserInputDAO):
        user: UserResponse

    id: str
    name: str | None
    tags: dict | None
    created_at: datetime | None
    modified_at: datetime | None
    datasets: List[ProjectDatasetDTO] | None
    users: List[UserInProject] | None
