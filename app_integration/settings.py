import os, multiprocessing
from dotenv import load_dotenv

load_dotenv('.docker.env')

APP_SCHEMA = os.environ['APP_SCHEMA']
APP_HOST_INTERNAl = os.environ['APP_HOST_INTERNAl']
APP_PORT_INTERNAL = os.environ['APP_PORT_INTERNAL']
APP_HOST_EXTERNAL = os.environ['APP_HOST_EXTERNAL']
APP_PORT_EXTERNAL = os.environ['APP_PORT_EXTERNAL']

MM_SCHEMA = os.environ['MM_SCHEMA']
MM_HOST_EXTERNAL = os.environ['MM_HOST_EXTERNAL']
MM_PORT_EXTERNAL = os.environ['MM_PORT_EXTERNAL']

RM_SCHEMA = os.environ['RM_SCHEMA']
RM_HOST_EXTERNAL = os.environ['RM_HOST_EXTERNAL']
RM_PORT_EXTERNAL = os.environ['RM_PORT_EXTERNAL']

rm_admin_key = os.environ['rm_admin_key']
mm_app_token = os.environ['mm_app_token']

app_url_internal = os.environ['app_url_internal']
app_url_external = os.environ['app_url_external']

redmine_url_external = os.environ['redmine_url_external']
mattermost_url_external = os.environ['mattermost_url_external']
