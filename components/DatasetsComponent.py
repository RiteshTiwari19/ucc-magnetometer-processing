from typing import List
from urllib.parse import quote as urlquote

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import pandas as pd
from dash import State, html, Input, Output, ALL, callback, clientside_callback, MATCH, callback_context, \
    no_update
from dash import dcc
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from FlaskCache import cache
from api import ProjectsService
from api.DatasetService import DatasetService
from api.DatasetTypeService import DatasetTypeService
from api.dto import DatasetFilterDTO, DatasetsWithDatasetTypeDTO, DatasetUpdateDTO
from components import Toast
from utils.ExportUtils import ExportUtils


def get_color_based_on_dataset_type(dataset_type_name):
    if dataset_type_name == 'OBSERVATORY_DATA':
        return 'dark-yellow'
    elif dataset_type_name == 'SURVEY_DATA':
        return 'dark-green'
    else:
        return 'dark-yellow'


def get_datasets(session_store, datasets_filter: DatasetFilterDTO | None = None):
    if not datasets_filter:
        datasets_filter: DatasetFilterDTO = DatasetFilterDTO()
        datasets_filter.states = 'DETACHED'

    dataset_papers = [
        html.Div(id='choose-project-link-modal'),
        dmc.Group([
            dmc.Group([
                html.Div([
                    "Project",
                    dcc.Dropdown(
                        id={'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown',
                            'sub': 'project-filter'})
                ], style={'width': '100%'}),
                html.Div([
                    "Dataset Type",
                    dcc.Dropdown(
                        id={'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown',
                            'sub': 'dataset-type-filter'})
                ], style={'width': '100%'}),
                html.Div([
                    "Dataset State",
                    dcc.Dropdown(
                        options=['DETACHED', 'LINKED', 'DIURNALLY_CORRECTED', 'RESIDUALS_COMPUTED',
                                 'INTERPOLATED'],
                        value='DETACHED',
                        multi=True,
                        id={'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown',
                            'sub': 'dataset-state-filter'})
                ], style={'width': '100%'}),

                dmc.TextInput(label="Dataset Name:", placeholder="Provide a dataset name to filter",
                              id='dataset-name-filter', icon=DashIconify(icon='ic:sharp-search',
                                                                         width=30)),
            ], grow=True, style={'minWidth': '80%'}),
            dmc.Group([
                dmc.Button('Filter',
                           leftIcon=DashIconify(icon="system-uicons:filter", color='dark-green',
                                                width=20),
                           variant='filled',
                           color='blue',
                           id='filter-datasets-button'
                           )
            ], grow=False, maw='200px')

        ], align='end', grow=True, position='apart')
    ]

    datasets = get_datasets_from_db(datasets_filter, session_store)

    out = dmc.Stack([
        dmc.Stack(dataset_papers, align='stretch', id='datasets_filter_stack'),
        dmc.Stack(children=datasets, align='stretch', mt='sm', id='datasets_stack'),
        html.Div(id='export-configurer-modal')
    ], align='stretch', mt='lg')

    return out


def get_single_menu_item(dataset, dataset_format):
    if dataset_format == 'CSV':
        menu_item_id = {'subset': 'csv-export-item', 'action': 'export', 'type': 'btn', 'dataset_id': dataset.id}
        menu_item = dmc.MenuItem(
            "CSV",
            id=menu_item_id,
            icon=DashIconify(icon="iwwa:csv", color="lime"))

    elif dataset_format == 'SHP':
        menu_item_id = {'subset': 'shp-export-item', 'action': 'export', 'type': 'btn', 'dataset_id': dataset.id}

        menu_item = dmc.MenuItem("Shapefile",
                                 icon=DashIconify(icon="gis:shape-file", color="lime"),
                                 id=menu_item_id
                                 )
    else:
        menu_item_id = {'subset': 'raster-export-item', 'action': 'export', 'type': 'btn', 'dataset_id': dataset.id}

        menu_item = dmc.MenuItem("Raster",
                                 icon=DashIconify(icon="vaadin:raster", color="lime"),
                                 id=menu_item_id
                                 )

    return menu_item


