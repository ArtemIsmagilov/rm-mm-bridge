from dotenv import load_dotenv

import dotenv, os
from abc import ABC, abstractmethod


class Conf(ABC):
    @abstractmethod
    def __init__(self, filename: str):
        path_dotenv = dotenv.find_dotenv(filename)
        dotenv.load_dotenv(path_dotenv)

        load_dotenv(filename)

        self.APP_SCHEMA = os.environ['APP_SCHEMA']
        self.APP_HOST_INTERNAl = os.environ['APP_HOST_INTERNAl']
        self.APP_PORT_INTERNAL = os.environ['APP_PORT_INTERNAL']
        self.APP_HOST_EXTERNAL = os.environ['APP_HOST_EXTERNAL']
        self.APP_PORT_EXTERNAL = os.environ['APP_PORT_EXTERNAL']

        self.MM_SCHEMA = os.environ['MM_SCHEMA']
        self.MM_HOST_EXTERNAL = os.environ['MM_HOST_EXTERNAL']
        self.MM_PORT_EXTERNAL = os.environ['MM_PORT_EXTERNAL']

        self.RM_SCHEMA = os.environ['RM_SCHEMA']
        self.RM_HOST_EXTERNAL = os.environ['RM_HOST_EXTERNAL']
        self.RM_PORT_EXTERNAL = os.environ['RM_PORT_EXTERNAL']

        self.rm_admin_key = os.environ['rm_admin_key']
        self.mm_app_token = os.environ['mm_app_token']

        self.app_url_internal = os.environ['app_url_internal']
        self.app_url_external = os.environ['app_url_external']

        self.redmine_url_external = os.environ['redmine_url_external']
        self.mattermost_url_external = os.environ['mattermost_url_external']


class Dev(Conf):
    def __init__(self, filename='.dev.env'):
        super().__init__(filename)


class Prod(Conf):
    def __init__(self, filename='.env'):
        super().__init__(filename)


class Debuging(Conf):
    def __init__(self, filename='debug.env'):
        super().__init__(filename)


class Testing(Conf):
    def __init__(self, filename='.test.env'):
        super().__init__(filename)
        # testing client
        self.test_mm_email1 = os.environ['test_mm_email1']
        self.test_mm_username1 = os.environ['test_mm_username1']
        self.test_mm_password1 = os.environ['test_mm_password1']
        self.test_mm_first_name1 = os.environ['test_mm_first_name1']
        self.test_mm_last_name1 = os.environ['test_mm_last_name1']

        self.test_mm_email2 = os.environ['test_mm_email2']
        self.test_mm_username2 = os.environ['test_mm_username2']
        self.test_mm_password2 = os.environ['test_mm_password2']
        self.test_mm_first_name2 = os.environ['test_mm_first_name2']
        self.test_mm_last_name2 = os.environ['test_mm_last_name2']

        # redmine clients
        self.test_rm_email1 = os.environ['test_rm_email1']
        self.test_rm_username1 = os.environ['test_rm_username1']
        self.test_rm_password1 = os.environ['test_rm_password1']
        self.test_rm_first_name1 = os.environ['test_rm_first_name1']
        self.test_rm_last_name1 = os.environ['test_rm_last_name1']

        self.test_rm_email2 = os.environ['test_rm_email2']
        self.test_rm_username2 = os.environ['test_rm_username2']
        self.test_rm_password2 = os.environ['test_rm_password2']
        self.test_rm_first_name2 = os.environ['test_rm_first_name2']
        self.test_rm_last_name2 = os.environ['test_rm_last_name2']


envs = Prod()
