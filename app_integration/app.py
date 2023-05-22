import logging, os, requests, datetime, re
from dotenv import load_dotenv
from posixpath import join
from flask import Flask, request, url_for
from redminelib import Redmine
from redminelib.exceptions import ImpersonateError, AuthError, ResourceNotFoundError
from mattermostdriver import Driver
from mattermostdriver.exceptions import NoAccessTokenProvided, InvalidOrMissingParameters

load_dotenv()

REDMINE_HOST = os.environ['REDMINE_HOST']
REDMINE_PORT = os.environ['REDMINE_PORT']

MATTERMOST_HOST = os.environ['MATTERMOST_HOST']
MATTERMOST_PORT = os.environ['MATTERMOST_PORT']

PYTHON_BOT_APP_HOST = os.environ['PYTHON_BOT_APP_HOST']
PYTHON_BOT_APP_PORT = os.environ['PYTHON_BOT_APP_PORT']

ADMIN_REDMINE_KEY_API = os.environ['ADMIN_REDMINE_KEY_API']
ADMIN_MATTERMOST_TOKEN = os.environ['ADMIN_MATTERMOST_TOKEN']

REDMINE_MATTERMOST_BRIDGE_APP_TOKEN = os.environ['REDMINE_MATTERMOST_BRIDGE_APP_TOKEN']

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, static_url_path='/static', static_folder='./static')

default_root_url = f'http://{PYTHON_BOT_APP_HOST}:{PYTHON_BOT_APP_PORT}'
static_path = f'{default_root_url}/static'

EXPAND_DICT = {
    'app': 'all',
    'acting_user': 'all',
    'acting_user_access_token': 'all',
    'locale': 'all',
    'channel': 'all',
    'channel_member': 'all',
    'team': 'all',
    'team_member': 'all',
    'post': 'all',
    'root_post': 'all',
    'user': 'all',
    'oauth2_app': 'all',
    'oauth2_user': 'all',
}


class TicketUser:
    def __init__(self, task, login, date_end):
        self.task = task
        self.login = login
        self.date_end = date_end


class ValidationDateError(Exception):
    pass


def generating_pretext(creator_tickets, tickets):
    return f"**@{creator_tickets}** created tickets for {', '.join('*@%s*' % i.assigned_to for i in tickets)}"


def generating_table_for_current_tickets(tickets):
    table = '''| Author | Assigned | Project | Subject | Description | Status | Is closed | Priority | Start date | End date | Done |\n|-|-|-|-|-|-|-|-|-|-|-|\n'''
    for i in tickets:
        s_d = '%s.%s.%s' % (i.start_date.day, i.start_date.month, i.start_date.year)
        e_d = '%s.%s.%s' % (i.due_date.day, i.due_date.month, i.due_date.year)
        is_closed = 'Yes' if i.status.is_closed else 'No'
        line = '| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n' % \
               (i.author.name, i.assigned_to.name, i.project.name, i.subject, i.description,
                i.status.name, is_closed, i.priority.name, s_d, e_d, i.done_ratio)
        table += line
    return table


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