def get_menu_items_for_dataset(dataset, session_store):
    menu_items = [get_single_menu_item(dataset, 'CSV')]

    if dataset.dataset_type.name == 'BATHYMETRY_DATA':
        menu_items.append(get_single_menu_item(dataset, 'TIFF'))
    if dataset.dataset_type.name != 'OBSERVATORY_DATA':
        menu_items.append(get_single_menu_item(dataset, 'SHP'))

    menu_dropdown = dmc.MenuDropdown(
        children=
        [
            dmc.MenuLabel("Format"),
            *menu_items
        ],
        style={'width': '100%'}
    )

    return menu_dropdown


def get_datasets_from_db(datasets_filter, session_store):
    dataset_papers = []
    datasets: List[DatasetsWithDatasetTypeDTO] = DatasetService.get_datasets(session=session_store,
                                                                             datasets_filter=datasets_filter)
    for idx, dataset in enumerate(datasets):
        dataset_paper = \
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            dmc.Stack(children=[
                                dmc.Group(children=[
                                    dmc.Title(dataset.dataset_type.name.replace('_', ' ').title(),
                                              color=get_color_based_on_dataset_type(dataset.dataset_type.name),
                                              underline=False, order=4),
                                    dmc.ActionIcon(
                                        DashIconify(icon="ooui:next-ltr", width=20, color='dark-gray'),
                                        size="xs"
                                    ),
                                    dmc.Text(dataset.name.upper(), color='blue', weight=700, underline=False),
                                ], style={'column-gap': '1px'}),
                                dmc.Group(children=[
                                    dmc.ActionIcon(
                                        DashIconify(icon="uil:calender", width=20, color='dark-gray'),
                                        size="xs"
                                    ),
                                    dmc.Text('CREATED AT', size='xs'),
                                    dmc.Text(dataset.created_at.strftime("%m/%d/%Y, %H:%M:%S"), color="dimmed",
                                             size='xs')
                                ]),
                                dmc.Group(children=[
                                    dmc.ActionIcon(
                                        DashIconify(icon="uil:calender", width=20, color='dark-gray'),
                                        size="xs"
                                    ),
                                    dmc.Text('MODIFIED AT', size='xs'),
                                    dmc.Text(dataset.modified_at.strftime("%m/%d/%Y, %H:%M:%S"), color="dimmed",
                                             size='xs')
                                ]),
                                dmc.Group(generate_tag_badges(dataset), position='left', spacing='xs')
                            ]),

                            dmc.Stack(children=[
                                dmc.Button('Delete',
                                           leftIcon=dmc.ActionIcon(
                                               DashIconify(icon="mdi:bin", width=20),
                                               size="lg",
                                               color='wine-red'
                                           ),
                                           variant='outline',
                                           color='wine-red',
                                           id={'type': 'btn', 'subset': 'datasets', 'action': 'delete',
                                               'index': dataset.id}),
                                dmc.Button('Link To Project',
                                           leftIcon=DashIconify(icon="mingcute:link-fill", color='dark-green'),
                                           variant='outline',
                                           color='lime',
                                           id={'type': 'btn', 'subset': 'datasets-modal',
                                               'action': 'link_to_project_modal',
                                               'index': dataset.id, 'dname': dataset.name}),

                                dmc.Menu(
                                    [
                                        dmc.MenuTarget(dmc.Button('Export',
                                                                  leftIcon=dmc.ActionIcon(
                                                                      DashIconify(icon="typcn:export", width=20),
                                                                      size="lg",
                                                                      color='lime'
                                                                  ), style={'width': '100%'}, variant='outline')),
                                        get_menu_items_for_dataset(dataset, session_store),
                                    ],
                                    trigger="hover",
                                    style={'width': '100%'},
                                    withArrow=True,
                                    position='left'
                                )
                            ], id=f'dataset-btn-stack-{idx}')
                        ],
                        position='apart', id='datasets-view-group'
                    )
                ],
                radius='md',
                shadow='lg',
                p='md')
        dataset_papers.append(dataset_paper)
    return dataset_papers


