"""Start the cached read-only research MCP on localhost; no app credentials used."""
import os
import secrets
import subprocess
from pathlib import Path

repo = Path(__file__).resolve().parent / '.agent_cache/resources/huggingface/pwc-cli'
if not (repo / 'mcp_server/pyproject.toml').exists():
    raise SystemExit('Missing research checkout: huggingface/pwc-cli')
env = os.environ.copy()
env.setdefault('PWC_MCP_CURSOR_KEY_CURRENT', secrets.token_urlsafe(48))
env['PWC_MCP_HOST'] = '127.0.0.1'
subprocess.run(['uv', 'run', '--project', 'mcp_server', 'pwc-mcp'], cwd=repo, env=env, check=True)
