import pytest, os
from datetime import date, timedelta
from jinja2 import Environment, PackageLoader, select_autoescape
from redminelib import Redmine

from ext_funcs import choose_name, create_full_name
from tests.blocks_code import blocks
from tests.conftest import (
    test_mm_user1, test_mm_user2, test_project_rm, test_rm_user1, test_rm_user2, test_memberships1, test_memberships2
)
from wsgi import views
from wsgi.constants import OPTIONS_DONE_FOR_FORM
from wsgi.redmine_api import (
    all_trackers, all_issue_statuses, all_priorities, delete_redmine_user, create_redmine_user, all_roles,
    create_project_memberships
)
from wsgi.settings import envs


class TestHelp:
    endpoint = '/help'

    def test_success(self, client):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        response = client.post(self.endpoint, json=data)

        full_name = create_full_name(test_mm_user1['first_name'], test_mm_user1['last_name'])
        author = choose_name(full_name, test_mm_user1['username'])
        tmp_env = Environment(loader=PackageLoader("wsgi"), autoescape=select_autoescape())
        tm = tmp_env.get_template('help.md')

        text = tm.render(author=author)

        assert response.json == {'type': 'ok', 'text': text}

    def test_unregister_account(self, client):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        os.environ.pop(test_mm_user1['username'])

        response = client.post(self.endpoint, json=data)

        os.environ[test_mm_user1['username']] = test_rm_user1.login

        assert response.json == views.unregister_mm_account(test_mm_user1['username'])

    def test_no_rm_user(self, client):
        global test_rm_user1, test_memberships1
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        delete_redmine_user(test_rm_user1.id)

        response = client.post(self.endpoint, json=data)

        test_rm_user1 = create_redmine_user(
            login=envs.test_rm_username1,
            password=envs.test_rm_password1,
            firstname=envs.test_rm_first_name1,
            lastname=envs.test_rm_last_name1,
            mail=envs.test_rm_email1,
        )

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json == views.deactivate_or_not_exist_rm_account(test_rm_user1.login)


class TestNewTasksSubmit:
    endpoint = '/new_tasks_submit'

    @pytest.mark.parametrize('template', (
            'new_tasks_submit_msg1.txt',
            'new_tasks_submit_msg2.txt',
            'new_tasks_submit_msg3.txt',
    ))
    def test_success(self, client, template):
        response = blocks.block_1(self.endpoint, client, template)
        assert response.json['type'] == 'ok'

    @pytest.mark.parametrize('login_mm', (
            envs.test_mm_username1,
            envs.test_mm_username2,
    ))
    def test_unregister_account(self, client, login_mm):
        # UNREGISTERED USER
        os.environ.pop(login_mm)

        response = blocks.block_1(self.endpoint, client, 'new_tasks_submit_msg1.txt')

        os.environ[login_mm] = test_rm_user1.login

        assert response.json == views.unregister_mm_account(login_mm)

    def test_no_rm_user(self, client):
        # NO REDMINE USER
        global test_rm_user1, test_memberships1

        delete_redmine_user(test_rm_user1.id)

        response = blocks.block_1(self.endpoint, client, 'new_tasks_submit_msg1.txt')

        test_rm_user1 = create_redmine_user(
            login=envs.test_rm_username1,
            password=envs.test_rm_password1,
            firstname=envs.test_rm_first_name1,
            lastname=envs.test_rm_last_name1,
            mail=envs.test_rm_email1,
        )

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json == views.deactivate_or_not_exist_rm_account(test_rm_user1.login)

    @pytest.mark.parametrize('username', (
            'anonymous',
    ))
    def test_no_rm_user_in_subject(self, client, username):
        # NO REDMINE USER
        os.environ[username] = username
        response = blocks.block_1(self.endpoint, client, 'new_tasks_submit_msg1.txt', username)
        os.environ.pop(username)
        assert response.json == views.deactivate_or_not_exist_rm_account(username)

    @pytest.mark.parametrize('template', (
            'new_tasks_submit_msg4.txt',
    ))
    def test_error_invalid_input(self, client, template):
        response = blocks.block_1(self.endpoint, client, template)
        assert response.json == views.invalid_input_data()

    @pytest.mark.parametrize('template', (
            'new_tasks_submit_msg5.txt',
            'new_tasks_submit_msg6.txt',
    ))
    def test_error_invalid_date(self, client, template):
        response = blocks.block_1(self.endpoint, client, template)
        assert response.json == views.invalid_format_date()

    @pytest.mark.parametrize('template', (
            'new_tasks_submit_msg7.txt',  # START DATE > END DATE
    ))
    def test_error_date_greater(self, client, template):
        response = blocks.block_1(self.endpoint, client, template)
        assert response.json == views.start_date_greater()

    @pytest.mark.parametrize('template', (
            'new_tasks_submit_msg8.txt',  # LARGE SUBJECT
    ))
    def test_error_large_task(self, client, template):
        response = blocks.block_1(self.endpoint, client, template)
        assert response.json == views.long_subject()

    def test_no_access_project(self, client):
        global test_memberships1

        test_memberships1.delete()
        response = blocks.block_1(self.endpoint, client, 'new_tasks_submit_msg1.txt')
        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])
        assert response.json == views.no_access_project(test_rm_user1.login, test_project_rm.identifier)


