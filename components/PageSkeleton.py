import dash_mantine_components as dmc


def get_skeleton():
    skeleton = [

               dmc.Paper(dmc.LoadingOverlay(
                   children=[
                       dmc.Stack(
                           spacing="xs",
                           children=[
                               dmc.Skeleton(height=500, width="100%", visible=True),
                           ],
                       )],
                   loaderProps={"variant": "dots", "color": "orange", "size": "xl"}
               ), radius='md', shadow='lg', p='md')]

    return dmc.Stack(children=skeleton, align='stretch', mt='md')
