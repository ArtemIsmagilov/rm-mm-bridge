from wsgi.handlers import *


def create_app(test_config=None):
    import logging, asyncio
    from flask import Flask, request, render_template, g, url_for
    from threading import Thread

    from wsgi.decorators import login_required
    from wsgi import views
    from converters import sing_plur_tasks, choose_name, create_full_name
    from wsgi.constants import EXPAND_DICT, OPTIONS_DONE_FOR_FORM
    from wsgi.settings import envs

    if envs.DEBUG:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )

    app = Flask(__name__, static_url_path='/static', static_folder='./static')

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
