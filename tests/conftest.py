from httpx import HTTPError
import pytest
from jinja2 import Environment, PackageLoader, select_autoescape
from wsgi import create_app, settings
from wsgi.my_bot import get_user_by_username, create_user, create_token
from wsgi.redmine_api import (
    create_redmine_user, create_redmine_project, create_project_memberships, all_roles, delete_redmine_project,
    delete_redmine_user_by_username
)

settings.envs = settings.Testing()

env = Environment(loader=PackageLoader("tests"), autoescape=select_autoescape())

# create mattermost test user, if it doesn't exist
test_mm_user1 = get_user_by_username(username=settings.envs.test_mm_username1)
if isinstance(test_mm_user1, HTTPError):
    test_mm_user1 = create_user({
        'email': settings.envs.test_mm_email1,
        'username': settings.envs.test_mm_username1,
        'password': settings.envs.test_mm_password1,
        'first_name': settings.envs.test_mm_first_name1,
        'last_name': settings.envs.test_mm_last_name1,
    })

rest_token1 = create_token(test_mm_user1['id'], {"description": "testuser1 token"})
settings.envs.test_mm_token1 = rest_token1['token']

test_mm_user2 = get_user_by_username(username=settings.envs.test_mm_username2)
if isinstance(test_mm_user2, HTTPError):
    test_mm_user2 = create_user({
        'email': settings.envs.test_mm_email2,
        'username': settings.envs.test_mm_username2,
        'password': settings.envs.test_mm_password2,
        'first_name': settings.envs.test_mm_first_name2,
        'last_name': settings.envs.test_mm_last_name2,
    })

rest_token2 = create_token(test_mm_user2['id'], {"description": "testuser2 token"})
settings.envs.test_mm_token2 = rest_token2['token']

# create redmine test user, if it doesn't exist
delete_redmine_user_by_username(settings.envs.test_rm_username1)
test_rm_user1 = create_redmine_user(
    login=settings.envs.test_rm_username1,
    password=settings.envs.test_rm_password1,
    firstname=settings.envs.test_rm_first_name1,
    lastname=settings.envs.test_rm_last_name1,
    mail=settings.envs.test_rm_email1,
)

delete_redmine_user_by_username(settings.envs.test_rm_username2)
test_rm_user2 = create_redmine_user(
    login=settings.envs.test_rm_username2,
    password=settings.envs.test_rm_password2,
    firstname=settings.envs.test_rm_first_name2,
    lastname=settings.envs.test_rm_last_name2,
    mail=settings.envs.test_rm_email2,
)

delete_redmine_project(resource_id='testing')
test_project_rm = create_redmine_project(
    name='Testing',
    identifier='testing',
    is_public=False,
)

first_role = all_roles()[0]
test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id, role_ids=[first_role.id])
test_memberships2 = create_project_memberships(project_id='testing', user_id=test_rm_user2.id, role_ids=[first_role.id])


@pytest.fixture
def app():
    app = create_app()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
