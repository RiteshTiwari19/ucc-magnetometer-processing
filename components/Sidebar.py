import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html, dcc, State, html, Input, Output, MATCH, ALL
from flask import session
from auth import AppIDAuthProvider

SIDEBAR_STYLE = {
    "padding": "2rem 1rem",
    "alignItems": 'flex-start',
    "backgroundColor": "#757575!important",
    'position': 'sticky',
    'top': '0px',
    'bottom': 'auto',
    'height': '100vh',
    'width': '13rem'
}

sidebar = html.Div(dbc.Navbar(
    [
        dbc.Nav(
            [
                html.H4("UCC Mag Data", style={'fontWeight': 'bold'}),
                html.Hr(),
                dmc.Group(
                    children=[
                        dmc.Avatar(children="A", color="cyan", radius="xl", id='sidebar_avatar'),
                        html.P(
                            f"Hello User", className="lead", id='sidebar_user',
                            style={'marginBottom': 0}
                        )
                    ]
                ),

                html.Hr(),
                html.Div([
                    dbc.Row([
                        dbc.Col([
                            dbc.NavLink([
                                html.I(className="fa-solid fa-house", id={"type": "sidebar-icon", "index": 1}),
                                html.Div("Home", style={'display': 'inline', 'marginLeft': '10px'}),
                                dbc.Popover(trigger='hover',
                                            target={"type": "sidebar-menu", "index": 1},
                                            id={"type": "sidebar-hover", "index": 1},
                                            className='d-none'
                                            )
                            ],
                                href="/dashboard/",
                                active="exact", id={"type": "sidebar-menu", "index": 1}, style={'color': '#ffab91'},
                                class_name='zoom'

                            ),
                            dbc.NavLink(
                                [html.I(className="fa-solid fa-database", id={"type": "sidebar-icon", "index": 2}),
                                 html.Div("Datasets", style={'display': 'inline', 'marginLeft': '10px'}),
                                 dbc.Popover(trigger='hover',
                                             target={"type": "sidebar-menu", "index": 2},
                                             id={"type": "sidebar-hover", "index": 2},
                                             className='d-none'
                                             )
                                 ],
                                href="/dashboard/datasets", active="exact", id={"type": "sidebar-menu", "index": 2},
                                style={'color': '#ffab91'}, class_name='zoom'),
                            dbc.NavLink(
                                [html.I(className="fa-solid fa-chart-line", id={"type": "sidebar-icon", "index": 3}),
                                 html.Div("Explore", style={'display': 'inline', 'marginLeft': '10px'}),
                                 dbc.Popover(trigger='hover',
                                             target={"type": "sidebar-menu", "index": 3},
                                             id={"type": "sidebar-hover", "index": 3},
                                             className='d-none'
                                             )
                                 ],
                                href="/dashboard/explore", active="exact", id={"type": "sidebar-menu", "index": 3},
                                style={'color': '#ffab91'}, class_name='zoom')
                        ])
                    ]),
                    dbc.Row([
                        dbc.Col([
                            html.Hr(),
                            dbc.NavLink([html.I(className="fa-solid fa-gear", id={"type": "sidebar-icon", "index": 4}),
                                         html.Div("Settings", style={'display': 'inline', 'marginLeft': '10px'}),
                                         dbc.Popover(trigger='hover',
                                                     target={"type": "sidebar-menu", "index": 4},
                                                     id={"type": "sidebar-hover", "index": 4},
                                                     className='d-none'
                                                     )
                                         ],
                                        href="/dashboard/settings", active="exact",
                                        id={"type": "sidebar-menu", "index": 4},
                                        style={'color': '#ffab91'}, class_name='zoom')
                        ])
                    ])
                ], style={'height': '100%', 'display': 'flex', 'flexDirection': 'column',
                          'justifyContent': 'space-between', 'flex': 'auto'})
            ],
            vertical=True,
            pills=True,
            navbar=True,
            justified=True,
            style={'height': '100%', 'width': '100%'}
        ),
    ],
    style=SIDEBAR_STYLE,
    id='nav-sidebar',
    color="dark"
), style={'height': '100%'})


def hover(app: dash.Dash):
    @app.callback(
        Output({'type': 'sidebar-icon', 'index': MATCH}, "className"),
        Input({'type': 'sidebar-hover', 'index': MATCH}, 'is_open'),
        Input({'type': 'sidebar-hover', 'index': MATCH}, 'target'),
    )
    def toggle_hover_behavior(is_open, target):
        default_classes = [
            {
                'index': 1,
                'classes': 'fa-solid fa-house',
                'hover_class': 'fa-solid fa-house fa-flip'
            },
            {
                'index': 2,
                'classes': 'fa-solid fa-database',
                'hover_class': 'fa-solid fa-database fa-flip'
            },
            {
                'index': 3,
                'classes': 'fa-solid fa-chart-line',
                'hover_class': 'fa-solid fa-chart-line fa-flip'
            },
            {
                'index': 4,
                'classes': 'fa-solid fa-gear',
                'hover_class': 'fa-solid fa-gear fa-spin'
            }
        ]
        target_el = [cls for cls in default_classes if cls['index'] == target['index']]
        if is_open:
            return target_el[0]['hover_class']
        else:
            return target_el[0]['classes']


def sidebar_user(app: dash.Dash):
    @app.callback(Output("sidebar_user", "children"), Output("sidebar_avatar", "children"), [Input("url", "pathname")])
    def sidebar_user(at):
        if AppIDAuthProvider.APPID_USER_TOKEN in session:
            return f"Hello, {session[AppIDAuthProvider.APPID_USER_NAME].split(' ')[0]}", \
                f"{session[AppIDAuthProvider.APPID_USER_NAME].split(' ')[0][0]}{session[AppIDAuthProvider.APPID_USER_NAME].split(' ')[1][0]}"
        else:
            return "Anonymous", "A"