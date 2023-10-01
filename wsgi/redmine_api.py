from redminelib import Redmine

from wsgi.settings import envs
from wsgi.decorators import decorator_redmine_error


@decorator_redmine_error
def create_redmine_user(**fields):
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.user.create(**fields)


@decorator_redmine_error
def delete_redmine_user(resource_id: int):
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.user.delete(resource_id)


@decorator_redmine_error
def delete_redmine_user_by_username(username: str):
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    for u in redmine.user.filter(name=username):
        return u.delete()


@decorator_redmine_error
def create_redmine_project(**fields):
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.project.create(**fields)


@decorator_redmine_error
def delete_redmine_project(resource_id):
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.project.delete(resource_id)


@decorator_redmine_error
def create_project_memberships(**fields):
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.project_membership.create(**fields)


@decorator_redmine_error
def delete_issue(resource_id):
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.issue.delete(resource_id)


@decorator_redmine_error
def all_roles():
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.role.all()


@decorator_redmine_error
def all_trackers():
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.tracker.all()


@decorator_redmine_error
def all_issue_statuses():
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.issue_status.all()


@decorator_redmine_error
def all_priorities():
    redmine = Redmine(envs.redmine_url_external, key=envs.rm_admin_key)
    return redmine.enumeration.filter(resource='issue_priorities')
