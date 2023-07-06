# gunicorn settings
import multiprocessing

from settings import APP_HOST_INTERNAl, APP_HOST_EXTERNAL, APP_PORT
#workers = multiprocessing.cpu_count() * 2 + 1
bind = f"{APP_HOST_EXTERNAL}:{APP_PORT}"
accesslog = '-'
access_log_format = 'h:%(h)s l:%(l)s u:%(u)s t:%(t)s r:"%(r)s" s:%(s)s b:%(b)s f:"%(f)s" a:"%(a)s"\n________________'
wsgi_app = 'start:create_app()'
loglevel = 'debug'

# certfile = path_to_certfile
# keyfile = path_to_keyfile

#check_config = True
