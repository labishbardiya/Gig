"""Explicitly verify GIG Google OAuth; never send email or create a calendar event."""
import argparse
import json
from pathlib import Path

from gig_backend.google_verify import (CALENDAR_SCOPE, DRIVE_SCOPE, GMAIL_SCOPE,
                                       load_credentials, private_drive_probe, provider_check)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('authorized_user_json', type=Path, help='Private OAuth authorized-user JSON on this PC')
    parser.add_argument('--write-drive-probe', action='store_true', help='Explicitly create one small private Drive text file')
    parser.add_argument('--check-gmail', action='store_true', help='Check Gmail token/provider access; does not create or send mail')
    parser.add_argument('--check-calendar', action='store_true', help='Check Calendar token/provider access; does not create an event')
    args = parser.parse_args()
    if not (args.write_drive_probe or args.check_gmail or args.check_calendar):
        parser.error('Choose at least one explicit check')
    if not args.authorized_user_json.is_file():
        parser.error('Authorized-user JSON was not found')
    output = {'drive_probe': None, 'gmail': None, 'calendar': None}
    try:
        if args.write_drive_probe:
            output['drive_probe'] = private_drive_probe(load_credentials(args.authorized_user_json, [DRIVE_SCOPE]))
        if args.check_gmail:
            output['gmail'] = provider_check(load_credentials(args.authorized_user_json, [GMAIL_SCOPE]), 'gmail')
        if args.check_calendar:
            output['calendar'] = provider_check(load_credentials(args.authorized_user_json, [CALENDAR_SCOPE]), 'calendar')
    except Exception as error:
        raise SystemExit('Verification failed: ' + str(error))
    print(json.dumps(output, indent=2))
    print('No email was sent, no calendar event was created, and the Drive probe was not made public.')


if __name__ == '__main__':
    main()
