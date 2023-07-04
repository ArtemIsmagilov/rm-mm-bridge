import logging, requests, datetime, re, json
from threading import Thread
from posixpath import join
from flask import Flask, request, url_for
from redminelib import Redmine
from redminelib.exceptions import ImpersonateError, AuthError, ResourceNotFoundError, ForbiddenError
from mattermostdriver import Driver
from mattermostdriver.exceptions import NoAccessTokenProvided, InvalidOrMissingParameters

from my_config import *
from my_constants import *
from ticket_user import TicketUser
from client_errors import ValidationDateError


def static_path(filename):
    return f'{app_url}/static/{filename}'


def check_correctness_access_token_for_app(bot):
    try:
        bot.login()
    except InvalidOrMissingParameters:
        return {'type': 'error', 'text': '## App haven\'t access token.'}
    except NoAccessTokenProvided:
        return {'type': 'error', 'text': '## App access token is not correct or is expired.'}


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='%Y-%m-%d:%H:%M:%S')

app = Flask(__name__, static_url_path='/static', static_folder='./static')

bot = Driver({
    'url': MM_HOST,
    'token': MM_APP_TOKEN,
    'scheme': MM_PROTOCOL,
    'port': int(MM_PORT),
    'basepath': '/api/v4',
    'verify': True,  # Or /path/to/file.pem
})

if MM_APP_TOKEN:
    res_valid = check_correctness_access_token_for_app(bot)
    if type(res_valid) is dict:
        logging.error('REDMINE_MATTERMOST_BRIDGE_APP_TOKEN ERROR: %s', res_valid)
        exit(1)


async def my_event_handler(message):
    load_message = json.loads(message)
    event = load_message.get('event', None)
    if event == 'posted':
        data = load_message['data']
        post = json.loads(data['post'])

        get_msg = post['message']

        # if not correct pattern #t(id ticket) then return
        if re.search('#t(\d+)', get_msg) is None:
            return

        mattermost_login = data['sender_name'].removeprefix('@')
        user_id = post['user_id']
        post_id = post['id']
        channel_id = post['channel_id']
        new_msg = post['message']

        # check exist login_redmine in config
        login_in_redmine = check_exist_login_redmine_in_config_file(mattermost_login)
        if type(login_in_redmine) is dict:
            resp = send_ephemeral_post(user_id, channel_id, login_in_redmine['message'])
            return

        with Redmine(redmine_url, key=ADMIN_REDMINE_KEY_API,
                     impersonate=login_in_redmine).session() as redmine:
            # check correct connection in redmine
            res = check_exist_account_and_token_in_redmine(redmine, mattermost_login, login_in_redmine)
            if type(res) is dict:
                error_msg = res['message']
                resp = send_ephemeral_post(user_id, channel_id, error_msg)
                return
            for regex in re.finditer('#t(\d+)', get_msg):
                ticket_id = int(regex.group(1))
                try:
                    ticket = redmine.issue.get(ticket_id)
                except ResourceNotFoundError:
                    error_msg = f'##### You have not ticket with ID `{ticket_id}`'
                    resp = send_ephemeral_post(user_id, channel_id, error_msg)
                    return
                except ForbiddenError:
                    error_msg = f'##### You haven\'t access to ticket with ID {ticket_id}'
                    resp = send_ephemeral_post(user_id, channel_id, error_msg)
                    return
                else:
                    new_msg = re.sub(fr'(?<!\[){regex.group(0)}',
                                     f'[#t{ticket_id}]({redmine_url}/issues/{ticket_id})', new_msg, 1)

        if new_msg != get_msg:
            resp = bot.posts.patch_post(post_id=post_id, options={
                'id': post_id,
                'message': new_msg,
            })


def parsing_input_text(text):
    result = []
    for i in text.split('\n'):
        if not i:
            continue
        task = re.search(r'^\d+\. (.+) @', i).group(1).strip()
        username = re.search(r' @(.+) \d+', i).group(1).removeprefix('@').strip()
        date_end = re.search(r' (\d+.+)$', i).group(1).strip()
        date_to_datetime_object = datetime.datetime.strptime(date_end, '%d.%m.%y').date()
        if date_to_datetime_object < datetime.date.today():
            raise ValidationDateError
        result.append(TicketUser(task, username, date_to_datetime_object))
    return result


