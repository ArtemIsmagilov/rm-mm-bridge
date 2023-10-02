def create_app(test_config=None):
    import logging, asyncio, os, textwrap, requests, json, re
    from flask import Flask, request, render_template, g, url_for
    from threading import Thread
    from datetime import datetime, date
    from typing import Sequence
    from posixpath import join
    from redminelib import Redmine
    from redminelib.exceptions import ResourceNotFoundError, ForbiddenError, ImpersonateError, AuthError

    from ext_funcs import sing_plur_tasks, choose_name, create_full_name
    from wsgi.decorators import login_required
    from wsgi import views
    from wsgi.constants import EXPAND_DICT, OPTIONS_DONE_FOR_FORM
    from wsgi.settings import envs
    from wsgi.client_errors import ValidationDateError, ValidationTextError
    from wsgi.my_bot import send_ephemeral_post, bot

    if envs.DEBUG:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )

    app = Flask(__name__, static_url_path='/static', static_folder='./static')

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

    @app.route('/manifest.json')
    def manifest() -> dict:
        return {
            'app_id': 'redmine-mattermost',
            'display_name': 'Redmine',
            'description': 'Integration Redmine server with Mattermost server',
            'homepage_url': 'https://github.com/ArtemIsmagilov/rm-mm-bridge.git',
            'app_type': 'http',
            'version': 'v1.0.2',
            'icon': 'redmine.png',
            'remote_webhook_auth_type': 'secret',
            'requested_permissions': ['act_as_bot', 'act_as_user', 'remote_webhooks'],
            'on_install': {
                'path': '/install',
                'expand': EXPAND_DICT,
            },
            'bindings': {
                'path': '/bindings',
            },
            'requested_locations': ['/command'],
            "http": {
                "root_url": envs.app_url_external,
            },
        }

    @app.route('/bindings', methods=['GET', 'POST'])
    def on_bindings() -> dict:
        return {
            'type': 'ok',
            'data': [{
                # binding for a command
                'location': '/command',
                'bindings': [{  # command with embedded form
                    'description': 'Redmine-Mattermost bridge',
                    'hint': '[help|new_task|new_tasks|tasks_by_me|tasks_for_me]',
                    # this will be the command displayed to user as /second-command
                    'label': 'redmine',
                    'icon': static_path('redmine.png'),
                    'bindings': [{  # help
                        'description': 'show help info about all commands app',
                        'hint': '[This is command with info about app]',
                        'label': 'help',
                        'icon': static_path('redmine.png'),
                        'submit': {
                            'path': '/help',
                            'expand': EXPAND_DICT,
                        },
                    },
                        {  # new_task
                            'description': 'create new one task by Redmine form',
                            'hint': '[You can create task by form with some fields]',
                            'label': 'new_task',
                            'icon': static_path('redmine.png'),
                            'submit': {
                                'path': '/new_task',
                                'expand': EXPAND_DICT,
                            },
                        },

                        {  # new_tasks
                            'description': 'create tasks in one slash-command',
                            'hint': '[You can create some tasks in one slash-command with some lines]',
                            'label': 'new_tasks',
                            'icon': static_path('redmine.png'),
                            'submit': {
                                'path': '/new_tasks',
                                'expand': EXPAND_DICT,
                            },
                        },

                        {  # tasks_for_me
                            'description': 'tasks for me',
                            'hint': '[You can look tasks assigned for you]',
                            'label': 'tasks_for_me',
                            'icon': static_path('redmine.png'),
                            'submit': {
                                'path': '/tasks_for_me',
                                'expand': EXPAND_DICT,
                            },
                        },
                        {  # tasks_by_me
                            'description': 'tasks by me',
                            'hint': '[You can look your tasks assigned by you]',
                            'label': 'tasks_by_me',
                            'icon': static_path('redmine.png'),
                            'submit': {
                                'path': '/tasks_by_me',
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
        subscribe_team_join(request.json['context'])
        return {'type': 'ok', 'text': 'success installing...', 'data': []}

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

    @app.before_request
    def load_user():
        if request.method == 'POST' and request.path not in {'/install', '/ping', '/bindings'}:
            mm_username = request.json['context']['acting_user']['username']
            g.user = os.environ.get(mm_username, None)

    @app.route('/help', methods=['POST'])
    @login_required
    def help_handler():
        login_rm = g.user
        acting_user = request.json['context']['acting_user']
        login_mm = acting_user['username']
        full_name = create_full_name(acting_user['first_name'], acting_user['last_name'])
        author = choose_name(full_name, login_mm)

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=login_rm).session() as redmine:
            # validation2 [have account and token for REST API]
            redmine_user = check_exist_account_and_token_in_redmine(redmine, login_rm)
            if type(redmine_user) is dict:
                return redmine_user

        md = render_template('help.md', author=author)
        return {
            'type': 'ok',
            'text': md,
        }

    @app.route('/tasks_by_me', methods=['POST'])
    @login_required
    def tasks_by_me_handler():
        login_rm = g.user
        acting_user = request.json['context']['acting_user']
        login_mm = acting_user['username']
        full_name = create_full_name(acting_user['first_name'], acting_user['last_name'])
        author = choose_name(full_name, login_mm)

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=login_rm).session() as redmine:
            # validation2 [have account and token for REST API]
            res = check_exist_account_and_token_in_redmine(redmine, login_rm)
            if type(res) is dict:
                return res

            my_tasks = redmine.issue.filter(author_id='me')

            if not my_tasks:
                return views.no_tasks_by_you(author)

            url_reported_tasks = f'{envs.redmine_url_external}/issues?c%5B%5D=project&c%5B%5D=tracker&c%5B%5D=status&c%5B%5D=subject&f%5B%5D=status_id&f%5B%5D=author_id&f%5B%5D=project.status&op%5Bauthor_id%5D=%3D&op%5Bproject.status%5D=%3D&op%5Bstatus_id%5D=o&set_filter=1&sort=updated_on%3Adesc&v%5Bauthor_id%5D%5B%5D=me&v%5Bproject.status%5D%5B%5D=1&v%5Bstatus_id%5D%5B%5D='
            t = sing_plur_tasks(my_tasks)
            text = '\n'.join((
                f'# Ok, {author}. I show {t} assigned by you for others.',
                generating_table_tasks(my_tasks),
                f'[{t.title()} assigned by me]({url_reported_tasks})'
            ))

            return {
                'type': 'ok',
                'text': text,
            }

    @app.route('/tasks_for_me', methods=['POST'])
    @login_required
    def tickets_for_me_handler():
        login_rm = g.user
        acting_user = request.json['context']['acting_user']
        login_mm = acting_user['username']
        full_name = create_full_name(acting_user['first_name'], acting_user['last_name'])
        author = choose_name(full_name, login_mm)

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=login_rm).session() as redmine:
            # validation2 [have account and token for REST API]
            res = check_exist_account_and_token_in_redmine(redmine, login_rm)
            if type(res) is dict:
                return res

            tasks_for_me = redmine.issue.filter(assigned_to_id='me')
            if not tasks_for_me:
                return views.no_tasks_for_you(author)

        url_issues_assigned_to_me = f'{envs.redmine_url_external}/issues?c%5B%5D=project&c%5B%5D=tracker&c%5B%5D=status&c%5B%5D=subject&c%5B%5D=author&f%5B%5D=status_id&f%5B%5D=assigned_to_id&f%5B%5D=project.status&op%5Bassigned_to_id%5D=%3D&op%5Bproject.status%5D=%3D&op%5Bstatus_id%5D=o&set_filter=1&sort=author%2Cpriority%3Adesc%2Cupdated_on%3Adesc&v%5Bassigned_to_id%5D%5B%5D=me&v%5Bproject.status%5D%5B%5D=1&v%5Bstatus_id%5D%5B%5D='
        t = sing_plur_tasks(tasks_for_me)
        text = '\n'.join((
            f'# Ok, {author}. I show {t} assigned for you.',
            f'[{t.title()} assigned to me]({url_issues_assigned_to_me})\n',
            generating_table_tasks(tasks_for_me),
        ))

        return {
            'type': 'ok',
            'text': text,
        }

    @app.route('/new_task', methods=['POST'])
    @login_required
    def new_task_handler():
        login_rm = g.user
        acting_user = request.json['context']['acting_user']
        login_mm = acting_user['username']
        full_name = create_full_name(acting_user['first_name'], acting_user['last_name'])
        author = choose_name(full_name, login_mm)

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=login_rm).session() as redmine:
            # validation2 [have account and token for REST API]
            res = check_exist_account_and_token_in_redmine(redmine, login_rm)
            if type(res) is dict:
                return res
            print(res)

            options_projects_in_redmine = generate_projects_for_form(redmine)

            if not options_projects_in_redmine:
                return views.no_rm_projects(author)

            today = date.today().strftime('%d.%m.%Y')
            options_trackers_in_redmine = generate_trackers_for_form(redmine)
            options_priorities_in_redmine = generate_priorities_for_form(redmine)
            options_statuses_in_redmine = generate_statuses_for_form(redmine)

        return {
            'type': 'form',
            "form": {
                "title": "Create task by form.",
                "icon": static_path('redmine.png'),
                "submit": {
                    "path": "/new_task_submit",
                    "expand": EXPAND_DICT,
                },
                "fields": [
                    {  # project
                        "name": "project",
                        "type": "static_select",
                        'is_required': True,
                        'description': 'Select redmine project from list',
                        "label": "Project",
                        "modal_label": 'Project',
                        'hint': 'name project',
                        "options": options_projects_in_redmine,
                    },
                    {  # tracker
                        "name": "tracker",
                        "type": "static_select",
                        'is_required': True,
                        'value': options_trackers_in_redmine[0],
                        'description': 'Select tracker',
                        "label": "Tracker",
                        "modal_label": 'Tracker',
                        'hint': 'name tracker',
                        "options": options_trackers_in_redmine,
                    },
                    {  # subject
                        "name": "subject",
                        "type": "text",
                        'is_required': True,
                        'description': 'Write short text for assignee',
                        "label": "Subject",
                        "modal_label": 'Subject',
                        'hint': 'Exist current task...',
                    },
                    {  # description
                        'name': 'description',
                        'type': 'text',
                        'subtype': 'textarea',
                        'description': 'Describe the task in detail',
                        'label': 'Description',
                        "modal_label": 'Description',
                        'hint': 'Some text...',
                    },
                    {  # status
                        "name": "status",
                        "type": "static_select",
                        'is_required': True,
                        'value': options_statuses_in_redmine[0],
                        'description': 'Select status',
                        "label": "Status",
                        "modal_label": 'Status',
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
                        'modal_label': 'Priority',
                        'hint': 'name priority',
                        "options": options_priorities_in_redmine,
                    },
                    {  # assignee
                        "name": "assignee",
                        "type": "user",
                        'description': 'Select mattermost user',
                        "label": "Assignee",
                        'modal_label': 'Assignee',
                        'hint': 'login in mattermost',
                    },
                    {  # start_date
                        "name": "start_date",
                        "type": "text",
                        'value': today,
                        'description': 'By default today or write need date',
                        "label": "Start_date",
                        'modal_label': 'Start date',
                        'hint': 'day.month.year(03.03.2023)',
                    },
                    {  # end_date
                        "name": "end_date",
                        "type": "text",
                        'description': 'By default None or write need date. End_date must > today',
                        "label": "End_date",
                        'modal_label': 'End date',
                        'hint': 'day.month.year(03.03.2023)',
                    },
                    {  # estimated time
                        "name": "estimated_time",
                        "type": "text",
                        'description': 'Write need count hours(natural digit)',
                        "label": "Estimated_time",
                        'modal_label': 'Estimated time',
                        'hint': 'only hours(natural number)',
                    },
                    {  # done
                        "name": "done",
                        "type": "static_select",
                        'is_required': True,
                        'value': OPTIONS_DONE_FOR_FORM[0],
                        'description': 'Select value done(%)',
                        "label": "Done",
                        'modal_label': 'Done',
                        'hint': 'value done',
                        "options": OPTIONS_DONE_FOR_FORM,

                    }

                ]
            }
        }

    @app.route('/new_tasks', methods=['POST'])
    @login_required
    def new_tasks_handler() -> dict:
        login_rm = g.user
        acting_user = request.json['context']['acting_user']
        login_mm = acting_user['username']
        full_name = create_full_name(acting_user['first_name'], acting_user['last_name'])
        author = choose_name(full_name, login_mm)

        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key, impersonate=login_rm).session() as redmine:
            # validation2 [have account and token for REST API]
            res = check_exist_account_and_token_in_redmine(redmine, login_rm)
            if type(res) is dict:
                return res

            options_projects_in_redmine = generate_projects_for_form(redmine)

            if not options_projects_in_redmine:
                return views.no_rm_projects(author)

        return {
            'type': 'form',
            "form": {
                "title": "Create tasks in one command.",
                "icon": static_path('redmine.png'),
                "submit": {
                    "path": "/new_tasks_submit",
                    "expand": EXPAND_DICT,
                },
                "fields": [
                    {
                        "name": "option",
                        "type": "static_select",
                        "label": "Project",
                        'modal_label': 'Project',
                        "options": options_projects_in_redmine,
                        'is_required': True,
                        'description': 'Select redmine project from list',
                        'hint': 'name project',
                        'position': 1,
                    },
                    {
                        "name": "message",
                        "type": "text",
                        "label": "Tasks",
                        'modal_label': 'Tasks',
                        'is_required': True,
                        'description': 'You need write one or some lines task, user and deadline date.',
                        'hint': ('1. Купить колбасы @vasiliy.fedorov 09.05.2023\n'
                                 '2. Написать симфонию @artem.ismagilov 10.05.2023\n'
                                 '[number issue]. [some text] @[username] [day.month.year]\n'
                                 ),
                        'position': 2,
                        'subtype': 'textarea',
                    },

                ]
            }
        }

    @app.route('/new_task_submit', methods=['POST'])
    @login_required
    def new_task_submit_handler() -> dict:
        login_rm = g.user
        values = request.json["values"]
        context = request.json["context"]
        acting_user = context['acting_user']
        login_mm = acting_user['username']
        full_name = create_full_name(acting_user['first_name'], acting_user['last_name'])
        author = choose_name(full_name, login_mm)

        task = validation_create_task_by_form(login_rm, context, values)
        if type(task) is dict:
            return task

        task.login_mm = login_mm

        text = '\n'.join((
            f'# Ok, {author}. I create task in redmine by form',
            generating_pretext(login_mm, (task,)),
            generating_table_tasks((task,))
        ))
        return {
            'type': 'ok',
            'text': text,
        }

    @app.route('/new_tasks_submit', methods=['POST'])
    @login_required
    def new_tasks_submit_handler() -> dict:
        login_rm = g.user
        values = request.json["values"]
        acting_user = request.json["context"]['acting_user']
        message, project_identifier = values['message'], values['option']['value']
        login_mm = acting_user['username']
        full_name = create_full_name(acting_user['first_name'], acting_user['last_name'])
        author = choose_name(full_name, login_mm)
        date_today = date.today()

        parsed_data = check_parsing_text(message)
        if type(parsed_data) is dict:
            return parsed_data

        redmine_users = []
        with Redmine(envs.redmine_url_external, key=envs.rm_admin_key).session() as redmine:
            for task, username, dt in parsed_data:
                # validation1 [have user in .env file]
                login_in_redmine_next_user = check_exist_login_redmine_in_config_file(username)
                if type(login_in_redmine_next_user) is dict:
                    return login_in_redmine_next_user

                with redmine.session(impersonate=login_in_redmine_next_user):
                    # validation2 [have account and token for REST API]
                    redmine_user = check_exist_account_and_token_in_redmine(redmine, login_in_redmine_next_user)
                    if type(redmine_user) is dict:
                        return redmine_user

                    # validation3 [user isn't included in this project]
                    res = check_included_user_in_project(redmine, project_identifier, redmine_user.login)
                    if type(res) is dict:
                        return res

                    redmine_user.created_task = task
                    redmine_user.created_date_end = dt
                    redmine_user.login_mm = username
                    redmine_users.append(redmine_user)

            with redmine.session(impersonate=login_rm):
                tasks = []
                for rm_u in redmine_users:
                    rm_obj = redmine.issue.create(
                        project_id=project_identifier,
                        subject=rm_u.created_task,
                        assigned_to_id=rm_u.id,
                        start_date=date_today,
                        due_date=rm_u.created_date_end,
                    )
                    rm_obj.login_mm = rm_u.login_mm
                    tasks.append(rm_obj)

        t = sing_plur_tasks(tasks)
        text = '\n'.join((
            f'# Ok, {author}. I create your {t} in redmine.',
            generating_pretext(login_mm, tasks),
            generating_table_tasks(tasks)
        ))

        return {
            'type': 'ok',
            'text': text,
        }

    def websocket_mattermost():
        asyncio.set_event_loop(event_loop_websocket_mattermost)
        bot.init_websocket(my_event_handler)

    if bot:
        event_loop_websocket_mattermost = asyncio.new_event_loop()
        Thread(target=websocket_mattermost, daemon=True).start()

    return app