class TestNewTaskSubmit:
    endpoint = '/new_task_submit'

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             'text...',
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             date.today().strftime('%d.%m.%Y'),
             (date.today() + timedelta(days=1)).strftime('%d.%m.%Y'),
             1,
             OPTIONS_DONE_FOR_FORM[0],
             None,
             ),
        ])
    def test_success(self, client, project, tracker, subject, description, status, priority, start_date, end_date,
                     estimated_time, done, assignee):
        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time,
            done, assignee
        )

        assert response.json['type'] == 'ok'

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             'text...',
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             date.today().strftime('%d.%m.%Y'),
             (date.today() + timedelta(days=1)).strftime('%d.%m.%Y'),
             1,
             OPTIONS_DONE_FOR_FORM[0],
             {'label': test_mm_user2['username'], 'value': test_mm_user2['id']},
             )
        ])
    def test_unregister_account(self, client, project, tracker, subject, description, status, priority, start_date,
                                end_date, estimated_time, done, assignee):
        # UNREGISTERED USER
        os.environ.pop(test_mm_user1['username'])
        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time,
            done, assignee
        )
        os.environ[test_mm_user1['username']] = test_rm_user1.login
        assert response.json == views.unregister_mm_account(test_mm_user1['username'])

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             'text...',
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             date.today().strftime('%d.%m.%Y'),
             (date.today() + timedelta(days=1)).strftime('%d.%m.%Y'),
             1,
             OPTIONS_DONE_FOR_FORM[0],
             {'label': test_mm_user2['username'], 'value': test_mm_user2['id']},
             )
        ])
    def test_no_rm_user(self, client, project, tracker, subject, description, status, priority, start_date, end_date,
                        estimated_time, done, assignee):
        # NO REDMINE USER
        global test_rm_user1, test_memberships1

        delete_redmine_user(test_rm_user1.id)

        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time,
            done, assignee
        )

        test_rm_user1 = create_redmine_user(
            login=envs.test_rm_username1,
            password=envs.test_rm_password1,
            firstname=envs.test_rm_first_name1,
            lastname=envs.test_rm_last_name1,
            mail=envs.test_rm_email1,
        )

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json == views.deactivate_or_not_exist_rm_account(test_rm_user1.login)

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             '?' * 500,  # INVALID DATA
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             date.today().strftime('%d.%m.%Y'),
             (date.today() + timedelta(days=1)).strftime('%d.%m.%Y'),
             1,
             OPTIONS_DONE_FOR_FORM[0],
             None,
             )
        ]
    )
    def test_long_subject(self, client, project, tracker, subject, description, status, priority, start_date, end_date,
                          estimated_time, done, assignee):
        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time,
            done, assignee
        )

        assert response.json == views.long_subject()

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             'text...',
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             date.today().strftime('%d.%m.%Y'),
             (date.today() + timedelta(days=1)).strftime('%d.%m.%Y'),
             1,
             OPTIONS_DONE_FOR_FORM[0],
             {'label': test_mm_user2['username'], 'value': test_mm_user2['id']},
             )
        ])
    def test_unregister_assignee(self, client, project, tracker, subject, description, status, priority, start_date,
                                 end_date, estimated_time, done, assignee):
        # UNREGISTERED ASSIGNEE USER
        os.environ.pop(test_mm_user2['username'])
        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time,
            done, assignee
        )
        os.environ[test_mm_user2['username']] = test_rm_user2.login
        assert response.json == views.unregister_mm_account(test_mm_user2['username'])

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             'text...',
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             '721878.1290.1290',  # INVALID DATA
             (date.today() + timedelta(days=1)).strftime('%d.%m.%Y'),
             1,
             OPTIONS_DONE_FOR_FORM[0],
             {'label': test_mm_user2['username'], 'value': test_mm_user2['id']},
             )
        ])
    def test_invalid_start_date(self, client, project, tracker, subject, description, status, priority, start_date,
                                end_date, estimated_time, done, assignee):
        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time, done, assignee
        )
        assert response.json == views.invalid_format_date()

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             'text...',
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             date.today().strftime('%d.%m.%Y'),
             '12.21.202',
             1,
             OPTIONS_DONE_FOR_FORM[0],
             None,
             ),
        ])
    def test_invalid_end_date(self, client, project, tracker, subject, description, status, priority, start_date,
                              end_date, estimated_time, done, assignee):
        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time, done, assignee
        )

        assert response.json == views.invalid_format_date()

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             'text...',
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             date.today().strftime('%d.%m.%Y'),
             (date.today() + timedelta(days=1)).strftime('%d.%m.%Y'),
             'estimated_time',  # INVALID DATE
             OPTIONS_DONE_FOR_FORM[0],
             None,
             ),
        ])
    def test_invalid_estimated_time(self, client, project, tracker, subject, description, status, priority, start_date,
                                    end_date, estimated_time, done, assignee):
        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time, done, assignee
        )

        assert response.json == views.invalid_estimated_time(estimated_time)

    @pytest.mark.parametrize(
        'project,tracker,subject,description,status,priority,start_date,end_date,estimated_time,done,assignee', [
            (test_project_rm,
             all_trackers()[0],
             'text...',
             'many text...',
             all_issue_statuses()[0],
             all_priorities()[0],
             date.today().strftime('%d.%m.%Y'),
             (date.today() + timedelta(days=1)).strftime('%d.%m.%Y'),
             1,  # INVALID DATE
             OPTIONS_DONE_FOR_FORM[0],
             None,
             ),
        ])
    def test_no_access_project(self, client, project, tracker, subject, description, status, priority, start_date,
                               end_date, estimated_time, done, assignee):
        global test_memberships1

        test_memberships1.delete()

        response = blocks.block_2(
            self.endpoint, client, project, tracker, subject, description, status, priority, start_date, end_date,
            estimated_time,
            done, assignee
        )

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json['type'] == 'error'


