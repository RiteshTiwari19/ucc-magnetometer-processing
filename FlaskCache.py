from celery import Celery
from dash import CeleryManager, Output, Input, callback
from flask_caching import Cache

celery_app = Celery(__name__,
                    broker='redis://localhost:6379/0',
                    backend='redis://localhost:6379/1',
                    )

default_config = "CeleryConfig"

celery_app.config_from_object(default_config)

background_callback_manager = CeleryManager(celery_app)
cache = Cache()