clientside_callback(
    """
    function(n_clicks) {
        return true
    }
    """,
    Output({'type': 'btn', 'subset': 'datasets', 'action': MATCH, 'index': MATCH}, "loading",
           allow_duplicate=True),
    Input({'type': 'btn', 'subset': 'datasets', 'action': MATCH, 'index': MATCH}, "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(nc1, opened) {
        return opened ? false: true
    }
    """,
    Output("modal-link-dataset-to-project", "opened"),
    Input("modal-close-button", "n_clicks"),
    State("modal-link-dataset-to-project", "opened"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(nc1, nc2, opened) {
        return opened ? false: true
    }
    """,
    Output("modal-export_dataset", "opened"),
    Input("export-modal-close-button", "n_clicks"),
    Input({'type': 'btn', 'subset': 'export-datasets', 'action': 'export-dataset-request', 'index': ALL, 'format': ALL},
          'n_clicks'),
    State("modal-export_dataset", "opened"),
    prevent_initial_call=True,
)


@callback(
    Output('dataset_tabs', 'active_tab'),
    Output("toast-placeholder-div", "children", allow_duplicate=True),
    Input({'type': 'btn', 'subset': 'datasets', 'action': ALL, 'index': ALL}, "n_clicks"),
    State({'idx': ALL, 'type': 'backend-search-dropdown', 'sub': 'link-filter'}, "value"),
    State('local', "data"),
    prevent_initial_call=True
)
def cta_handler(n_clicks, project_id, session_store):
    ct = callback_context
    button_id = ct.triggered_id

    if not any(click for click in n_clicks):
        raise PreventUpdate

    action = button_id['action']
    dataset_id = button_id['index']

    if action == 'delete':
        DatasetService.delete_dataset(dataset_id=dataset_id, session=session_store)
        return "existing_datasets", Toast.get_toast("Notification", 'Dataset deleted successfully', icon='info')
    if action == 'link_to_project':
        status = ProjectsService.ProjectService \
            .link_dataset_to_project(project_id=project_id[0], dataset_id=dataset_id, session_store=session_store)

        if status == 'NO_UPDATE':
            toast = Toast.get_toast("Notification", 'Dataset Already Linked to Project', icon='info')
        else:
            toast = Toast.get_toast("Notification", 'Dataset Linked to Project', icon='info')

        return "existing_datasets", toast
    return "existing_datasets", no_update


@callback(
    Output('choose-project-link-modal', 'children'),
    Input({'type': 'btn', 'subset': 'datasets-modal', 'action': 'link_to_project_modal',
           'index': ALL, 'dname': ALL}, "n_clicks"),
    State('local', "data"),
    prevent_initial_call=True
)
def open_modal(n_clicks, session_store):
    ct = callback_context
    button_id = ct.triggered_id
    if not any(click for click in n_clicks):
        raise PreventUpdate

    dataset_id = button_id['index']
    dataset_name = button_id['dname']

    return get_link_to_project_modal(dataset_id, dataset_name)


def get_link_to_project_modal(dataset_id, dataset_name):
    return html.Div(
        [
            dmc.Modal(
                title="Link Dataset to Project",
                id="modal-link-dataset-to-project",
                zIndex=10000,
                opened=True,
                centered=True,
                children=[
                    dmc.Group([
                        dmc.Text("Dataset", weight=500, underline=False),
                        dmc.Text(dataset_name, id='dataset_link_id', color='dimmed')
                    ]),

                    dmc.Space(h=15),

                    html.Div([
                        "Search Project",
                        dcc.Dropdown(id={'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown',
                                         'sub': 'link-filter'})
                    ]),

                    dmc.Space(h=20),
                    dmc.Group(
                        [
                            dmc.Button("Submit",
                                       id={'type': 'btn', 'subset': 'datasets', 'action': 'link_to_project',
                                           'index': dataset_id}),
                            dmc.Button(
                                "Close",
                                color="red",
                                variant="outline",
                                id="modal-close-button",
                            ),
                        ],
                        position="right",
                    ),
                ],
            ),
        ]
    )


