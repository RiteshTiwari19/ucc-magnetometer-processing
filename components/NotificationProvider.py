import dash_mantine_components as dmc
from dash_iconify import DashIconify
from dash import callback_context, no_update
from utils import Consts


def notify(message: str, action='show', notification_id='my-notification'):
    children_content = message.split(';')
    print('Updating Notification!')
    if children_content[0] == Consts.Consts.LOADING_DISPLAY_STATE:
        return dmc.Notification(
            id=notification_id,
            title=children_content[1],
            message=children_content[2],
            loading=True,
            color="orange",
            action=action,
            autoClose=False,
            disallowClose=False,
        )
    elif children_content[0] == Consts.Consts.FINISHED_DISPLAY_STATE:
        return dmc.Notification(
            id=notification_id,
            title=children_content[1],
            message=children_content[2],
            color="green",
            action="update",
            icon=DashIconify(icon="akar-icons:circle-check"),
        )