class TestNewTasks:
    endpoint = '/new_tasks'

    def test_success(self, client):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        response = client.post(self.endpoint, json=data)
        assert response.json['type'] == 'form'

    def test_unregister_account(self, client):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        os.environ.pop(test_mm_user1['username'])
        response = client.post(self.endpoint, json=data)
        os.environ[test_mm_user1['username']] = test_rm_user1.login

        assert response.json == views.unregister_mm_account(test_mm_user1['username'])

    def test_no_rm_user(self, client):
        global test_rm_user1, test_memberships1

        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        delete_redmine_user(test_rm_user1.id)

        response = client.post(self.endpoint, json=data)

        test_rm_user1 = create_redmine_user(
            login=envs.test_rm_username1,
            password=envs.test_rm_password1,
            firstname=envs.test_rm_first_name1,
            lastname=envs.test_rm_last_name1,
            mail=envs.test_rm_email1,
        )

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json == views.deactivate_or_not_exist_rm_account(test_rm_user1.login)

    def test_no_access_project(self, client):
        global test_memberships1

        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        test_memberships1.delete()

        response = client.post(self.endpoint, json=data)

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json['type'] == 'error'


class TestNewTask:
    endpoint = '/new_task'

    def test_success(self, client):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        response = client.post(self.endpoint, json=data)

        response.json['type'] = 'form'

    def test_unregister_account(self, client):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        os.environ.pop(test_mm_user1['username'])
        response = client.post(self.endpoint, json=data)
        os.environ[test_mm_user1['username']] = test_rm_user1.login

        assert response.json == views.unregister_mm_account(test_mm_user1['username'])

    def test_no_rm_user(self, client):
        global test_rm_user1, test_memberships1

        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        delete_redmine_user(test_rm_user1.id)

        response = client.post(self.endpoint, json=data)

        test_rm_user1 = create_redmine_user(
            login=envs.test_rm_username1,
            password=envs.test_rm_password1,
            firstname=envs.test_rm_first_name1,
            lastname=envs.test_rm_last_name1,
            mail=envs.test_rm_email1,
        )

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json == views.deactivate_or_not_exist_rm_account(test_rm_user1.login)

    def test_no_access_project(self, client):
        global test_memberships1

        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        test_memberships1.delete()

        response = client.post(self.endpoint, json=data)

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json['type'] == 'error'