@callback(
    Output({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': MATCH}, "options"),
    Input({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': MATCH}, "search_value"),
    State("local", "data")
)
def update_options(search_value, session_store):
    if not search_value or len(search_value) <= 2:
        raise PreventUpdate

    triggered = callback_context.triggered_id
    subject = triggered['sub']

    if subject == 'link-filter' or subject == 'project-filter':
        params = {'project_name': search_value}

        options = ProjectsService.ProjectService.fetch_projects(session_store=session_store, params=params)
        options = [{'label': o.name, 'value': o.id} for o in options]

        return options

    elif subject == 'dataset-type-filter':
        data_types = DatasetTypeService.get_dataset_types(session=session_store)
        options = [{'label': data_type.name, 'value': data_type.id} for data_type in data_types]
        return options
    else:
        return no_update


@callback(
    Output('datasets_stack', 'children'),
    Input('filter-datasets-button', 'n_clicks'),
    State('dataset-name-filter', 'value'),
    State({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': 'project-filter'},
          'value'),
    State({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': 'dataset-type-filter'},
          'value'),
    State({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': 'dataset-state-filter'},
          'value'),
    State('local', 'data'),
    prevent_initial_update=True
)
def filter_datasets(n_clicks, dataset_name_query, project_query, dataset_type_query, dataset_state_query,
                    session_store):
    if not n_clicks:
        raise PreventUpdate
    else:
        dataset_state_query = dataset_state_query
        dataset_filter_dto: DatasetFilterDTO = DatasetFilterDTO()

        dataset_filter_dto.states = ';'.join(dataset_state_query)

        if dataset_name_query:
            dataset_filter_dto.dataset_name = dataset_name_query

        if dataset_type_query:
            dataset_filter_dto.dataset_type_id = dataset_type_query

        if project_query:
            dataset_filter_dto.project_id = project_query

    return get_datasets_from_db(datasets_filter=dataset_filter_dto, session_store=session_store)


def file_download_link(dataset, data_type='CSV'):
    location = "/download/{}.{}".format(dataset.id, data_type)
    return location


def generate_tag_badges(dataset: DatasetsWithDatasetTypeDTO):
    tag_buttons = []
    idx = 0

    for key, value in dataset.tags.items():
        if key == 'state' or key == 'Observation Dates':
            btn_id = f'dataset-disabled-tag-btn-{idx}'

            btn_variant = 'subtle'
            btn_color = 'gray'

            btn_to_add = dmc.Group([dmc.Button(
                [
                    f"{key.upper()}: ",
                    dmc.Badge(f"{value}", color="secondary", className="ms-1", variant='gradient',
                              gradient={"from": "indigo", "to": "cyan"}),
                ],
                style={'display': 'inline-block', 'margin': '10px', 'padding': '5px'}, variant=btn_variant,
                color=btn_color,
                id=btn_id
            )
            ])

            idx += 1
            tag_buttons.append(btn_to_add)

        tag = 'EXPORT'
        values = []
        if key == 'export' and len(dataset.tags[key].keys()) > 0:
            for key_inner, value_inner in dataset.tags[key].items():
                lnk_btn = dbc.Button(
                    key_inner,
                    href="/download/{}.{}".format(dataset.id, key_inner),
                    target="_blank",
                    external_link=True,
                    outline=True,
                    color='primary'
                )

                values.append(lnk_btn)

            download_group_children = []

            for idx, btn in enumerate(values):
                if idx != len(values) - 1:
                    download_group_children.append(btn)
                else:
                    download_group_children.append(btn)

            download_group = dmc.Group(
                children=[
                    dmc.Title(tag.upper(), order=5),
                    dbc.ButtonGroup(
                        children=download_group_children,
                        size='sm'
                    )])

            tag_buttons.append(download_group)

    for project in dataset.projects:
        btn_id = f'dataset-disabled-tag-btn-{idx}'

        btn_variant = 'subtle'
        btn_color = 'gray'

        btn_to_add = dmc.Group([dmc.Button(
            [
                f"Linked Project: ",
                dmc.Badge(f"{project.project.name}", color="secondary", className="ms-1", variant='gradient',
                          gradient={"from": "indigo", "to": "cyan"}),
            ],
            style={'display': 'inline-block', 'margin': '10px', 'padding': '5px'}, variant=btn_variant,
            color=btn_color,
            id=btn_id
        )
        ])
        tag_buttons.append(btn_to_add)
    return tag_buttons


@callback(
    Output('export-configurer-modal', 'children'),
    Input({'subset': ALL, 'action': 'export', 'type': 'btn', 'dataset_id': ALL}, "n_clicks"),
    State('local', 'data'),
    prevent_initial_call=True
)
def configure_export(trigger, local_storage):
    if not callback_context.triggered or not any(click for click in trigger):
        raise PreventUpdate

    triggered_id = callback_context.triggered_id
    dataset = DatasetService.get_dataset_by_id(dataset_id=triggered_id['dataset_id'], session_store=local_storage)

    download_path = ExportUtils.download_data_if_not_exists(dataset_path=dataset.path,
                                                            dataset_id=dataset.id,
                                                            session=local_storage)

    df = pd.read_csv(download_path)

    unnamed_cols = [col for col in df.columns if 'unnamed' in col.lower()]

    df = df.drop(columns=unnamed_cols)

    if triggered_id['subset'] == 'csv-export-item':
        modal_title = 'CSV Export'
        export_format = 'csv'
    elif triggered_id['subset'] == 'shp-export-item':
        modal_title = 'Shape File Export'
        export_format = 'shp'
    else:
        modal_title = 'Raster Export'
        export_format = 'tiff'

    modal = dmc.Modal(
        title=modal_title,
        id="modal-export_dataset",
        zIndex=10000,
        opened=True,
        centered=True,
        children=[
            dmc.Group([
                dmc.Text("Dataset", weight=500, underline=False),
                dmc.Text(dataset.name, id='dataset_export_name', color='dimmed')
            ]),

            dmc.Space(h=15),

            dmc.MultiSelect(
                label='Columns to Export',
                value=['Easting', 'Northing'],
                data=df.columns,
                placeholder='Select columns to export',
                id='export-dataset-columns'
            ) if 'modal_title' != 'Raster Export' else dmc.Select(
                label='Column to Interpolate',
                data=df.columns,
                placeholder='Select column to interpolate',
                id='export-dataset-column-raster'
            ),

            dmc.Space(h=20),
            dmc.Group(
                [
                    dmc.Button("Request Export",
                               id={'type': 'btn', 'subset': 'export-datasets', 'action': 'export-dataset-request',
                                   'index': dataset.id, 'format': export_format}),
                    dmc.Button(
                        "Close",
                        color="red",
                        variant="outline",
                        id="export-modal-close-button",
                    ),
                ],
                position="right",
            ),
        ],
    )

    return modal


@callback(
    Output('local', 'data', allow_duplicate=True),
    Input({'type': 'btn', 'subset': 'export-datasets', 'action': 'export-dataset-request', 'index': ALL, 'format': ALL},
          'n_clicks'),
    State('export-dataset-columns', 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def process_export_request(btn_clicked, export_dataset_columns, local_storage):
    triggered = callback_context.triggered
    default_cols = {'Easting', 'Northing'}
    if not triggered or not any(click for click in btn_clicked):
        raise PreventUpdate
    elif default_cols.issubset(set(export_dataset_columns)) and len(default_cols) == len(export_dataset_columns):
        raise PreventUpdate
    else:

        triggered_id = callback_context.triggered_id

        dataset_id = triggered_id['index']
        export_format = triggered_id['format']

        dataset = DatasetService.get_dataset_by_id(dataset_id=dataset_id,
                                                   session_store=local_storage)

        if export_format == 'csv':
            exported_file_path = ExportUtils.export_csv(
                dataset_id=dataset_id,
                session=local_storage,
                cols_to_export=export_dataset_columns
            )

            existing_tags = dataset.tags
            if 'export' not in existing_tags:
                existing_tags['export'] = {'CSV': exported_file_path}
            else:
                existing_tags['export']['CSV'] = exported_file_path

        else:
            exported_file_path = ExportUtils.export_shp_file(
                dataset_id=dataset_id,
                session=local_storage,
                cols_to_export=export_dataset_columns
            )

            existing_tags = dataset.tags
            if 'export' not in existing_tags:
                existing_tags['export'] = {'ShapeFile': exported_file_path}
            else:
                existing_tags['export']['ShapeFile'] = exported_file_path

        update_dataset_dto: DatasetUpdateDTO = DatasetUpdateDTO(
            tags=existing_tags
        )
        updated_dataset = DatasetService.update_dataset(dataset_id=dataset.id,
                                                        session_store=local_storage,
                                                        dataset_update_dto=DatasetUpdateDTO(tags=existing_tags))

        return no_update
