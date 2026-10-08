"""CALL-E skill launcher adapter. No direct vendor HTTP or shell interpolation."""
import json
from pathlib import Path
import subprocess


TERMINAL = {'COMPLETED', 'FAILED', 'NO_ANSWER', 'DECLINED', 'CANCELED', 'CANCELLED', 'VOICEMAIL', 'BUSY', 'EXPIRED'}


class Calle:
    def __init__(self, package_dir, launcher, node):
        self.package_dir = package_dir
        self.launcher = launcher
        self.node = node

    def invoke(self, argv):
        package = json.loads((Path(self.package_dir) / 'package.json').read_text())
        if package.get('name') != '@call-e/cli' or package.get('bin', {}).get('calle') not in ('bin/calle.js', './bin/calle.js'):
            raise RuntimeError('Untrusted CALL-E entry point')
        request = {'package_dir': self.package_dir, 'integration': {'source': 'skills_sh', 'name': 'skills_sh_skill', 'version': '0.1.0'}, 'argv': argv}
        process = subprocess.run([self.node, self.launcher], input=json.dumps(request), text=True,
                                 capture_output=True, timeout=90, shell=False)
        # Never expose stderr/raw CLI responses: these may contain sensitive recovery data.
        if process.returncode:
            raise RuntimeError('CALL-E command failed; inspect privately before retrying')
        result = json.loads(process.stdout)
        if result.get('ok') is False:
            raise RuntimeError('CALL-E returned an error')
        return result

    def ready(self):
        result = self.invoke(['auth', 'status'])
        return result.get('usable') is True

    def start(self, payload):
        goal = ('You are an AI assistant calling on behalf of ' + payload['on_behalf_of'] +
                '. Disclose this at the beginning; do not impersonate the human. Respect refusal. '
                'Do not make purchases, commitments, or reveal information beyond the supplied scope. '
                'Objective: ' + payload['goal'] + '\nApproved context: ' + payload['context'] +
                '\nBoundaries: ' + payload['boundaries'])
        args = ['call', 'start', '--to-phone', payload['phone'], '--goal', goal,
                '--language', payload['language'], '--region', payload['region']]
        result = self.invoke(args)
        run_id = result.get('run_id')
        if not isinstance(run_id, str) or not run_id:
            # Includes call_started=unknown. Never automatically resubmit.
            raise RuntimeError('Submission uncertain; manual recovery required')
        content = result.get('status_result', {}).get('structuredContent', {})
        return run_id, sanitise(content)

    def status(self, run_id):
        result = self.invoke(['call', 'status', '--run-id', run_id])
        return sanitise(result.get('result', {}).get('structuredContent', {}))


def sanitise(content):
    if not isinstance(content, dict):
        return {'status': 'UNKNOWN', 'untrusted_call_data': True}
    # Do not return arbitrary recovery commands, credentials or execution confirmation fields.
    return {**{k: content[k] for k in ('status', 'summary', 'post_summary', 'transcript', 'activity', 'call_id') if k in content}, 'untrusted_call_data': True}
