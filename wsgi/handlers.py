import json, re, logging, os, textwrap, requests
from datetime import datetime, date
from typing import Sequence
from posixpath import join
from redminelib import Redmine
from redminelib.exceptions import ResourceNotFoundError, ForbiddenError, ImpersonateError, AuthError

from converters import sing_plur_tasks
from wsgi import views
from wsgi.client_errors import ValidationDateError, ValidationTextError
from wsgi.constants import EXPAND_DICT
from wsgi.my_bot import send_ephemeral_post, bot
from wsgi.settings import envs


async def my_event_handler(message):
    load_message = json.loads(message)
    event = load_message.get('event', None)
    logging.info('my_event_handler: %s', event)
    if event == 'posted':
        data = load_message['data']
        post = json.loads(data['post'])

        get_msg = post['message']

        # if not correct pattern #t(id task) then return
        if re.search(r'#t(\d+)', get_msg) is None:
            return

        login_mm = data['sender_name'].removeprefix('@')
        user_id = post['user_id']
        post_id = post['id']
        channel_id = post['channel_id']
        new_msg = post['message']

        # check exist login_redmine in config
        login_rm = check_exist_login_redmine_in_config_file(login_mm)
        if type(login_rm) is dict:
            resp = send_ephemeral_post(user_id, channel_id, login_rm['text'])
            return

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=login_rm).session() as redmine:
            # check have redmine account in redmine
            rm_user = check_exist_account_and_token_in_redmine(redmine, login_mm)
            if type(rm_user) is dict:
                resp = send_ephemeral_post(user_id, channel_id, rm_user['text'])
                return
            for regex in re.finditer(r'#t(\d+)', get_msg):
                task_id = int(regex.group(1))
                try:
                    task = redmine.issue.get(task_id)
                except ResourceNotFoundError:
                    error_msg = f'# You have not task with ID `{task_id}`'
                    resp = send_ephemeral_post(user_id, channel_id, error_msg)
                    return
                except ForbiddenError:
                    error_msg = f'# You haven\'t access to task with ID {task_id}'
                    resp = send_ephemeral_post(user_id, channel_id, error_msg)
                    return
                else:
                    issue_link = f'{envs.redmine_url_external}/issues/{task_id}'
                    new_msg = re.sub(fr'(?<!\[){regex.group(0)}', issue_link, new_msg, 1)

        if new_msg != get_msg:
            resp = bot.posts.patch_post(post_id=post_id, options={'id': post_id, 'message': new_msg})


def static_path(filename: str) -> str:
    return f'{envs.app_url_external}/static/{filename}'


def parsing_input_text(text: str) -> list:
    result = []
    for i in re.split(r'\d+\. ', text):
        i = i.strip()
        if not i:
            continue
        subject = re.search(r'(.+) @', i, flags=re.DOTALL).group(1).strip()
        username = re.search(r' @(.+) \d+', i).group(1).removeprefix('@').strip()
        date_end = re.search(r' (\d+\.\d+\.\d+)', i).group(1).strip()

        date_to_datetime_object = datetime.strptime(date_end, '%d.%m.%Y').date()

        if date_to_datetime_object < date.today():
            raise ValidationDateError
        elif len(subject) > 255:
            raise ValidationTextError

        result.append((subject, username, date_to_datetime_object))
    return result


def validation_create_task_by_form(login_rm: str, context: dict, values: dict):
    login_mm = context['acting_user']['username']
    project_name, project_identifier = values['project']['label'], values['project']['value']
    tracker_id = int(values['tracker']['value'])
    subject = values['subject']
    description = values['description']
    status_id = int(values['status']['value'])
    priority_id = int(values['priority']['value'])
    assigned_to_id = None

    mattermost_assignee_login = values['assignee']

    if mattermost_assignee_login is not None:
        mattermost_assignee_login = mattermost_assignee_login['label']

    start_date = values['start_date']
    end_data = values['end_date']
    estimated_time = values['estimated_time']

    done_ratio = int(values['done']['value'])

    with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=login_rm).session() as redmine:
        # exist account and access token in redmine
        res = check_exist_account_and_token_in_redmine(redmine, login_rm)
        if type(res) is dict:
            return res

        # check including user in project
        res = check_included_user_in_project(redmine, project_identifier, login_rm)
        if type(res) is dict:
            return res

        # if mattermost_assignee_login is exists, then validate mattermost_assignee_login
        if mattermost_assignee_login:
            # check assignee redmine login in env file
            redmine_assignee_login = check_exist_login_redmine_in_config_file(mattermost_assignee_login)
            if type(redmine_assignee_login) is dict:
                return redmine_assignee_login

            with redmine.session(impersonate=redmine_assignee_login):
                # check assignee exist account and access token in redmine
                res = check_exist_account_and_token_in_redmine(redmine, redmine_assignee_login)
                if type(res) is dict:
                    return res

                # check including assignee user in project
                res = check_included_user_in_project(redmine, project_identifier, redmine_assignee_login)
                if type(res) is dict:
                    return res

                assigned_to_id = redmine.user.get('me').id

        # valid start date
        start_date_obj = check_format_date(start_date)
        if type(start_date_obj) is dict:
            return start_date_obj

        # valid end date
        end_date_obj = check_format_date(end_data)
        if type(end_date_obj) is dict:
            return end_date_obj

        if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
            return views.start_date_greater()

        # valid estimated time
        estimated_time_obj = check_estimated_time(estimated_time)
        if type(estimated_time_obj) is dict:
            return estimated_time_obj

        if len(subject) > 255:
            return views.long_subject()

        # after validation all fields, create new task

        task = redmine.issue.create(
            project_id=project_identifier,
            subject=subject,
            tracker_id=tracker_id,
            description=description,
            status_id=status_id,
            priority_id=priority_id,
            assigned_to_id=assigned_to_id,
            start_date=start_date_obj,
            due_date=end_date_obj,
            estimated_hours=estimated_time_obj,
            done_ratio=done_ratio,
        )

        return task


