import math

import dash_bootstrap_components as dbc
from dash import dcc, html


def get_pagination(parent_div_id='pagination-parent-div',
                   pagination_id='pagination-bar',
                   total_projects=1,
                   step=1,
                   value=1,
                   marks=None
                   ):
    min_pages = 1
    max_pages = math.ceil(total_projects / 5)

    pagination = html.Div(
        [
            dbc.Pagination(id=pagination_id, max_value=max_pages, min_value=min_pages,
                           first_last=True, previous_next=True, step=step, active_page=1,
                           fully_expanded=False
                           ),
        ],
        id=parent_div_id,
        style={'display': 'flex', 'flexDirection': 'row', 'alignItems': 'center', 'justifyContent': 'center'}
    )
    return pagination
