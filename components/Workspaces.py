import dash
import dash_bootstrap_components as dbc
from dash import State, html, Input, Output, Patch, ALL, callback, clientside_callback, MATCH
from flask import session
import dash_mantine_components as dmc

from FlaskCache import cache
from api.ProjectsService import ProjectService
from api.UserService import UserService
from api.dto import CreateProjectDTO
from auth import AppIDAuthProvider
from components import Pagination, MagDataComponent, InterpolationComponent
from dataservices import InMermoryDataService


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
                    # active_tab="projects" if 'current_active_project' not in session else "mag_data",
                    active_tab="projects",
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
            dmc.Button('Create', id={'type': 'button', 'action': 'wrk-create', 'subset': 'projects', 'idx': -1},
                       className='zoom', variant='filled', fullWidth=True,
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
                    html.Div(dmc.Button('Select', className='zoom', size='lg',
                                        variant='filled',
                                        id={'type': 'button', 'subset': 'projects', 'action': 'wrk-select',
                                            'idx': workspace['id']},
                                        style={'background': '#00bfa5', 'margin': '10px', 'width': '100%'})),
                    html.Div(dmc.Button('Delete', className='zoom', size='lg',
                                        variant='filled', color='red',
                                        id={'type': 'button', 'action': 'wrk-delete', 'subset': 'projects',
                                            'idx': workspace['id']},
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
        Input("pagination-bar", "active_page"),
        State("local", "data")
    )
    def switch_workspace_tab(at, active_page, session_store):
        visibility_patch = Patch()
        displayed_workspace = UserService.get_user_projects(
            user_id=session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID],
            session=session_store)

        total_workspaces = len(displayed_workspace)

        if at == "projects":

            if total_workspaces % 5 == 0 and active_page * 5 > total_workspaces:
                active_page = active_page - 1

            if active_page <= 1:
                active_page = 1

            visibility_patch['visibility'] = 'visible'
            start_workspace = ((active_page * 5) - 5)
            end_workspace = start_workspace + 5
            if end_workspace > total_workspaces:
                end_workspace = total_workspaces

            displayed_workspace = displayed_workspace[start_workspace:end_workspace]

            return get_existing_workspaces(displayed_workspace), visibility_patch, \
                Pagination.get_pagination(
                    total_projects=total_workspaces), active_page

        elif at == "mag_data":
            visibility_patch['visibility'] = 'hidden'
            return MagDataComponent.get_mag_data_page(session, du), visibility_patch, Pagination.get_pagination(
                total_projects=total_workspaces), 1
        elif at == "mag_data_interpolation":
            visibility_patch['visibility'] = 'hidden'
            return InterpolationComponent.get_interpolation_page(session), visibility_patch, Pagination.get_pagination(
                total_projects=total_workspaces), 1
        else:
            visibility_patch['visibility'] = 'hidden'
            return html.P(""), visibility_patch, Pagination.get_pagination(
                total_projects=total_workspaces), 1


@callback(
    Output("tabs", "active_tab", allow_duplicate=True),
    Output({'type': 'button', 'subset': 'projects', 'idx': ALL, 'action': ALL}, "loading", allow_duplicate=True),
    Input({'type': 'button', 'subset': 'projects', 'idx': ALL, 'action': ALL}, 'n_clicks'),
    State({'type': 'input', 'form': 'new_proj', 'id': ALL}, 'value'),
    State("tabs", "active_tab"),
    State("local", "data"),
    prevent_initial_call=True)
def workspace_button_handler(clicks, form_value, active_tab_current_state, session_store):
    ct = dash.callback_context
    button_id = ct.triggered_id

    if button_id is None:
        return active_tab_current_state, [False] * len(clicks)

    if button_id['action'] == 'wrk-create':
        if form_value[0] is not None:
            project_to_create = get_new_project(project_name=form_value[0], session_store=session_store)
            ProjectService.create_new_project(project=project_to_create, session=session_store)
            cache.delete_memoized(UserService.get_projects)
            return "projects", [False] * len(clicks)
    elif button_id['action'] == 'wrk-delete':
        ProjectService.delete_project(session=session_store, project_id=button_id['idx'])
        cache.delete_memoized(UserService.get_projects)
    elif button_id['action'] == 'wrk-select':
        session['current_active_project'] = button_id['idx']
        return "mag_data", [False] * len(clicks)
    return "projects", [False] * len(clicks)


clientside_callback(
    """
    function(n_clicks) {
        return true
    }
    """,
    Output({'type': 'button', 'action': 'wrk-create', 'subset': 'projects', 'idx': -1}, "loading",
           allow_duplicate=True),
    Input({'type': 'button', 'action': 'wrk-create', 'subset': 'projects', 'idx': -1}, "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        return true
    }
    """,
    Output({'type': 'button', 'action': 'wrk-delete', 'subset': 'projects', 'idx': MATCH}, "loading",
           allow_duplicate=True),
    Input({'type': 'button', 'action': 'wrk-delete', 'subset': 'projects', 'idx': MATCH}, "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        return true
    }
    """,
    Output({'type': 'button', 'action': 'wrk-select', 'subset': 'projects', 'idx': MATCH}, "loading",
           allow_duplicate=True),
    Input({'type': 'button', 'action': 'wrk-select', 'subset': 'projects', 'idx': MATCH}, "n_clicks"),
    prevent_initial_call=True,
)


def get_new_project(project_name, session_store):
    project: CreateProjectDTO = CreateProjectDTO()
    project.name = project_name
    project.tags = {}

    user_role: CreateProjectDTO.UserRoleInnerDTO = CreateProjectDTO.UserRoleInnerDTO()
    user_role.role = session_store[AppIDAuthProvider.APPID_USER_ROLES][0]
    user_role.user_id = session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID]

    project.user_role = [user_role]

    return project
