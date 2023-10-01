def unregister_mm_account(login_mm: str) -> dict:
    return {
        'type': 'error',
        'text': f'# Mattermost account with login `{login_mm}` not added in config file for integration with redmine'
    }


def start_date_greater() -> dict:
    return {
        'type': 'error',
        'text': '# Due date must be greater than start date'
    }


def invalid_format_date() -> dict:
    return {
        'type': 'error',
        'text': f'# Invalid format date'
    }


def invalid_estimated_time(t: str) -> dict:
    return {
        'type': 'error',
        'text': f'# Invalid format for estimated time - {t}'
    }


def no_rm_access_token() -> dict:
    return {
        'type': 'error',
        'text': '# Your app haven\'t redmine access token.'
    }


def deactivate_or_not_exist_rm_account(login_rm: str) -> dict:
    return {
        'type': 'error',
        'text': f'# Redmine account-`{login_rm}` doesn\'t exist or deactivated.'
    }


def no_rm_project(login_rm: str, project_id: str) -> dict:
    return {
        'type': 'error',
        'text': f'# User with login \'{login_rm}\' haven\'t project with identifier `{project_id}`.'
    }


def no_rm_projects(author: str) -> dict:
    return {
        "type": 'error',
        "text": f"# {author}, you have not projects in redmine"
    }


def no_access_project(login_rm: str, project_id: str) -> dict:
    return {
        'type': 'error',
        'text': f'# User with login \'{login_rm}\' does not have access to the project with identifier `{project_id}`.'
    }


def invalid_input_data() -> dict:
    return {
        'type': 'error',
        'text': '# Invalid input data. Look for example.'
    }


def long_subject() -> dict:
    return {
        'type': 'error',
        'text': '# Subject is too long (maximum is 255 characters)'
    }


def no_tasks_for_you(author: str) -> dict:
    return {
        'type': 'error',
        'text': f'{author}, there are no tasks for you yet.'
    }


def no_tasks_by_you(author: str) -> dict:
    return {
        'type': 'error',
        'text': f'{author}, there are no tasks by you yet.'
    }