class TestTasksForMe:
    endpoint = '/tasks_for_me'

    @pytest.mark.parametrize('rm_user, mm_user', (
            (test_rm_user1, test_mm_user1),
            (test_rm_user2, test_mm_user2)
    ))
    def test_success_no_tasks(self, client, rm_user, mm_user):
        data = {'context': {'acting_user': {'id': mm_user['id'], 'username': mm_user['username'],
                                            'first_name': mm_user['first_name'],
                                            'last_name': mm_user['last_name']}}}

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key).session() as redmine:
            [i.delete() for i in redmine.issue.all()]

        response = client.post(self.endpoint, json=data)

        full_name = create_full_name(mm_user['first_name'], mm_user['last_name'])
        author = choose_name(full_name, mm_user['username'])

        assert response.json == views.no_tasks_for_you(author)

    @pytest.mark.parametrize(
        'project_id,subject', [
            (test_project_rm.id, 'subject1'),
            (test_project_rm.identifier, 'asdasdasdasdasd'),
        ])
    def test_no_assignee(self, client, project_id, subject):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key).session() as redmine:
            issue = redmine.issue.create(project_id=project_id, subject=subject)

            response = client.post(self.endpoint, json=data)

            issue.delete()

        full_name = create_full_name(test_mm_user1['first_name'], test_mm_user1['last_name'])
        author = choose_name(full_name, test_mm_user1['username'])

        assert response.json == views.no_tasks_for_you(author)

    @pytest.mark.parametrize(
        'project_id,subject,mm_user', [
            ('testing', 'subject1', test_mm_user1),
            ('testing', 'asdasdasdasdasd', test_mm_user2),
        ])
    def test_success_assignee(self, client, project_id, subject, mm_user):
        data = {'context': {'acting_user': {'id': mm_user['id'], 'username': mm_user['username'],
                                            'first_name': mm_user['first_name'],
                                            'last_name': mm_user['last_name']}}}

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key).session() as redmine:
            rm_login = os.environ[mm_user['username']]
            assignee_id = redmine.user.filter(name=rm_login)[0].id
            issue = redmine.issue.create(project_id=project_id, subject=subject, assigned_to_id=assignee_id)

            response = client.post(self.endpoint, json=data)

            issue.delete()

        assert response.json['type'] == 'ok'

    def test_unregister_account(self, client):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        os.environ.pop(test_mm_user1['username'])
        response = client.post(self.endpoint, json=data)
        os.environ[test_mm_user1['username']] = test_rm_user1.login

        assert response.json == views.unregister_mm_account(test_mm_user1['username'])

    def test_no_rm_user(self, client):
        global test_rm_user1, test_memberships1

        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        delete_redmine_user(test_rm_user1.id)

        response = client.post(self.endpoint, json=data)

        test_rm_user1 = create_redmine_user(
            login=envs.test_rm_username1,
            password=envs.test_rm_password1,
            firstname=envs.test_rm_first_name1,
            lastname=envs.test_rm_last_name1,
            mail=envs.test_rm_email1,
        )

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json == views.deactivate_or_not_exist_rm_account(test_rm_user1.login)