def check_estimated_time(estimated_time):
    if estimated_time is None:
        return estimated_time
    try:
        result = int(estimated_time)
    except ValueError:
        return views.invalid_estimated_time(estimated_time)
    else:
        return result


def check_format_date(string_date):
    if not string_date:
        return string_date
    try:
        date_obj = datetime.strptime(string_date, '%d.%m.%Y').date()
    except ValueError:
        return views.invalid_format_date()
    else:
        return date_obj


def check_exist_login_redmine_in_config_file(login_mm: str):
    login_rm = os.environ.get(login_mm, None)
    if not login_rm:
        return views.unregister_mm_account(login_mm)
    return login_rm


def check_exist_account_and_token_in_redmine(redmine, login_rm):
    try:
        redmine_user = redmine.user.get('current')
    except ImpersonateError:
        return views.deactivate_or_not_exist_rm_account(login_rm)
    except AuthError:
        return views.no_rm_access_token()
    else:
        return redmine_user


def check_included_user_in_project(redmine, project_identifier, login_rm):
    try:
        project = redmine.project.get(project_identifier)
    except ResourceNotFoundError:
        return views.no_rm_project(login_rm, project_identifier)
    except ForbiddenError:
        return views.no_access_project(login_rm, project_identifier)


def check_parsing_text(message: str):
    try:
        parsed_data = parsing_input_text(message)
    except AttributeError:
        return views.invalid_input_data()
    except ValueError:
        return views.invalid_format_date()
    except ValidationDateError:
        return views.start_date_greater()
    except ValidationTextError:
        return views.long_subject()
    else:
        return parsed_data


def generating_pretext(creator_tasks: str, tasks: Sequence):
    t = sing_plur_tasks(tasks)
    return f"**@{creator_tasks}** created {t} for {', '.join({'*@%s*' % i.login_mm for i in tasks})}\n"


def generating_table_tasks(tasks: Sequence):
    table = [
        '| ID | Project | Tracker | Status | Subject | Updated | Start date | End date | Priority | Author | Assignee |',
        '|-|-|-|-|-|-|-|-|-|-|-|',
    ]
    for t in tasks:
        issue_id = t.id
        project_id = t.project.id
        project_name = t.project.name
        tracker_name = t.tracker.name
        status_name = t.status.name
        subject = t.subject

        subject = textwrap.shorten(subject, 50)

        update_date = t.updated_on.strftime('%d.%m.%Y')
        dt_start = t.start_date.strftime('%d.%m.%Y') if t.start_date else None
        dt_end = t.due_date.strftime('%d.%m.%Y') if t.due_date else None
        priority_name = t.priority.name

        author = t.author.name
        author_id = t.author.id

        if hasattr(t, 'assigned_to'):
            assignee = t.assigned_to.name
            assigned_id = t.assigned_to.id
            assignee_line = f' [{assignee}]({envs.redmine_url_external}/users/{assigned_id}) |\n'
        else:
            assignee_line = 'None'

        line = f'| [{issue_id}]({envs.redmine_url_external}/issues/{issue_id}) |' \
               f' [{project_name}]({envs.redmine_url_external}/projects/{project_id}) |' \
               f' {tracker_name} |' \
               f' {status_name} |' \
               f' [{subject}]({envs.redmine_url_external}/issues/{issue_id}) |' \
               f' {update_date} |' \
               f' {dt_start} |' \
               f' {dt_end} |' \
               f' {priority_name} |' \
               f' [{author}]({envs.redmine_url_external}/users/{author_id}) |' \
               f' {assignee_line} |'
        table.append(line)

    return '\n'.join(table)


def generate_projects_for_form(redmine):
    result = [{"label": p.name, "value": p.identifier} for p in redmine.project.all()]
    return result


def generate_trackers_for_form(redmine):
    result = [{"label": t.name, "value": f'{t.id}'} for t in redmine.tracker.all()]
    return result


def generate_priorities_for_form(redmine):
    result = [{"label": p.name, "value": f'{p.id}'}
              for p in redmine.enumeration.filter(resource='issue_priorities')]
    return result


def generate_statuses_for_form(redmine):
    result = [{"label": s.name, "value": f"{s.id}"} for s in redmine.issue_status.all() if s.is_closed is False]
    return result


def create_direct_channel(context: dict):
    bot_user_id = context['bot_user_id']
    user_id = context['acting_user']['id']
    data = [bot_user_id, user_id]
    response_dict = bot.channels.create_direct_channel(options=data)
    channel_id = response_dict['id']
    return channel_id


def subscribe_team_join(context: dict) -> None:
    site_url = envs.mattermost_url_external
    bot_access_token = context['bot_access_token']

    url = join(site_url, 'plugins/com.mattermost.apps/api/v1/subscribe')
    logging.info(f'Subscribing to team_join for {site_url}...')
    headers = {'Authorization': f'BEARER {bot_access_token}'}
    body = {
        'subject': 'bot_joined_team',
        'call': {
            'path': '/bot_joined_team',
            'expand': EXPAND_DICT,
        },
    }
    res = requests.post(url, headers=headers, json=body)
    if res.status_code != 200:
        logging.error(f'Could not subscribe to team_join event for {site_url}')
    else:
        logging.debug(f'subscribed to team_join event for {site_url}')
