"""Read-only adapter smoke check; prints counts and safe failure categories only."""
import argparse
import asyncio
import json
from app.config import settings
from app.db import Session
from app.integrations.clients import Clients, ProviderError
from app.models import Project


async def check(project_id, number=None, provider='all'):
    if provider not in {'all', 'github', 'jira'}:
        raise ProviderError('Unknown provider selection', retryable=False)
    if provider != 'jira' and (type(number) is not int or number < 1):
        raise ProviderError('GitHub check requires a positive PR number', retryable=False)
    with Session() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise ProviderError('Project does not exist', retryable=False)
        client = Clients()
        result = {'mode': settings().mode, 'project_id': project_id, 'read_only': True, 'llm_calls': 0}
        if provider in {'all', 'github'}:
            try:
                pr = await client.pull_request(project.github_repository, number)
            except ProviderError as exc:
                raise ProviderError(f'GitHub PR retrieval: {exc}', retryable=exc.retryable,
                                    retry_after=exc.retry_after) from None
            result['pull_request'] = {'number': pr['number'], 'files': len(pr['files']), 'commits': len(pr['commits'])}
        if provider in {'all', 'jira'}:
            try:
                sprint = await client.sprint(project)
            except ProviderError as exc:
                raise ProviderError(f'Jira sprint retrieval: {exc}', retryable=exc.retryable,
                                    retry_after=exc.retry_after) from None
            result['sprint'] = {'id': sprint['id'], 'issues': len(sprint['issues'])}
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--pr-number', type=int)
    parser.add_argument('--provider', choices=['all', 'github', 'jira'], default='all')
    args = parser.parse_args()
    if args.project_id < 1 or (args.pr_number is not None and args.pr_number < 1):
        parser.error('Project ID and PR number must be positive')
    if args.provider != 'jira' and args.pr_number is None:
        parser.error('--pr-number is required for GitHub/all checks')
    try:
        print(json.dumps(asyncio.run(check(args.project_id, args.pr_number, args.provider)), indent=2))
    except ProviderError as exc:
        parser.exit(1, f'Integration check failed: {exc}\n')


if __name__ == '__main__':
    main()