class TestTasksByMe:
    endpoint = '/tasks_by_me'

    @pytest.mark.parametrize('rm_user, mm_user', (
            (test_rm_user1, test_mm_user1),
            (test_rm_user2, test_mm_user2),
    ))
    def test_no_tasks(self, client, rm_user, mm_user):
        data = {'context': {'acting_user': {'id': mm_user['id'], 'username': mm_user['username'],
                                            'first_name': mm_user['first_name'],
                                            'last_name': mm_user['last_name']}}}

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=rm_user.login).session() as redmine:
            [i.delete() for i in redmine.issue.all()]

        response = client.post(self.endpoint, json=data)

        full_name = create_full_name(mm_user['first_name'], mm_user['last_name'])
        author = choose_name(full_name, mm_user['username'])

        assert response.json == views.no_tasks_by_you(author)

    @pytest.mark.parametrize('rm_user, mm_user', (
            (test_rm_user1, test_mm_user1),
            (test_rm_user2, test_mm_user2),
    ))
    def test_success(self, client, rm_user, mm_user):
        data = {'context': {'acting_user': {'id': mm_user['id'], 'username': mm_user['username'],
                                            'first_name': mm_user['first_name'],
                                            'last_name': mm_user['last_name']}}}

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=rm_user.login).session() as redmine:
            issue = redmine.issue.create(project_id=test_project_rm.identifier, subject='subject')

            response = client.post(self.endpoint, json=data)

            issue.delete()

        assert response.json['type'] == 'ok'

    def test_unregister_account(self, client):
        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        os.environ.pop(test_mm_user1['username'])
        response = client.post(self.endpoint, json=data)
        os.environ[test_mm_user1['username']] = test_rm_user1.login

        assert response.json == views.unregister_mm_account(test_mm_user1['username'])

    def test_no_rm_user(self, client):
        global test_rm_user1, test_memberships1

        data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                            'first_name': test_mm_user1['first_name'],
                                            'last_name': test_mm_user1['last_name']}}}

        delete_redmine_user(test_rm_user1.id)

        response = client.post(self.endpoint, json=data)

        test_rm_user1 = create_redmine_user(
            login=envs.test_rm_username1,
            password=envs.test_rm_password1,
            firstname=envs.test_rm_first_name1,
            lastname=envs.test_rm_last_name1,
            mail=envs.test_rm_email1,
        )

        first_role = all_roles()[0]
        test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                       role_ids=[first_role.id])

        assert response.json == views.deactivate_or_not_exist_rm_account(test_rm_user1.login)


class TestEventHandler:

    @pytest.mark.parametrize('temp', (
            '#t{}',
            '  asdasd      #t{}    asda asdasd',
    ))
    def test_success(self, app, temp):
        with app.app_context():
            with Redmine(envs.redmine_url_external, key=envs.rm_admin_key,
                         impersonate=test_rm_user1.login).session() as redmine:
                issue = redmine.issue.create(project_id=test_project_rm.id, subject='subject...')

            new_post = blocks.block_3(temp.format(issue.id), 2)

        assert f'{envs.redmine_url_external}/issues/{issue.id}' in new_post['message']
        issue.delete()

    @pytest.mark.parametrize('temp', (
            '#t{}',
            '  asdasd      #t{}    asda asdasd',
    ))
    def test_unregister_account(self, app, temp):
        with app.app_context():
            with Redmine(envs.redmine_url_external, key=envs.rm_admin_key,
                         impersonate=test_rm_user1.login).session() as redmine:
                issue = redmine.issue.create(project_id=test_project_rm.id, subject='subject...')

            os.environ.pop(test_mm_user1['username'])

            new_post = blocks.block_3(temp.format(issue.id), 2)

            os.environ[test_mm_user1['username']] = test_rm_user1.login

        assert new_post['message'] == temp.format(issue.id)
        issue.delete()

    @pytest.mark.parametrize('temp', (
            '#t{}',
            '  asdasd      #t{}    asda asdasd',
    ))
    def test_no_rm_user(self, app, temp):
        global test_rm_user1, test_memberships1

        with app.app_context():
            with Redmine(envs.redmine_url_external, key=envs.rm_admin_key,
                         impersonate=test_rm_user1.login).session() as redmine:
                issue = redmine.issue.create(project_id=test_project_rm.id, subject='subject...')

            delete_redmine_user(test_rm_user1.id)

            new_post = blocks.block_3(temp.format(issue.id), 2)

            test_rm_user1 = create_redmine_user(
                login=envs.test_rm_username1,
                password=envs.test_rm_password1,
                firstname=envs.test_rm_first_name1,
                lastname=envs.test_rm_last_name1,
                mail=envs.test_rm_email1,
            )

            first_role = all_roles()[0]
            test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                           role_ids=[first_role.id])

        assert new_post['message'] == temp.format(issue.id)
        issue.delete()

    @pytest.mark.parametrize('temp', (
            '#t{}',
            '  asdasd      #t{}    asda asdasd',
    ))
    def test_no_access_task(self, app, temp):
        with app.app_context():
            global test_memberships1
            with Redmine(envs.redmine_url_external, key=envs.rm_admin_key).session() as redmine:
                issue = redmine.issue.create(project_id=test_project_rm.id, subject='subject...', is_private=True)

            test_memberships1.delete()

            new_post = blocks.block_3(temp.format(issue.id), 2)

            first_role = all_roles()[0]
            test_memberships1 = create_project_memberships(project_id='testing', user_id=test_rm_user1.id,
                                                           role_ids=[first_role.id])

        assert new_post['message'] == temp.format(issue.id)
        issue.delete()

