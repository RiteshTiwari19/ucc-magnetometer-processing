import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, State, html, Input, Output, Patch, ALL
from dataservices import InMermoryDataService
import datetime
from flask import session
from components import Pagination, MagDataComponent, InterpolationComponent
import dash_mantine_components as dmc


# import MagDataComponent


def get_workspaces_html(total_projects=2):
    workspace_tabs = html.Div([
        html.Div(
            [
                html.P(id='hover-out'),
                dbc.Tabs(
                    [
                        dbc.Tab(label="Projects", tab_id="projects", activeTabClassName="fw-bold",
                                activeLabelClassName="text-success"),
                        dbc.Tab(label="Diurnal Correction", tab_id="mag_data_diurnal", activeTabClassName="fw-bold",
                                activeLabelClassName="text-success"),
                        dbc.Tab(label="Residuals", tab_id="mag_data", activeTabClassName="fw-bold",
                                activeLabelClassName="text-success"),
                        dbc.Tab(label="Interpolation", tab_id="mag_data_interpolation", activeTabClassName="fw-bold",
                                activeLabelClassName="text-success"),
                    ],
                    id="tabs",
                    active_tab="projects" if 'current_active_project' not in session else "mag_data",
                    style={'width': '100%'}
                ),
                html.Div(id="workspace-content", style={
                    'width': '100%',
                    'padding': '10px',
                    'display': 'flex',
                    'flexDirection': 'row',
                    'flexWrap': 'wrap',
                    'alignItems': 'stretch'
                }),
            ], style={'width': '100%'}, ),

        html.Div(children=Pagination.get_pagination(total_projects=total_projects), id='workspace-pagination-footer',
                 style={'width': '100%', 'padding': '10px'})
    ],
        style={
            'textAlign': 'center',
            'width': '100%',
            'padding': '10px',
            'display': 'flex',
            'flexDirection': 'row',
            'flexWrap': 'wrap'
        }
    )

    return workspace_tabs


def get_existing_workspaces(workspaces=None):
    if workspaces is None:
        workspaces = []

    cards = []

    if len(workspaces) == 0:
        cards += [
            dbc.Card([
                dbc.CardHeader([
                    "Project"
                ]),
                dbc.CardBody([
                    html.H4(f"asdad", className="card-title"),
                    html.Br(),
                    html.P(f"Date Created:", className="card-text"),
                    html.P(f"Date Modified:")
                ], className="card-body"),

                dbc.CardFooter([
                    html.Div([
                        html.Div(dbc.Button('Select', className='btn btn-lg',
                                            style={'background': '#00bfa5', 'margin': '10px', 'width': '100%'})),
                        html.Div(dbc.Button('Delete', className='btn btn-lg btn-danger',
                                            style={'margin': '10px', 'width': '100%'}))
                    ], style={
                        'display': 'flex',
                        'flexDirection': 'row',
                        'flexWrap': 'wrap',
                        'justifyContent': 'space-around'
                    })

                ])
            ], className="card text-white card border-success mb-3",
                style={'minWidth': '30%', 'width': '30%', 'display': 'inline-block', 'visibility': 'hidden',
                       'margin': '10px', 'height': '40%'})
        ]

    cards += [dbc.Popover(trigger='hover', target='wrkspc-sel-btn-2', id='popover', className='d-none')]
    cards += [dbc.Card([
        dbc.CardHeader([
            "New Project"
        ]),
        dbc.CardBody([
            html.H4(f"Create new project", className="card-title"),
            html.Br(),
            dbc.FormFloating(
                [
                    dbc.Input(type='input', placeholder="Project 1",
                              id={'type': 'input', 'form': 'new_proj', 'id': 'create-proj-name-fld'}),
                    dbc.Label("Project Name"),
                ]
            ),
        ], className="card-body"),

        dbc.CardFooter(
            dbc.Button('Create', id={'type': 'button', 'action': 'wrk-create', 'subset': 'projects', 'idx': -1},
                       className='btn btn-block', value='some-cal',
                       style={'background': '#00bfa5'}),
            style={'position': 'absolute',
                   'bottom': 0,
                   'left': 0,
                   'right': 0})
    ], className="card text-white card border-success mb-3",
        style={'minWidth': '30%', 'width': '30%', 'display': 'inline-block', 'margin': '10px'})]
    for idx, workspace in enumerate(workspaces):
        card = dbc.Card([
            dbc.CardHeader([
                "Project"
            ]),
            dbc.CardBody([
                html.H4(f"{workspace['name']}", className="card-title"),
                html.Br(),
                html.P(f"Date Created: {workspace['date_created']}", className="card-text"),
                html.P(f"Date Modified: {workspace['date_modified']}")
            ], className="card-body"),

            dbc.CardFooter([
                html.Div([
                    html.Div(dbc.Button('Select', className='btn btn-lg zoom', value=workspace['name'],
                                        id={'type': 'button', 'subset': 'projects', 'action': 'wrk-select',
                                            'idx': workspace['name']},
                                        style={'background': '#00bfa5', 'margin': '10px', 'width': '100%'})),
                    html.Div(dbc.Button('Delete', className='btn btn-lg btn-danger zoom', value=workspace['name'],
                                        id={'type': 'button', 'action': 'wrk-delete', 'subset': 'projects',
                                            'idx': workspace['name']},
                                        style={'margin': '10px', 'width': '100%'}))
                ], style={
                    'display': 'flex',
                    'flexDirection': 'row',
                    'flexWrap': 'wrap',
                    'justifyContent': 'space-around'
                })

            ])
        ], className="card text-white card border-none mb-3",
            style={'minWidth': '30%', 'width': '30%', 'display': 'inline-block', 'margin': '10px'},
            id=f'project-container-div', class_name='zoom')

        cards.append(card)
    return cards


