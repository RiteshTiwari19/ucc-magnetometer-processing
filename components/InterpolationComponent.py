import base64
import os
import shutil
import threading
import uuid
from io import BytesIO

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import pandas as pd
import rasterio
from dash import html, Input, Output, callback, callback_context, State
from dash.exceptions import PreventUpdate
from flask import session
from matplotlib import pyplot as plt
from rasterio.plot import show

import AppConfig
from Celery import background_callback_manager
from FlaskCache import cache
from api import InterpolationService
from api.DatasetService import DatasetService
from api.ProjectsService import ProjectService
from api.dto import DatasetResponse, DatasetUpdateDTO, CreateNewDatasetDTO, CreateDatasetDTO
from auth import AppIDAuthProvider
from components import ResidualComponent
from utils.AzureContainerHelper import BlobConnector
from utils.ExportUtils import ExportUtils


def get_interpolation_page(session):
    active_project = ProjectService.get_project_by_id(session=session,
                                                      project_id=session[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])

    raster_save_file = f'{session[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT]}-{session[AppConfig.WORKING_DATASET]}.tiff'

    interpolation_page = html.Div([
        html.Div(ResidualComponent.get_page_tags(active_project, tags_to_add={
            'Stage': 'Interpolation'
        }, session_store=session, skip_extra_styling=True), id='mag-data-tags-div',
                 style={
                     'display': 'flex',
                     'flexDirection': 'row',
                     'flexWrap': 'wrap',
                     'alignItems': 'space-between',
                     'justifyContent': 'flex-start'
                 }),
        dmc.Divider(size=3,
                    color='gray', variant='dashed', style={'marginTop': '1em', 'marginBottom': '1.5em'}),
        dmc.Text("Interpolation",
                 style={"fontSize": 20, "color": "#009688"}),

        html.Div('{}----{}----{}'.format(
            session[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
            session[AppIDAuthProvider.APPID_USER_NAME],
            session[AppConfig.WORKING_DATASET]
        ), id='interpolation-placeholder', style={'visibility': 'hidden'}),

        get_cta_input_block(session),

        html.Br(),

        dmc.LoadingOverlay(
            html.Div(
                children=[
                    dmc.Image(width='100%', withPlaceholder=True,
                              id='interpolated-raster-image', height='800px',
                              style={'minHeight': '650px'}),
                    html.Br(),
                    dbc.Button('Export Raster',
                               color='success',
                               download=f'{session[AppConfig.WORKING_DATASET]}-raster.tiff',
                               href='/download/{}.{}____{}'.format('NO_ID',
                                                                   'tiff',
                                                                   raster_save_file),
                               external_link=True,
                               target="_blank",
                               outline=True,
                               disabled=True,
                               id='export_interpolation_raster',
                               )
                ], id='interpolated-raster-parent-group'),
            loaderProps={"variant": "dots", "color": "orange", "size": "xl"}
        ),
        html.Br(),
        html.Div(
            dmc.Group(
                dmc.Button(
                    "Done",
                    color='green',
                    variant='Filled',
                    id='finish-interpolation-page',
                    disabled=True
                )
            )
        , className='fix-bottom-right')

    ],
        style={
            'display': 'flex',
            'flexDirection': 'column',
            'width': '100%'
        })

    return interpolation_page


@cache.memoize(timeout=50000)
def get_or_download_dataframe(session_store, dataset_id=None):
    if not dataset_id:
        dataset_id = session_store[AppConfig.WORKING_DATASET]

    project = ProjectService.get_project_by_id(
        project_id=session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
        session=session_store
    )

    dataset: DatasetResponse = [d.dataset for d in project.datasets if d.dataset.id == dataset_id][0]

    if 'local_path' in dataset.tags and dataset_id in dataset.tags['local_path']:
        ret_df = pd.read_csv(dataset.tags['local_path'][dataset.id])

        unnamed_cols = [col for col in ret_df.columns if 'unnamed' in col.lower()]
        ret_df = ret_df.drop(columns=unnamed_cols)

        if 'Baseline' in ret_df.columns:
            ret_df.rename(columns={'Baseline': 'Residuals'}, inplace=True)

        return ret_df

    download_path = ExportUtils.download_data_if_not_exists(dataset_path=dataset.path,
                                                            dataset_id=dataset.id,
                                                            session=session_store)
    dataset_tags = dataset.tags or {}
    if 'local_path' not in dataset.tags:
        dataset_tags['local_path'] = {f'{dataset.id}': download_path}
    else:
        dataset_tags['local_path'][dataset.id] = download_path

    updated_dataset = DatasetService.update_dataset(dataset_id=dataset.id,
                                                    session_store=session_store,
                                                    dataset_update_dto=DatasetUpdateDTO(tags=dataset_tags))
    ret_df = pd.read_csv(download_path)
    unnamed_cols = [col for col in ret_df.columns if 'unnamed' in col.lower()]
    ret_df = ret_df.drop(columns=unnamed_cols)

    if 'Baseline' in ret_df.columns:
        ret_df.rename(columns={'Baseline': 'Residuals'}, inplace=True)

    return ret_df


def get_cta_input_block(session):
    df = get_or_download_dataframe(session_store=session)

    ret_val = \
        dmc.Stack([
            dmc.Group(
                children=[
                    dmc.Select(
                        label='Interpolation Type',
                        description="Select the Interpolation Type",
                        data=['Linear', 'Cubic'],
                        value='Cubic',
                        required=False,
                        searchable=False,
                        clearable=False,
                        id='interpolation-type-select'
                    ),
                    dmc.Select(
                        description="Provide provide the column you want to interpolate",
                        label='Column to Interpolate',
                        data=df.columns,
                        required=False,
                        searchable=True,
                        clearable=False,
                        id='column-to-interpolate-select'
                    ),
                    dmc.NumberInput(
                        label="Grid Spacing",
                        description="Provide spacing for the interpolated grid",
                        value=20,
                        min=20,
                        step=5,
                        id='grid-spacing-number-input'
                    ),
                    dmc.Button(
                        "Interpolate",
                        variant='filled',
                        color='blue',
                        id='interpolate-btn',
                        disabled=True,
                    )

                ], grow=True, align='end'
            ),
            dmc.Group(
                children=[
                    dmc.Checkbox(
                        label='Show Contours',
                        disabled=True,
                        id='show-contours-checkbox',
                        color='green',
                        size='md'
                    )
                ], grow=False
            )
        ], align='stretch')
    return ret_val


@callback(
    Output("interpolate-btn", "disabled"),
    Input("grid-spacing-number-input", "value"),
    Input("column-to-interpolate-select", "value"),
    Input("interpolation-type-select", "value"),
)
def enable_interpolation_button(grid_spacing, col_to_interpolate, interpolation_type):
    triggered = callback_context.triggered
    if not triggered:
        raise PreventUpdate
    if not grid_spacing or not col_to_interpolate or not interpolation_type:
        return True
    elif col_to_interpolate == '' or interpolation_type == '':
        return True
    else:
        return False


@callback(
    Output("interpolated-raster-image", "src", allow_duplicate=True),
    Input("interpolate-btn", "n_clicks"),
    State("grid-spacing-number-input", "value"),
    State("column-to-interpolate-select", "value"),
    State("interpolation-type-select", "value"),
    State("interpolation-placeholder", "children"),
    State("local", "data"),
    background=True,
    manager=background_callback_manager,
    prevent_initial_call=True
)
def verde_interpolate(interpolation_button, spacing, col_to_interpolate, interpolation_type, id_placeholder,
                      local_storage):
    triggered = callback_context.triggered
    if not triggered:
        raise PreventUpdate
    if not interpolation_button:
        raise PreventUpdate
    else:
        working_dataset = id_placeholder.split('----')[2]
        df = get_or_download_dataframe(dataset_id=working_dataset, session_store=local_storage)
        figure = InterpolationService.verde_interpolate(
            df=df,
            col_to_interpolate=col_to_interpolate,
            interpolation_type=interpolation_type,
            tiff_name=id_placeholder,
            spacing=spacing
        )

        buf = BytesIO()
        figure.savefig(buf, format="png")
        # Embed the result in the html output.
        fig_data = base64.b64encode(buf.getbuffer()).decode("ascii")
        fig_bar_matplotlib = f'data:image/png;base64,{fig_data}'

        return fig_bar_matplotlib


@callback(
    Output('export_interpolation_raster', 'disabled'),
    Output('show-contours-checkbox', 'disabled'),
    Input('interpolate-btn', 'n_clicks')
)
def export_raster(btn_clicks):
    triggered = callback_context.triggered
    if not triggered or not btn_clicks:
        return True, True
    else:
        return False, False


@callback(
    Output("interpolated-raster-image", "src", allow_duplicate=True),
    Input('show-contours-checkbox', 'checked'),
    State("column-to-interpolate-select", "value"),
    prevent_initial_call=True
)
def show_contours(checked, col_to_interpolate):
    triggered = callback_context.triggered
    if not triggered:
        raise PreventUpdate
    else:
        save_path = os.path.join(
            AppConfig.PROJECT_ROOT,
            'data',
            session[AppIDAuthProvider.APPID_USER_NAME],
            'downloads',
            f'{session[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT]}-{session[AppConfig.WORKING_DATASET]}.tiff'
        )
        plt.style.use('dark_background')
        fig = plt.figure()
        ax = fig.gca()
        if checked:
            fig_raster = show(rasterio.open(save_path), with_bounds=True, contour=True,
                              title=f'{col_to_interpolate} Raster', ax=ax, cmap='RdBu_r')
            fig_raster.set_ylabel('Northing')
            fig_raster.set_xlabel('Easting')
        else:
            fig_raster = show(rasterio.open(save_path), with_bounds=True, contour=False,
                              title=f'{col_to_interpolate} Raster', ax=ax, cmap='RdBu_r')
            fig_raster.set_ylabel('Northing')
            fig_raster.set_xlabel('Easting')
            im = fig_raster.get_images()[0]
            fig.colorbar(im, ax=ax)

        buf = BytesIO()
        fig.savefig(buf, format="png")
        # Embed the result in the html output.
        fig_data = base64.b64encode(buf.getbuffer()).decode("ascii")
        fig_bar_matplotlib = f'data:image/png;base64,{fig_data}'

        return fig_bar_matplotlib


@callback(
    Output("finish-interpolation-page", "disabled"),
    Input("interpolate-btn", "n_clicks")
)
def enable_finish_button(interpolate_btn):
    triggered = callback_context.triggered
    if not triggered or not interpolate_btn:
        return True
    else:
        return False


@callback(
    Output("tabs", "active_tab", allow_duplicate=True),
    Input("finish-interpolation-page", "n_clicks"),
    State("interpolation-placeholder", "children"),
    State("local", "data"),
    prevent_initial_call=True
)
def finish_interpolation(btn_clicked, tiff_name, local_storage):
    triggered = callback_context.triggered

    if not triggered or not btn_clicked:
        raise PreventUpdate
    else:
        tiff_source_path = os.path.join(
            AppConfig.PROJECT_ROOT,
            'data',
            session[AppIDAuthProvider.APPID_USER_NAME],
            'downloads',
            f"{tiff_name.split('----')[0]}-{tiff_name.split('----')[2]}.tiff"
        )

        df_source_path = os.path.join(
            AppConfig.PROJECT_ROOT,
            "data",
            tiff_name.split('----')[1],
            "downloads",
            f"{tiff_name.split('----')[0]}-{tiff_name.split('----')[2]}.csv"
        )

        is_update = False

        project_id = local_storage[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT]
        active_project = ProjectService.get_project_by_id(session=local_storage,
                                                          project_id=project_id)
        parent_dataset_id = session[AppConfig.WORKING_DATASET]
        existing_dataset = DatasetService.get_dataset_by_id(parent_dataset_id,
                                                            session_store=local_storage)
        is_update = False
        existing_dataset_id = None
        existing_tags = None
        for dat in active_project.datasets:
            if str(dat.dataset.parent_dataset_id) == str(existing_dataset.id) \
                    and dat.dataset.tags['state'] == 'INTERPOLATED':
                is_update = True
                existing_dataset_id = dat.dataset.id
                existing_tags = dat.dataset.tags

        new_dataset_id = str(uuid.uuid4()) if not is_update else existing_dataset_id

        df_destination_path = os.path.join(AppConfig.PROJECT_ROOT, "data",
                                           tiff_name.split('----')[1],
                                           "exported",
                                           f'{new_dataset_id}.csv'
                                           )

        tiff_destination_path = os.path.join(
            AppConfig.PROJECT_ROOT,
            'data',
            tiff_name.split('----')[1],
            'exported',
            f"{new_dataset_id}.tiff"
        )

        shutil.copyfile(src=df_source_path, dst=df_destination_path)
        shutil.copyfile(src=tiff_source_path, dst=tiff_destination_path)

        azr_path = '{}.csv'.format(new_dataset_id)

        try:
            if not is_update:

                link_state = 'INTERPOLATED'
                tags = {'state': link_state}
                tags['export'] = {'Raster': f'{new_dataset_id}.tiff'}

                if 'Observation Dates' in existing_dataset.tags:
                    tags['Observation Dates'] = existing_dataset.tags['Observation Dates']

                new_dataset: CreateNewDatasetDTO = CreateNewDatasetDTO(
                    dataset=CreateDatasetDTO(
                        parent_dataset_id=parent_dataset_id,
                        id=new_dataset_id,
                        name=existing_dataset.name,
                        dataset_type_id=existing_dataset.dataset_type.id,
                        project_id=project_id,
                        path=f"datasets/{local_storage[AppIDAuthProvider.APPID_USER_BACKEND_ID]}/{new_dataset_id}.csv",
                        tags=tags
                    ),
                    project_dataset_state=link_state
                )
                created_dataset = DatasetService.create_new_dataset(dataset=new_dataset, session=local_storage)
            else:
                print(f'Updating existing interpolation dataset with id: {new_dataset_id}')
                updated_dataset = DatasetService.update_dataset(dataset_id=existing_dataset_id,
                                                                session_store=local_storage,
                                                                dataset_update_dto=DatasetUpdateDTO(
                                                                    tags=existing_tags))

            uploader_thread = threading.Thread(
                target=BlobConnector.upload_blob, kwargs={
                    'blob_name': azr_path,
                    'user_id': local_storage[AppIDAuthProvider.APPID_USER_BACKEND_ID],
                    'local_file_path': df_destination_path,
                    'linked': False
                })
            uploader_thread.start()

            cache.delete_memoized(DatasetService.get_dataset_by_id)
            cache.delete_memoized(ProjectService.get_project_by_id)

            session[AppConfig.WORKING_DATASET] = new_dataset_id
            return "projects"
        except:
            pass
