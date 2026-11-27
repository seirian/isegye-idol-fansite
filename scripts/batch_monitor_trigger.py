"""Validate a completed, same-repository main workflow before reading evidence."""
from pathlib import Path
import json, os, subprocess

REPO = 'seirian/isegye-idol-fansite'
COMPLETIONS = {
    'Albums - hourly verified metadata and chart refresh':'albums-daily.yml',
    'Music - daily verified catalog refresh':'music-daily.yml',
    'Schedule - every 2 hours permitted-source refresh':'schedule-refresh.yml',
    'Content - verified channel video catalog':'video-catalog.yml',
    'Playground - daily verified question bank':'playground-daily.yml',
    'History - weekly verified activity refresh':'history-monthly.yml',
    'Production - isolated inour SFTP deployment':'production.yml',
    'Batches - verified outcome recovery watchdog':'batch-watchdog.yml',
    'Melon charts - independent lightweight evidence capture':'melon-chart-capture.yml',
}


def validate(event, getter):
    source = event.get('workflow_run', {})
    if (event.get('action') != 'completed' or source.get('name') not in COMPLETIONS or
        source.get('head_branch') != 'main' or source.get('head_repository', {}).get('full_name') != REPO or
        type(source.get('id')) is not int or source['id'] <= 0):
        raise ValueError('Untrusted monitoring wake-up')
    run = getter(source['id'])
    if (run.get('id') != source['id'] or run.get('name') != source['name'] or
        run.get('head_branch') != 'main' or run.get('repository', {}).get('full_name') != REPO or
        run.get('head_repository', {}).get('full_name') != REPO or
        run.get('path') != '.github/workflows/'+COMPLETIONS[source['name']] or
        run.get('status') != 'completed' or
        run.get('event') not in ('push','schedule','workflow_dispatch','workflow_run')):
        raise ValueError('Untrusted completed run')
    # All completed conclusions are important, not only success.
    return True


def get_run(run_id):
    result = subprocess.run(['gh','api','--method','GET',f'repos/{REPO}/actions/runs/{run_id}'],
                            capture_output=True, timeout=30, check=True)
    return json.loads(result.stdout)


if __name__ == '__main__':
    if os.getenv('GITHUB_REPOSITORY') != REPO or os.getenv('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Main repository required')
    if os.getenv('GITHUB_EVENT_NAME') == 'workflow_run':
        validate(json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text()), get_run)
    print('Trusted monitoring trigger; no batch dispatched')
