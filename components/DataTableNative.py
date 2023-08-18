from dash import Dash, dash_table, dcc, html
import dash_bootstrap_components as dbc


def get_native_datable(df, datatable_id='datatable-datasets'):
    data_table = html.Div([
        dash_table.DataTable(
            id=datatable_id,
            columns=[
                {"name": i, "id": i, "deletable": True, "selectable": True} for i in df.columns if i != 'id'
            ],
            data=df.to_dict('records'),
            editable=True,
            filter_action="native",
            sort_action="native",
            sort_mode="multi",
            column_selectable="single",
            row_selectable="multi",
            row_deletable=True,
            selected_columns=[],
            selected_rows=[],
            page_action="native",
            page_current=0,
            page_size=10,
            fill_width=False
        ),

        html.Div(id='datatable-datasets-container-plot')],
        style={'overflow': 'scroll'}
    )

    return data_table
