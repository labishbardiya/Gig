"""Read-only readiness check. Does not plan, start, or spend credits on a call."""
from pathlib import Path
from gig_backend.calle import Calle


if __name__ == '__main__':
    cli = Calle('/opt/homebrew/lib/node_modules/@call-e/cli', str(Path(__file__).parent / 'vendor/run-agent-command.mjs'), '/opt/homebrew/bin/node')
    try:
        usable = cli.ready()
        print({'usable': usable})
        if usable:
            tools = cli.invoke(['mcp', 'tools'])
            # Report capability names only, never raw credentials or CLI response bodies.
            import json
            encoded = json.dumps(tools)
            print({'required_tools': {name: name in encoded for name in ('plan_call', 'run_call', 'get_call_run')}})
    except Exception:
        print({'usable': False, 'reason': 'CLI validation/auth readiness failed; no call attempted'})
