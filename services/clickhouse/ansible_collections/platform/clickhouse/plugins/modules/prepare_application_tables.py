DOCUMENTATION = '''
module: prepare_application_tables
short_description: Render application table SQL on the Ansible controller
description: Uses the ordinary Ansible template lookup without target contact.
options:
  job: {type: dict, required: true, description: Resolved provider job.}
  phase: {type: str, required: true, description: Existing provider phase.}
  template_path: {type: path, required: true, description: Existing role table template.}
author: Platform Installer
'''
