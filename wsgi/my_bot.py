from mattermostautodriver import Driver

from wsgi.settings import envs
from wsgi.decorators import decorator_http_error


@decorator_http_error
def send_ephemeral_post(user_id, channel_id, msg):
    resp = bot.posts.create_post_ephemeral(options={
        'user_id': user_id,
        'post': {
            'channel_id': channel_id,
            'message': msg,
        }
    })
    return resp


@decorator_http_error
def create_user(options: dict):
    return bot.users.create_user(options)


@decorator_http_error
def create_token(user_id, options):
    return bot.users.create_user_access_token(user_id, options)


@decorator_http_error
def get_user_by_username(username: str):
    return bot.users.get_user_by_username(username)


def create_direct_channel(context: dict):
    bot_user_id = context['bot_user_id']
    user_id = context['acting_user']['id']
    data = [bot_user_id, user_id]
    response_dict = bot.channels.create_direct_channel(options=data)
    channel_id = response_dict['id']
    return channel_id

if envs.mm_app_token:
    bot = Driver({
        'scheme': envs.MM_SCHEMA,
        'url': envs.MM_HOST_EXTERNAL,
        'port': int(envs.MM_PORT_EXTERNAL),
        'token': envs.mm_app_token,
        'verify': True,  # Or /path/to/file.pem
    })

    bot.login()
else:
    bot = None
