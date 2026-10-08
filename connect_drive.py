"""Run locally on the server to authorize Drive; never paste credentials into chat."""
import argparse
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client_json', type=Path, help='Your Google OAuth Desktop app client JSON')
    parser.add_argument('--output', type=Path, default=Path('data/google-authorized-user.json'))
    parser.add_argument('--workspace', action='store_true', help='Also authorize Gmail draft and Calendar event scopes')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new output path to preserve existing credentials.')
    scopes = ['https://www.googleapis.com/auth/drive.file']
    if args.workspace:
        scopes += ['https://www.googleapis.com/auth/gmail.compose',
                   'https://www.googleapis.com/auth/calendar.events']
    flow = InstalledAppFlow.from_client_secrets_file(str(args.client_json), scopes=scopes)
    credentials = flow.run_local_server(port=0)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(credentials.to_json())
    print('Google authorization completed. Set GIG_GOOGLE_CREDENTIALS_FILE to the absolute output path, then restart GIG.')
    print('Do not share or commit either JSON file. No files have been uploaded.')
