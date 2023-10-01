import time
from datetime import timedelta, date
from mattermostautodriver import Driver

from tests.conftest import env, test_project_rm, test_mm_user1, test_rm_user1
from wsgi import bot, handlers
from wsgi.redmine_api import delete_issue
from wsgi.settings import envs


def block_1(url, client, template, username1=envs.test_mm_username1, username2=envs.test_mm_username2):
    tm = env.get_template(template)
    dt1 = (date.today() + timedelta(days=1)).strftime('%d.%m.%Y')
    dt2 = (date.today() + timedelta(days=1)).strftime('%d.%m.%Y')
    msg = tm.render(username1=username1, username2=username2, dt1=dt1, dt2=dt2)

    data = {'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                        'first_name': test_mm_user1['first_name'],
                                        'last_name': test_mm_user1['last_name']}},
            'values': {'message': msg, 'option': {"label": test_project_rm.name, "value": test_project_rm.identifier}}}

    response = client.post(url, json=data)
    # delete project's issues
    [delete_issue(i) for i in test_project_rm.issues]
    return response


def block_2(url,
            client,
            project,
            tracker,
            subject,
            description,
            status,
            priority,
            start_date,
            end_date,
            estimated_time,
            done,
            assignee,
            ):
    data = {
        'context': {'acting_user': {'id': test_mm_user1['id'], 'username': test_mm_user1['username'],
                                    'first_name': test_mm_user1['first_name'], 'last_name': test_mm_user1['last_name']
                                    }
                    },
        'values': {'project': {'value': project.id, 'label': project.name},
                   'tracker': {'value': tracker.id},
                   'subject': subject,
                   'description': description,
                   'status': {'value': status.id, 'label': status.name},
                   'priority': {'value': priority.id, 'label': priority.name},
                   'start_date': start_date,
                   'end_date': end_date,
                   'estimated_time': estimated_time,
                   'done': done,
                   'assignee': assignee
                   }
    }

    response = client.post(url, json=data)
    # delete project's issues
    [delete_issue(i) for i in test_project_rm.issues]
    return response


def block_3(msg: str, secs: int):
    mm_client1 = Driver({
        'scheme': envs.MM_SCHEMA,
        'url': envs.MM_HOST_EXTERNAL,
        'port': int(envs.MM_PORT_EXTERNAL),
        'token': envs.test_mm_token1,
        'verify': True,  # Or /path/to/file.pem
    })
    mm_client1.login()

    context = {'bot_user_id': bot.client.userid, 'acting_user': {'id': test_mm_user1['id']}}
    channel_id = handlers.create_direct_channel(context)

    created_post = mm_client1.posts.create_post({'channel_id': channel_id, 'message': msg})
    time.sleep(secs)
    new_post = bot.posts.get_post(created_post['id'])

    return new_post

