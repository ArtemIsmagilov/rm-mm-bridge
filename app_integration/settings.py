import os
from dotenv import load_dotenv

load_dotenv('.docker.env')


RM_PROTOCOL = os.environ['RM_PROTOCOL']
RM_HOST = os.environ['RM_HOST']
RM_PORT = os.environ['RM_PORT']

MM_PROTOCOL = os.environ['MM_PROTOCOL']
MM_HOST = os.environ['MM_HOST']
MM_PORT = os.environ['MM_PORT']

APP_PROTOCOL = os.environ['APP_PROTOCOL']
APP_HOST_INTERNAl = os.environ['APP_HOST_INTERNAl']
APP_HOST_EXTERNAL = os.environ['APP_HOST_EXTERNAL']
APP_PORT = os.environ['APP_PORT']

ADMIN_RM_KEY_API = os.environ['ADMIN_RM_KEY_API']

MM_APP_TOKEN = os.environ['MM_APP_TOKEN']

app_url = f'{APP_PROTOCOL}://{APP_HOST_EXTERNAL}:{APP_PORT}'
redmine_url = f'{RM_PROTOCOL}://{RM_HOST}:{RM_PORT}'
mattermost_url = f'{MM_PROTOCOL}://{MM_HOST}:{MM_PORT}'
