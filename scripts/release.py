"""Publish an immutable-version release after the tagged bundle passes checks."""
import json
import os
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from validate import ROOT, check


def main():
    check(release=True)
    version = json.loads((ROOT / 'version.json').read_text())
    tag = 'v' + version['version']
    assert os.environ['GITHUB_REF'] == 'refs/tags/' + tag, 'Tag and contract version differ'
    repository = os.environ['GITHUB_REPOSITORY']
    assert repository == 'forgeturl/studio-integration'
    headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
               'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'}
    base = 'https://api.github.com/repos/' + repository + '/releases'
    try:
        with urlopen(Request(base + '/tags/' + tag, headers=headers), timeout=30):
            print('Release already exists; keeping it unchanged')
            return
    except HTTPError as error:
        if error.code != 404:
            raise
    changelog = (ROOT / 'CHANGELOG.md').read_text()
    body = re.split(r'\n## ', changelog.split('## [' + version['version'] + ']', 1)[1], maxsplit=1)[0]
    payload = {'tag_name': tag, 'name': tag, 'body': body.strip(), 'draft': False,
               'prerelease': version['prerelease'], 'make_latest': 'false' if version['prerelease'] else 'true'}
    with urlopen(Request(base, data=json.dumps(payload).encode(), headers=headers), timeout=30) as response:
        print(json.load(response)['html_url'])


if __name__ == '__main__':
    main()