def switch_workspace_tab_outer(app: dash.Dash, du):
    @app.callback(
        Output("workspace-content", "children"),
        Output("workspace-pagination-footer", "style"),
        Output("workspace-pagination-footer", "children"),
        Output("pagination-bar", "active_page"),
        Input("tabs", "active_tab"),
        Input("pagination-bar", "active_page")
    )
    def switch_workspace_tab(at, active_page):
        visibility_patch = Patch()
        if at == "projects":

            if len(InMermoryDataService.WorkspaceService.workspaces) % 5 == 0 and active_page * 5 > len(
                    InMermoryDataService.WorkspaceService.workspaces):
                active_page = active_page - 1

            if active_page <= 1:
                active_page = 1

            total_workspaces = len(InMermoryDataService.WorkspaceService.workspaces)
            visibility_patch['visibility'] = 'visible'
            start_workspace = ((active_page * 5) - 5)
            end_workspace = start_workspace + 5
            if end_workspace > total_workspaces:
                end_workspace = total_workspaces

            displayed_workspace = InMermoryDataService.WorkspaceService.workspaces[start_workspace:end_workspace]

            return get_existing_workspaces(displayed_workspace), visibility_patch, \
                Pagination.get_pagination(
                    total_projects=len(InMermoryDataService.WorkspaceService.workspaces)), active_page

        elif at == "mag_data":
            visibility_patch['visibility'] = 'hidden'
            return MagDataComponent.get_mag_data_page(session, du), visibility_patch, Pagination.get_pagination(
                total_projects=len(InMermoryDataService.WorkspaceService.workspaces)), 1
        elif at == "mag_data_interpolation":
            visibility_patch['visibility'] = 'hidden'
            return InterpolationComponent.get_interpolation_page(session), visibility_patch, Pagination.get_pagination(
                total_projects=len(InMermoryDataService.WorkspaceService.workspaces)), 1
        else:
            visibility_patch['visibility'] = 'hidden'
            return html.P(""), visibility_patch, Pagination.get_pagination(
                total_projects=len(InMermoryDataService.WorkspaceService.workspaces)), 1


def workspace_button_handler(app: dash.Dash):
    @app.callback(
        Output("tabs", "active_tab", allow_duplicate=True),
        Input({'type': 'button', 'subset': 'projects', 'idx': ALL, 'action': ALL}, 'n_clicks'),
        State({'type': 'input', 'form': 'new_proj', 'id': ALL}, 'value'),
        State("tabs", "active_tab"),
        prevent_initial_call=True,
    )
    def workspace_button_handler(clicks, form_value, active_tab_current_state):
        ct = dash.callback_context
        button_id = ct.triggered_id

        if button_id is None:
            return active_tab_current_state

        if button_id['action'] == 'wrk-create':
            if form_value[0] is not None:
                InMermoryDataService.WorkspaceService.add_project({'name': form_value[0]})
                return "projects"
        elif button_id['action'] == 'wrk-delete':
            InMermoryDataService.WorkspaceService.delete_project(button_id['idx'])
        elif button_id['action'] == 'wrk-select':
            session['current_active_project'] = button_id['idx']
            return "mag_data"
        return "projects"