def generate_option_on_send_form_source(username):
    with Redmine(f'http://{REDMINE_HOST}:{REDMINE_PORT}', key=ADMIN_REDMINE_KEY_API,
                 impersonate=username).session() as redmine:
        redmine_user = redmine.user.get('current')
        result = [{"label": p.name, "value": p.identifier} for p in redmine.project.all()]
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
        'display_name': 'Redmine-Mattermost Bridge app',
        'homepage_url': 'https://github.com/mattermost/mattermost-app-examples/tree/master/python/hello-world',
        'app_type': 'http',
        'icon': f'redmine.png',
        'requested_permissions': ['act_as_bot', 'act_as_user', 'remote_oauth2', 'remote_webhooks'],
        'on_install': {
            'path': '/install',
            'expand': EXPAND_DICT,
        },
        'bindings': {
            'path': '/bindings',
        },
        'requested_locations': [
            '/channel_header',
            '/command',
            '/post_menu',

        ],
        'root_url': os.environ.get('ROOT_URL', default_root_url),

        "http": {
            "root_url": os.environ.get('ROOT_URL', default_root_url)
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

                    {
                        'description': 'test command',
                        'hint': '[This is command with info about app: redmine-mattermost-bridge]',
                        # this will be the command displayed to user as /first-command
                        'label': 'app_info',
                        'icon': f'{static_path}/redmine.png',
                        'submit': {
                            'path': '/app_info',
                            'expand': EXPAND_DICT,
                        },
                    },
                    # create_issues
                    {
                        'description': 'create issues',
                        'hint': '[You can create some issues in one form]',
                        'label': 'create_issues',
                        'icon': f'{static_path}/redmine.png',
                        'submit': {
                            'path': '/create_issues',
                            'expand': EXPAND_DICT,
                        },
                    },
                    # tickets_for_me
                    {
                        'description': 'tickets for me',
                        'hint': '[You can look ticket for you]',
                        'label': 'tickets_for_me',
                        'icon': f'{static_path}/redmine.png',
                        'submit': {
                            'path': '/tickets_for_me',
                            'expand': EXPAND_DICT,
                        },
                    },
                    # my_tickets
                    {
                        'description': 'my tickets',
                        'hint': '[You can look your tickets]',
                        'label': 'my_tickets',
                        'icon': f'{static_path}/redmine.png',
                        'submit': {
                            'path': '/my_tickets',
                            'expand': EXPAND_DICT,
                        },
                    },
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
def app_info():
    md = """
### Hi, i can 
* automatically create multiple tickets
* view tickets created by you
* view tasks that you have been assigned.

---

| commands        | Description                |
|-----------------|----------------------------|
| /app_info       | help info about app        |
| /create_issues  | create one or some tickets |
| /tickets_for_me | look tickets for me        |
| /my_tickets     | look my tickets            |

"""
    return {'type': 'ok', 'text': md}


@app.route('/my_tickets', methods=['POST'])
def my_tickets():
    context = request.json['context']
    username = context['acting_user']['username']
    with Redmine(f'http://{REDMINE_HOST}:{REDMINE_PORT}', key=ADMIN_REDMINE_KEY_API, impersonate=username). \
            session() as redmine:
        try:
            redmine_user = redmine.user.get('current')
        except ImpersonateError:
            return {'type': 'error', 'text': '### You have\'t account in redmine or you deactivated.'}
        except AuthError:
            return {'type': 'error', 'text': '### Your app haven\'t redmine access token.'}
        your_issues = redmine.issue.filter(author__id=redmine_user.id)
        if not your_issues:
            return {'type': 'ok', 'text': 'You haven\'t created issues yet'}

        bot = Driver({
            'url': MATTERMOST_HOST,
            'token': REDMINE_MATTERMOST_BRIDGE_APP_TOKEN,
            'scheme': 'http',
            'port': int(MATTERMOST_PORT),
            'basepath': '/api/v4',
            'verify': True,  # Or /path/to/file.pem
        })
        try:
            bot.login()
        except InvalidOrMissingParameters:
            return {'type': 'error', 'text': '## App haven\'t access token.'}
        except NoAccessTokenProvided:
            return {'type': 'error', 'text': '## App access token is not correct or is expired.'}
        bot_user_id = context['bot_user_id']
        user_id = context['acting_user']['id']
        data = [bot_user_id, user_id]
        response_dict = bot.channels.create_direct_message_channel(options=data)
        channel_id = response_dict['id']

        bot.posts.create_post(options={
            'channel_id': channel_id,
            'message': '# Ok. I look your tickets.',
            "props": {
                "attachments": [
                    {
                        "fallback": "test",
                        "pretext": f'@{username} tickets',
                        "text": generating_table_for_current_tickets(your_issues),
                    }
                ]}
        })
        return {'type': 'ok', }


@app.route('/tickets_for_me', methods=['POST'])
def tickets_for_me():
    context = request.json['context']
    username = context['acting_user']['username']
    with Redmine(f'http://{REDMINE_HOST}:{REDMINE_PORT}', key=ADMIN_REDMINE_KEY_API,
                 impersonate=username).session() as redmine:
        try:
            current_user = redmine.user.get('current')
        except ImpersonateError:
            return {'type': 'error', 'text': '## You have\'t account in redmine or you deactivated.'}
        except AuthError:
            return {'type': 'error', 'text': '### Your app haven\'t redmine access token.'}
        issues_for_me = current_user.issues
        if not issues_for_me:
            return {'type': 'ok', 'text': 'There are no tasks for you yet.'}
    bot = Driver({
        'url': MATTERMOST_HOST,
        'token': REDMINE_MATTERMOST_BRIDGE_APP_TOKEN,
        'scheme': 'http',
        'port': int(MATTERMOST_PORT),
        'basepath': '/api/v4',
        'verify': True,  # Or /path/to/file.pem
    })
    try:
        bot.login()
    except InvalidOrMissingParameters:
        return {'type': 'error', 'text': '## App haven\'t access token.'}
    except NoAccessTokenProvided:
        return {'type': 'error', 'text': '## App access token is not correct or is expired.'}
    bot_user_id = context['bot_user_id']
    user_id = context['acting_user']['id']
    data = [bot_user_id, user_id]
    response_dict = bot.channels.create_direct_message_channel(options=data)
    channel_id = response_dict['id']

    bot.posts.create_post(options={
        'channel_id': channel_id,
        'message': '# Ok. I look tickets for you.',
        "props": {
            "attachments": [
                {
                    "fallback": "test",
                    "pretext": f'Tickets for @{username}',
                    "text": generating_table_for_current_tickets(issues_for_me),
                }
            ]}
    })
    return {'type': 'ok', }


@app.route('/create_issues', methods=['POST'])
def create_issues():
    username = request.json['context']['acting_user']['username']
    try:
        options_projects_in_redmine = generate_option_on_send_form_source(username)
    except ImpersonateError:
        return {"type": 'error', "text": "## You have not account in redmine or you deactivated."}
    except AuthError:
        return {'type': 'error', 'text': '## Your app haven\'t redmine access token.'}
    if not options_projects_in_redmine:
        return {"type": 'ok', "text": "# You have not projects in redmine"}
    return {'type': 'form', "form": {
        "source": {
            "path": "/create_issues"
        },
        "title": "Create issues form.",
        "icon": f'{static_path}/redmine.png',
        "submit": {
            "path": "/create_issues_submit",
            "expand": EXPAND_DICT,
        },
        "fields": [
            {
                "name": "option",
                "type": "static_select",
                "label": "Projects",
                "options": options_projects_in_redmine,  # list options
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


@app.route('/create_issues_submit', methods=['POST'])
def create_issues_submit():
    values = request.json["values"]
    context = request.json["context"]
    message, project_id = values['message'], values['option']['value']
    username = context['acting_user']['username']
    date_today = datetime.date.today()
    try:
        parsed_data = parsing_input_text(message)
    except AttributeError:
        return {'type': 'error', 'text': '## Invalid input data. Look for example.'}
    except ValueError:
        return {'type': 'error', 'text': '## Invalid format end date. Look for example [day.month.year] - 10.8.23.'}
    except ValidationDateError:
        return {'type': 'error', 'text': '## Due date must be greater than start date'}
    
    redmine_users = []
    with Redmine(f'http://{REDMINE_HOST}:{REDMINE_PORT}', key=ADMIN_REDMINE_KEY_API).session() as redmine:
        for u in parsed_data:
            with redmine.session(impersonate=u.login):
                try:
                    redmine_user = redmine.user.get('current')
                except ImpersonateError:
                    return {'type': 'error', 'text': f'## User with login \'{u.login}\' doesn\'t exist in redmine.'}
                except AuthError:
                    return {'type': 'error', 'text': '### Your app haven\'t redmine access token.'}
                try:
                    project = redmine.project.get(project_id)
                except ResourceNotFoundError:
                    return {'type': 'error',
                            'text': f'## User with login \'{u.login}\' haven\'t project with ID \'{project_id}\'.'}
                redmine_user.created_task = u.task
                redmine_user.created_date_end = u.date_end
                redmine_users.append(redmine_user)

    tickets = [
        redmine.issue.create(
            project_id=project_id,
            subject=f'@{username} create ticket for @{t.login}',
            description=t.created_task,
            assigned_to_id=t.id,
            start_date=date_today,
            due_date=t.created_date_end,
        )
        for t in redmine_users]

    bot = Driver({
        'url': MATTERMOST_HOST,
        'token': REDMINE_MATTERMOST_BRIDGE_APP_TOKEN,
        'scheme': 'http',
        'port': int(MATTERMOST_PORT),
        'basepath': '/api/v4',
        'verify': True,  # Or /path/to/file.pem
    })
    try:
        bot.login()
    except InvalidOrMissingParameters:
        return {'type': 'error', 'text': '## App haven\'t access token.'}
    except NoAccessTokenProvided:
        return {'type': 'error', 'text': '## App access token is not correct or is expired.'}
    bot_user_id = context['bot_user_id']
    user_id = context['acting_user']['id']
    data = [bot_user_id, user_id]
    response_dict = bot.channels.create_direct_message_channel(options=data)
    channel_id = response_dict['id']

    bot.posts.create_post(options={
        'channel_id': channel_id,
        'message': '# Ok. I create your tickets in redmine.',
        "props": {
            "attachments": [
                {
                    "fallback": "test",
                    "pretext": generating_pretext(username, tickets),
                    "text": generating_table_for_current_tickets(tickets),
                }
            ]}
    })

    return {'type': 'ok'}


if __name__ == '__main__':
    app.run(
        debug=True,
        host=PYTHON_BOT_APP_HOST,
        port=int(PYTHON_BOT_APP_PORT),
        use_reloader=False,
    )
