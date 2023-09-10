import os

from azure.storage.blob import BlobClient, BlobServiceClient
from azure.identity import DefaultAzureCredential

import AppConfig


class BlobConnector:
    account_url = f"https://{AppConfig.STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    default_credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url, credential=default_credential)

    @classmethod
    def upload_blob(cls, blob_name: str,
                    local_file_path: str,
                    state: str = None,
                    linked: bool = False,
                    user_id: str = None,
                    project_id: str = None):
        with open(file=local_file_path, mode="rb") as data:
            container = AppConfig.DATASETS_CONTAINER if not linked else AppConfig.PROJECTS_CONTAINER
            if linked:
                blob_name = f"{project_id}/{blob_name}/{state}/{blob_name}"
            else:
                blob_name = f"datasets/{user_id}/{blob_name}"

            blob_client = cls.blob_service_client.get_container_client(container=container)
            blob_client.upload_blob(name=blob_name, data=data, overwrite=True)

    @classmethod
    def download_blob(cls,
                      blob_name: str,
                      download_location: str,
                      linked: bool = False):
        with open(file=download_location, mode="wb") as download_file:
            container = AppConfig.DATASETS_CONTAINER if not linked else AppConfig.PROJECTS_CONTAINER
            blob_client = cls.blob_service_client.get_container_client(container=container)
            download_file.write(blob_client.download_blob(blob_name).readall())

    @classmethod
    def copy_blob_between_containers(cls, source_blob_path, target_blob_path, copy_from_container, copy_to_container):

        source_blob_path = f"https://{AppConfig.STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{copy_from_container}/{source_blob_path}"
        copied_blob = cls.blob_service_client.get_blob_client(copy_to_container, target_blob_path)
        copied_blob.start_copy_from_url(source_blob_path)

        # Optionally Delete Original Blob
        # remove_blob = cls.blob_service_client.get_blob_client(copy_from_container, source_blob_path)
        # remove_blob.delete_blob()

    @classmethod
    def delete_blob(cls, container_name, blob_path):
        blob_client = cls.blob_service_client.get_blob_client(container=container_name, blob=blob_path)
        blob_client.delete_blob()

if __name__ == "__main__":
    # dfl = os.getcwd() + f"\\downloaded.csv" blob_name = "datasets/a02c649d-587a-4b7e-b1c3-1545771040e6/18_05.csv"
    # BlobConnector.download_blob(blob_name=blob_name, download_location=dfl) BlobConnector.download_blob(
    # blob_name="18_05.csv", user_id="a02c649d-587a-4b7e-b1c3-1545771040e6",
    # local_file_path="C:\\Users\\T04091\\PycharmProjects\\mag-project\\data\\Ritesh Tiwari\\bob_12_03_processed.csv")

    # BlobConnector.copy_blob_between_containers(
    #     source_blob_path='datasets/a02c649d-587a-4b7e-b1c3-1545771040e6/ISAPIWORKING.csv',
    #     target_blob_path='datasets/a02c649d-587a-4b7e-b1c3-1545771040e6/ISAPINOTWORKING.csv',
    #     copy_from_container=AppConfig.DATASETS_CONTAINER,
    #     copy_to_container=AppConfig.PROJECTS_CONTAINER
    # )

    print('HOHO')
