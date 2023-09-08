from dash import html, no_update, MATCH, ALL, callback, callback_context
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from api.ProjectsService import ProjectService
from auth import AppIDAuthProvider
from components import ResidualComponent


def get_diurnal_correction_page(session):
    active_project = ProjectService.get_project_by_id(session=session,
                                                      project_id=session[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])

    diurnal_page = dmc.Stack([
        html.Div(ResidualComponent.get_page_tags(active_project, tags_to_add={
            'Stage': 'Diurnal Correction'
        }), id='diurnal-page-tags-div',
                 style={
                     'display': 'flex',
                     'flexDirection': 'row',
                     'flexWrap': 'wrap',
                     'alignItems': 'space-between',
                     'justifyContent': 'flex-start'
                 }),
        html.Div(children=[
            dmc.Group(children=[
                dmc.Button('Skip', variant='outline', color='gray',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
                               'prev': 'None', 'action': 'skip'}),
                dmc.Button('Next', variant='color', color='green',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
                               'prev': 'None', 'action': 'next'}),
            ])
        ],
            className='fix-bottom-right')], align='stretch')

    return diurnal_page