def send_ephemeral_post(user_id, channel_id, msg):
    resp = bot.posts.create_ephemeral_post(options={
        'user_id': user_id,
        'post': {
            'channel_id': channel_id,
            'message': msg,
        }
    })
    return resp


def validation_create_ticket_by_form(context, values):
    mattermost_login = context['acting_user']['username']
    project_name, project_identifier = values['projects']['label'], values['projects']['value']
    tracker_id = int(values['trackers']['value'])
    subject = values['subject']
    description = values['description']
    status_id = int(values['status']['value'])
    priority_id = int(values['priority']['value'])
    assigned_to_id = None

    mattermost_assignee_login = values['mattermost_user']

    if mattermost_assignee_login is not None:
        mattermost_assignee_login = values['mattermost_user']['label']

    start_date = values['start_date']
    end_data = values['end_date']
    estimated_time = values['estimated_time']

    done_ratio = int(values['done']['value'])

    # exist redmine login  in env file
    redmine_login = check_exist_login_redmine_in_config_file(mattermost_login)
    if type(redmine_login) is dict:
        return redmine_login

    with Redmine(redmine_url, key=ADMIN_REDMINE_KEY_API,
                 impersonate=redmine_login).session() as redmine:
        # exist account and access token in redmine
        res = check_exist_account_and_token_in_redmine(redmine, mattermost_login, redmine_login)
        if type(res) is dict:
            return res

        # check including user in project
        res = check_included_user_in_project(redmine, project_identifier, mattermost_login)
        if type(res) is dict:
            return res

        # if mattermost_assignee_login is exists, then validate mattermost_assignee_login
        if mattermost_assignee_login:
            # check assignee redmine login in env file
            redmine_assignee_login = check_exist_login_redmine_in_config_file(mattermost_assignee_login)
            if type(redmine_assignee_login) is dict:
                return redmine_assignee_login

            # check assignee exist account and access token in redmine

            with redmine.session(impersonate=redmine_assignee_login):

                res = check_exist_account_and_token_in_redmine(redmine, mattermost_assignee_login,
                                                               redmine_assignee_login)
                if type(res) is dict:
                    return res

                # check including assignee user in project
                res = check_included_user_in_project(redmine, project_identifier, mattermost_assignee_login)
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
            return {'type': 'error', 'text': '#### Completion date must be later than the start date'}

        # valid estimated time
        estimated_time_obj = check_estimated_time(estimated_time)
        if type(estimated_time_obj) is dict:
            return estimated_time_obj

        # after validation all fields, create new ticket

        ticket = redmine.issue.create(
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

        return ticket


def check_estimated_time(estimated_time):
    if estimated_time is None:
        return estimated_time
    if re.match(r'^(\d+)$', estimated_time) is None:
        return {'type': 'error', 'text': f'Invalid format for estimated time - {estimated_time}'}
    return int(estimated_time)


def check_format_date(string_date):
    if not string_date:
        return string_date
    try:
        date_obj = datetime.datetime.strptime(string_date, '%d.%m.%y').date()
    except ValueError:
        return {'type': 'error', 'text': f'### Invalid format date - {string_date}'}
    else:
        return date_obj


def check_exist_login_redmine_in_config_file(login_in_mattermost):
    login_in_redmine = os.environ.get(login_in_mattermost, None)
    if not login_in_redmine:
        return {'type': 'error',
                'text': f'### Account with login {login_in_mattermost} not added in config file for integration with redmine'}
    return login_in_redmine


def check_exist_account_and_token_in_redmine(redmine, mattermost_login, redmine_login):
    try:
        redmine_user = redmine.user.get('current')
        return redmine_user
    except ImpersonateError:
        return {'type': 'error',
                'text': f'### Account {mattermost_login}({redmine_login}) doesn\'t exist in redmine or deactivated.'}
    except AuthError:
        return {'type': 'error', 'text': '### Your app haven\'t redmine access token.'}


def check_included_user_in_project(redmine, project_identifier, mattermost_login):
    try:
        project = redmine.project.get(project_identifier)
    except ResourceNotFoundError:
        return {'type': 'error',
                'text': f'## User with login \'{mattermost_login}\' haven\'t project with identifier `{project_identifier}`.'}
    except ForbiddenError:
        return {'type': 'error',
                'text': f'## User with login \'{mattermost_login}\' does not have access to the project with identifier `{project_identifier}`.'}


def check_parsing_text(message):
    try:
        parsed_data = parsing_input_text(message)
    except AttributeError:
        return {'type': 'error', 'text': '## Invalid input data. Look for example.'}
    except ValueError:
        return {'type': 'error', 'text': '## Invalid format end date. Look for example [day.month.year] - 10.8.23.'}
    except ValidationDateError:
        return {'type': 'error', 'text': '## Due date must be greater than start date'}
    else:
        return parsed_data


def generating_pretext(creator_tickets, tickets, assigned=True):
    if not assigned:
        return f"**@{creator_tickets}** created one ticket by form"
    return f"**@{creator_tickets}** created ticket(s) for {', '.join('*@%s*' % i.assigned_to for i in tickets)}"


def generating_table_tickets_for_me(tickets):
    table = '| ID | Project | Tracker | Status | Subject | Updated | End date | Priority | Author |\n' \
            '|----|---------|---------|--------|---------|---------|:--------:|----------|--------|\n'

    for t in tickets:
        issue_id = t.id
        project_id = t.project.id
        project_name = t.project.name
        tracker_name = t.tracker.name
        status_name = t.status.name
        subject = t.subject

        if len(subject) > 30: subject = subject[:30] + '...'

        update_date = t.updated_on.strftime('%d.%m.%y')
        date_end = t.due_date.strftime('%d.%m.%y') if t.due_date else None
        priority_name = t.priority.name
        author = t.author.name
        author_id = t.author.id
        line = f'| [{issue_id}]({redmine_url}/issues/{issue_id}) |' \
               f' [{project_name}]({redmine_url}/projects/{project_id}) |' \
               f' {tracker_name} |' \
               f' {status_name} |' \
               f' [{subject}]({redmine_url}/issues/{issue_id}) |' \
               f' {update_date} |' \
               f' {date_end} |' \
               f' {priority_name} |' \
               f' [{author}]({redmine_url}/users/{author_id}) |\n'
        table += line

    return table


def generating_table_my_tickets(tickets):
    table = '| ID | Project | Tracker | Status | Subject | Updated | End date | Priority | Assignee |\n' \
            '|----|---------|---------|--------|---------|---------|:--------:|----------|----------|\n'
    for t in tickets:
        issue_id = t.id
        project_id = t.project.id
        project_name = t.project.name
        tracker_name = t.tracker.name
        status_name = t.status.name
        subject = t.subject

        if len(subject) > 30: subject = subject[:30] + '...'

        update_date = t.updated_on.strftime('%d.%m.%y')
        date_end = t.due_date.strftime('%d.%m.%y') if t.due_date else None
        priority_name = t.priority.name

        if hasattr(t, 'assigned_to'):
            assignee = t.assigned_to.name
            assigned_id = t.assigned_to.id
            assignee_line = f' [{assignee}]({redmine_url}/users/{assigned_id}) |\n'
        else:
            assignee_line = 'None \n'
        line = f'| [{issue_id}]({redmine_url}/issues/{issue_id}) |' \
               f' [{project_name}]({redmine_url}/projects/{project_id}) |' \
               f' {tracker_name} |' \
               f' {status_name} |' \
               f' [{subject}]({redmine_url}/issues/{issue_id}) |' \
               f' {update_date} |' \
               f' {date_end} |' \
               f' {priority_name} |' \
               f' {assignee_line}'
        table += line

    return table


def generate_projects_for_form(redmine):
    result = [{"label": p.name, "value": p.identifier} for p in redmine.project.all()]
    return result


def generate_trackers_for_form(redmine):
    result = [{"label": t.name, "value": f'{t.id}'} for t in redmine.tracker.all()]
    return result


def generate_priorities_for_form(redmine):
    result = [{"label": p.name, "value": f'{p.id}'} for p in redmine.enumeration.filter(resource='issue_priorities')]
    return result


def generate_statuses_for_form(redmine):
    result = [{"label": s.name, "value": f"{s.id}"} for s in redmine.issue_status.all() if s.is_closed is False]
    return result


def _subscribe_team_join(context: dict) -> None:
    site_url = context['mattermost_site_url']
    bot_access_token = context['bot_access_token']
    url = join(site_url, 'plugins/com.mattermost.apps/api/v1/subscribe')
    logging.info(f'Subscribing to team_join for {site_url}')
    headers = {'Authorization': f'BEARER {bot_access_token}'}
    body = {
        'subject': 'bot_joined_team',
        'call': {
            'path': '/bot_joined_team',
            'expand': {
                'app': 'all',
                'team': 'all'
            }
        },
    }
    res = requests.post(url, headers=headers, json=body)
    if res.status_code != 200:
        logging.error(f'Could not subscribe to team_join event for {site_url}')
    else:
        logging.debug(f'subscribed to team_join event for {site_url}')


@app.route('/manifest.json')
def manifest() -> dict:
    return {
        'app_id': 'redmine-mattermost-bridge',
        'display_name': 'Redmine',
        'homepage_url': 'https://github.com/mattermost/mattermost-app-examples/tree/master/python/hello-world',
        'app_type': 'http',
        'icon': 'redmine.png',
        'requested_permissions': ['act_as_bot', 'act_as_user', 'remote_oauth2', 'remote_webhooks'],
        'on_install': {
            'path': '/install',
            'expand': EXPAND_DICT,
        },
        'bindings': {
            'path': '/bindings',
        },
        'requested_locations': [
            '/command',
        ],
        'root_url': app_url,
        "http": {
            "root_url": app_url,
        },

    }


@app.route('/bindings', methods=['GET', 'POST'])
def on_bindings() -> dict:
    return {
        'type': 'ok',
        'data': [
            {
                # binding for a command
                'location': '/command',
                'bindings': [
                    {  # command with embedded form
                        'description': 'Integration with Redmine',
                        'hint': '[app_info|create_ticket_by_form|create_tickets|tickets_for_me]',
                        # this will be the command displayed to user as /second-command
                        'label': 'integration_with_redmine',
                        'icon': static_path('redmine.png'),
                        'bindings': [
                            {  # app_info
                                'description': 'show info about commands app',
                                'hint': '[This is command with info about app: redmine-mattermost-bridge]',
                                # this will be the command displayed to user as /first-command
                                'label': 'app_info',
                                'icon': static_path('redmine.png'),
                                'submit': {
                                    'path': '/app_info',
                                    'expand': EXPAND_DICT,
                                },
                            },
                            {  # create_ticket_by_form
                                'description': 'create ticket by form',
                                'hint': '[You can create ticket by form with some fields]',
                                'label': 'create_ticket_by_form',
                                'icon': static_path('redmine.png'),
                                'submit': {
                                    'path': '/create_ticket_by_form',
                                    'expand': EXPAND_DICT,
                                },
                            },

                            {  # create_tickets
                                'description': 'create issues',
                                'hint': '[You can create some issues in one form]',
                                'label': 'create_tickets',
                                'icon': static_path('redmine.png'),
                                'submit': {
                                    'path': '/create_tickets',
                                    'expand': EXPAND_DICT,
                                },
                            },

                            {  # tickets_for_me
                                'description': 'tickets for me',
                                'hint': '[You can look ticket for you]',
                                'label': 'tickets_for_me',
                                'icon': static_path('redmine.png'),
                                'submit': {
                                    'path': '/tickets_for_me',
                                    'expand': EXPAND_DICT,
                                },
                            },
                            {  # my_tickets
                                'description': 'my tickets',
                                'hint': '[You can look your tickets]',
                                'label': 'my_tickets',
                                'icon': static_path('redmine.png'),
                                'submit': {
                                    'path': '/my_tickets',
                                    'expand': EXPAND_DICT,
                                },
                            },
                        ],
                    }
                    ,
                ]
            }
        ]
    }


@app.route('/ping', methods=['POST'])
def on_ping() -> dict:
    logging.debug('ping...')
    return {'type': 'ok'}


@app.route('/install', methods=['GET', 'POST'])
def on_install() -> dict:
    _subscribe_team_join(request.json['context'])
    return {'type': 'ok', 'data': []}


@app.route('/bot_joined_team', methods=['GET', 'POST'])
def on_bot_joined_team() -> dict:
    context = request.json['context']
    logging.info(
        f'bot_joined_team event received for site:{context["mattermost_site_url"]}, '
        f'team:{context["team"]["id"]} name:{context["team"]["name"]} '
        f'{request.args} {request.data}'
    )
    # Here one can subscribe to channel_joined/left events as these required team_id now to be subscribed,
    # hence use the team_id received in the event and make a call for subscribing to channel_joined/left events.
    # Also supply {'team_id': team_id} in the request body of the subscription
    # {
    #    'subject': 'bot_joined_team',
    #    'call': {
    #        'path': '/bot_joined_team',
    #         'expand': {
    #             'app': 'all',
    #             'team': 'all'
    #         }
    #    },
    #    'team_id': 'team_id'   # get this team_id when bot_joined_team event occurs
    # }
    return {'type': 'ok', 'data': []}


@app.route('/app_info', methods=['POST'])
def app_info_handler():
    context = request.json['context']
    login_in_mattermost = context['acting_user']['username']
    md = f""" 
### Hi, {login_in_mattermost}. I can 
* automatically create multiple tickets
* view tickets created by you
* view tasks that you have been assigned.

---

| commands        | Description                |
|-----------------|----------------------------|
| /app_info       | help info about app        |
| /create_tickets | create one or some tickets |
| /tickets_for_me | look tickets for me        |
| /my_tickets     | look my tickets            |"""
    return {'type': 'ok', 'text': md}


@app.route('/my_tickets', methods=['POST'])
def my_tickets_handler():
    context = request.json['context']
    login_in_mattermost = context['acting_user']['username']

    # validation1 [have user in .env file]
    login_in_redmine = check_exist_login_redmine_in_config_file(login_in_mattermost)
    if type(login_in_redmine) is dict:
        return login_in_redmine

    with Redmine(redmine_url, key=ADMIN_REDMINE_KEY_API,
                 impersonate=login_in_redmine).session() as redmine:

        # validation2 [have account and token for REST API]
        res = check_exist_account_and_token_in_redmine(redmine, login_in_mattermost, login_in_redmine)
        if type(res) is dict:
            return res

        my_tickets = redmine.issue.filter(author_id='me', status_id='open', sort='updated_on:desc')
        if not my_tickets:
            return {'type': 'ok', 'text': 'You haven\'t created issues yet'}

        bot_user_id = context['bot_user_id']
        user_id = context['acting_user']['id']
        data = [bot_user_id, user_id]
        response_dict = bot.channels.create_direct_message_channel(options=data)
        channel_id = response_dict['id']
        url_reported_issues = f'{redmine_url}/issues?c%5B%5D=project&c%5B%5D=tracker&c%5B%5D=status&c%5B%5D=subject&f%5B%5D=status_id&f%5B%5D=author_id&f%5B%5D=project.status&op%5Bauthor_id%5D=%3D&op%5Bproject.status%5D=%3D&op%5Bstatus_id%5D=o&set_filter=1&sort=updated_on%3Adesc&v%5Bauthor_id%5D%5B%5D=me&v%5Bproject.status%5D%5B%5D=1&v%5Bstatus_id%5D%5B%5D='

        resp = bot.posts.create_post(options={
            'channel_id': channel_id,
            'message': f'# Ok, {login_in_mattermost}. I look your tickets.',
            "props": {
                "attachments": [
                    {
                        "fallback": "test",
                        "pretext": f'@{login_in_mattermost} tickets',
                        "text": generating_table_my_tickets(my_tickets),
                        "title": 'Reported issues',
                        "title_link": url_reported_issues,
                    }
                ]}
        })
        return {'type': 'ok', }


@app.route('/tickets_for_me', methods=['POST'])
def tickets_for_me_handler():
    context = request.json['context']
    login_in_mattermost = context['acting_user']['username']

    # validation1 [have user in .env file]
    login_in_redmine = check_exist_login_redmine_in_config_file(login_in_mattermost)
    if type(login_in_redmine) is dict:
        return login_in_redmine

    with Redmine(redmine_url, key=ADMIN_REDMINE_KEY_API,
                 impersonate=login_in_redmine).session() as redmine:

        # validation2 [have account and token for REST API]
        res = check_exist_account_and_token_in_redmine(redmine, login_in_mattermost, login_in_redmine)
        if type(res) is dict:
            return res

        issues_for_me = redmine.issue.filter(assigned_to_id='me', status_id='open', sort='updated_on:desc')
        if not issues_for_me:
            return {'type': 'ok', 'text': 'There are no tasks for you yet.'}

    bot_user_id = context['bot_user_id']
    user_id = context['acting_user']['id']
    data = [bot_user_id, user_id]
    response_dict = bot.channels.create_direct_message_channel(options=data)
    channel_id = response_dict['id']
    url_issues_assigned_to_me = f'{redmine_url}/issues?c%5B%5D=project&c%5B%5D=tracker&c%5B%5D=status&c%5B%5D=subject&c%5B%5D=author&f%5B%5D=status_id&f%5B%5D=assigned_to_id&f%5B%5D=project.status&op%5Bassigned_to_id%5D=%3D&op%5Bproject.status%5D=%3D&op%5Bstatus_id%5D=o&set_filter=1&sort=author%2Cpriority%3Adesc%2Cupdated_on%3Adesc&v%5Bassigned_to_id%5D%5B%5D=me&v%5Bproject.status%5D%5B%5D=1&v%5Bstatus_id%5D%5B%5D='
    resp = bot.posts.create_post(options={
        'channel_id': channel_id,
        'message': f'# Ok, {login_in_mattermost}. I look tickets for you.',
        "props": {
            "attachments": [
                {
                    "fallback": "test",
                    "pretext": f'Tickets for @{login_in_mattermost}',
                    "text": generating_table_tickets_for_me(issues_for_me),
                    "title": 'Issues assigned to me',
                    "title_link": url_issues_assigned_to_me}
            ]}
    })
    return {'type': 'ok'}


@app.route('/create_ticket_by_form', methods=['POST'])
def create_ticket_by_form_handler():
    login_in_mattermost = request.json['context']['acting_user']['username']

    # validation1 [have user in .env file]
    login_in_redmine = check_exist_login_redmine_in_config_file(login_in_mattermost)
    if type(login_in_redmine) is dict:
        return login_in_redmine

    with Redmine(redmine_url, key=ADMIN_REDMINE_KEY_API,
                 impersonate=login_in_redmine).session() as redmine:

        # validation2 [have account and token for REST API]
        res = check_exist_account_and_token_in_redmine(redmine, login_in_mattermost, login_in_redmine)
        if type(res) is dict:
            return res

        options_projects_in_redmine = generate_projects_for_form(redmine)

        if not options_projects_in_redmine:
            return {"type": 'ok', "text": "# You have not projects in redmine"}

        today = datetime.date.today().strftime('%d.%m.%y')
        options_trackers_in_redmine = generate_trackers_for_form(redmine)
        options_priorities_in_redmine = generate_priorities_for_form(redmine)
        options_statuses_in_redmine = generate_statuses_for_form(redmine)

    return {'type': 'form', "form": {
        "source": {
            "path": "/create_ticket_by_form"
        },
        "title": "Create ticket by form.",
        "icon": static_path('redmine.png'),
        "submit": {
            "path": "/create_ticket_by_form_submit",
            "expand": EXPAND_DICT,
        },
        "fields": [
            {  # projects
                "name": "projects",
                "type": "static_select",
                'is_required': True,
                'description': 'Select redmine project from list',
                "label": "Projects",
                'hint': 'name project',
                "options": options_projects_in_redmine,
            },
            {  # trackers
                "name": "trackers",
                "type": "static_select",
                'is_required': True,
                'value': options_trackers_in_redmine[0],
                'description': 'Select tracker',
                "label": "Trackers",
                'hint': 'name tracker',
                "options": options_trackers_in_redmine,
            },
            {  # subject
                "name": "subject",
                "type": "text",
                'is_required': True,
                'description': 'Write short text for assignee',
                "label": "Subject",
                'hint': 'Exist current task...',
            },
            {  # description
                'name': 'description',
                'type': 'text',
                'subtype': 'textarea',
                'description': 'Describe the task in detail',
                'label': 'Description',
                'hint': 'Some text...',
            },
            {  # status
                "name": "status",
                "type": "static_select",
                'is_required': True,
                'value': options_statuses_in_redmine[0],
                'description': 'Select status',
                "label": "Status",
                'hint': 'name status',
                "options": options_statuses_in_redmine,
            },
            {  # priority
                "name": "priority",
                "type": "static_select",
                'is_required': True,
                'value': options_priorities_in_redmine[1],
                'description': 'Select priority',
                "label": "Priority",
                'hint': 'name priority',
                "options": options_priorities_in_redmine,
            },
            {  # assignee
                "name": "mattermost_user",
                "type": "user",
                'description': 'Select mattermost user',
                "label": "Assignee",
                'hint': 'login in mattermost',
            },
            {  # start_date
                "name": "start_date",
                "type": "text",
                'value': today,
                'description': 'By default today or write need date',
                "label": "Start_date",
                'hint': 'day.month.year(03.03.23)',
            },
            {  # end_date
                "name": "end_date",
                "type": "text",
                'description': 'By default None or write need date. End_date must > today',
                "label": "End_date",
                'hint': 'day.month.year(03.03.23)',
            },
            {
                # estimated time
                "name": "estimated_time",
                "type": "text",
                'description': 'Write need time for ticket',
                "label": "Estimated_time",
                'hint': 'only hours(natural number)',
            },
            {  # done
                "name": "done",
                "type": "static_select",
                'is_required': True,
                'value': OPTIONS_DONE_FOR_FORM[0],
                'description': 'Select value done(%)',
                "label": "Done",
                'hint': 'value done',
                "options": OPTIONS_DONE_FOR_FORM,

            }

        ]
    }
            }


@app.route('/create_tickets', methods=['POST'])
def create_tickets_handler():
    login_in_mattermost = request.json['context']['acting_user']['username']

    # validation1 [have user in .env file]
    login_in_redmine = check_exist_login_redmine_in_config_file(login_in_mattermost)
    if type(login_in_redmine) is dict:
        return login_in_redmine

    with Redmine(redmine_url, key=ADMIN_REDMINE_KEY_API,
                 impersonate=login_in_redmine).session() as redmine:

        # validation2 [have account and token for REST API]
        res = check_exist_account_and_token_in_redmine(redmine, login_in_mattermost, login_in_redmine)
        if type(res) is dict:
            return res

        options_projects_in_redmine = generate_projects_for_form(redmine)

        if not options_projects_in_redmine:
            return {"type": 'ok', "text": "# You have not projects in redmine"}

    return {'type': 'form', "form": {
        "source": {
            "path": "/create_tickets"
        },
        "title": "Create issues form.",
        "icon": static_path('redmine.png'),
        "submit": {
            "path": "/create_tickets_submit",
            "expand": EXPAND_DICT,
        },
        "fields": [
            {
                "name": "option",
                "type": "static_select",
                "label": "Projects",
                "options": options_projects_in_redmine,
                'is_required': True,
                'description': 'Select redmine project from list',
                'hint': 'name project',
                'position': 1,
            },
            {
                "name": "message",
                "type": "text",
                "label": "Issues",
                'is_required': True,
                'description': 'You need write one or some lines task, user and deadline date.',
                'hint': '1. Купить колбасы @vasiliy.fedorov 09.05.23\n2. Написать симфонию @artem.ismagilov 10.05.23\n'
                        '[number issue]. [some text] @[username] [day.month.year]\n',
                'position': 2,
                'subtype': 'textarea',
            },

        ]
    }
            }


@app.route('/create_ticket_by_form_submit', methods=['POST'])
def create_ticket_by_from_submit_handler():
    logging.info(request.json)
    values = request.json["values"]
    context = request.json["context"]
    login_in_mattermost = context['acting_user']['username']

    ticket = validation_create_ticket_by_form(context, values)

    if type(ticket) is dict:
        return ticket

    bot_user_id = context['bot_user_id']
    user_id = context['acting_user']['id']
    data = [bot_user_id, user_id]
    response_dict = bot.channels.create_direct_message_channel(options=data)
    channel_id = response_dict['id']

    bot.posts.create_post(options={
        'channel_id': channel_id,
        'message': f'# Ok, {login_in_mattermost}. I create ticket in redmine by form',
        "props": {
            "attachments": [
                {
                    "fallback": "test",
                    "pretext": generating_pretext(login_in_mattermost, [ticket], hasattr(ticket, 'assigned_to')),
                    "text": generating_table_my_tickets([ticket]),
                }
            ]}
    })

    return {'type': 'ok'}


@app.route('/create_tickets_submit', methods=['POST'])
def create_tickets_submit_handler():
    values = request.json["values"]
    context = request.json["context"]
    message, project_identifier = values['message'], values['option']['value']
    login_in_mattermost = context['acting_user']['username']
    date_today = datetime.date.today()

    # validation1 [have user in .env file]
    login_in_redmine = check_exist_login_redmine_in_config_file(login_in_mattermost)
    if type(login_in_redmine) is dict:
        return login_in_redmine

    parsed_data = check_parsing_text(message)
    if type(parsed_data) is dict:
        return parsed_data

    redmine_users = []
    with Redmine(redmine_url, key=ADMIN_REDMINE_KEY_API).session() as redmine:
        for u in parsed_data:

            # validation1 [have user in .env file]
            login_in_redmine_next_user = check_exist_login_redmine_in_config_file(u.login)
            if type(login_in_redmine_next_user) is dict:
                return login_in_redmine_next_user

            with redmine.session(impersonate=login_in_redmine_next_user):

                # validation2 [have account and token for REST API]
                redmine_user = check_exist_account_and_token_in_redmine(redmine, u.login, login_in_redmine_next_user)
                if type(redmine_user) is dict:
                    return redmine_user

                # validation3 [user isn't included in this project]
                res = check_included_user_in_project(redmine, project_identifier, u.login)
                if type(res) is dict:
                    return res

                redmine_user.created_task = u.task
                redmine_user.created_date_end = u.date_end
                redmine_users.append(redmine_user)
        tickets = []
        with redmine.session(impersonate=login_in_redmine):
            for t in redmine_users:
                t = redmine.issue.create(
                    project_id=project_identifier,
                    subject=t.created_task,
                    assigned_to_id=t.id,
                    start_date=date_today,
                    due_date=t.created_date_end,
                )
                tickets.append(t)

    bot_user_id = context['bot_user_id']
    user_id = context['acting_user']['id']
    data = [bot_user_id, user_id]
    response_dict = bot.channels.create_direct_message_channel(options=data)
    channel_id = response_dict['id']

    bot.posts.create_post(options={
        'channel_id': channel_id,
        'message': f'# Ok, {login_in_mattermost}. I create your ticket(s) in redmine.',
        "props": {
            "attachments": [
                {
                    "fallback": "test",
                    "pretext": generating_pretext(login_in_mattermost, tickets),
                    "text": generating_table_my_tickets(tickets),
                }
            ]}
    })

    return {'type': 'ok'}


def run_app():
    app.run(
        debug=True,
        host=APP_HOST_INTERNAl,
        port=int(APP_PORT),
        use_reloader=False,
    )


def main():
    Thread(target=run_app).start()
    if MM_APP_TOKEN:
        bot.init_websocket(my_event_handler)


if __name__ == '__main__':
    main()
