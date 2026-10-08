"""Save the Fish API key privately without echoing it or putting it in shell history."""
import getpass
import os
from pathlib import Path

if __name__ == '__main__':
    key = getpass.getpass('Fish Audio API key (hidden): ').strip()
    if not key or any(c.isspace() for c in key):
        raise SystemExit('No valid key entered; nothing changed.')
    directory = Path(__file__).resolve().parent/'data'
    directory.mkdir(mode=0o700, exist_ok=True)
    target = directory/'fish-api-key'
    fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
    os.chmod(target, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(key)
    print('Saved privately. No restart needed. Refresh the phone app and try a short reply.')
