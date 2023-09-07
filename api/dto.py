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
    name: str | None
    path: str | None
    dataset_type_id: str | None
    project_id: str | None


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
    id: str | None
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

    id: str | None
    name: str | None
    tags: dict | None
    created_at: datetime | None
    modified_at: datetime | None
    datasets: List[ProjectDatasetDTO] | None
    users: List[UserInProject] | None


class CreateNewDatasetDTO(BaseModel):
    dataset: CreateDatasetDTO | None
    project_dataset_state: str | None


class DatasetInput(BaseModel):
    name: str | None
    path: str | None
    created_at: datetime | None
    modified_at: datetime | None


class DatasetsOutput(DatasetInput):
    class ProjectDatasetInputDAO(BaseModel):
        project_dataset_state: str | None = "INIT"

    class DatasetProjectDTO(ProjectDatasetInputDAO):
        project: ProjectDTO | None

    id: str | None
    projects: List[DatasetProjectDTO] | None


class DatasetFilterDTO(BaseModel):
    project_id: str | None
    dataset_name: str | None
    dataset_type_id: str | None


class DatasetType(BaseModel):
    name: str | None
    description: str | None
    id: str | None


class DatasetsWithDatasetTypeDTO(DatasetsOutput):
    dataset_type: DatasetType | None
