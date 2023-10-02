import multiprocessing
from wsgi.settings import envs

#workers = multiprocessing.cpu_count() * 2 + 1
bind = f"{envs.APP_HOST_INTERNAl}:{envs.APP_PORT_INTERNAL}"
accesslog = '-'
access_log_format = 'h:%(h)s l:%(l)s u:%(u)s t:%(t)s r:"%(r)s" s:%(s)s b:%(b)s f:"%(f)s" a:"%(a)s"\n________________'
wsgi_app = 'wsgi:create_app()'
loglevel = 'debug'
# certfile = '/etc/letsencrypt/live/www.example.com/fullchain.pem'
# keyfile = '/etc/letsencrypt/live/www.example.com/privkey.pem'
#ssl_version =  # if necessary
# check_config = True
