from pathlib import Path

import yaml

for path in Path('.github/workflows').glob('*.yml'):
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), path
    assert 'jobs' in data, path
    print(f'{path}: YAML valid; jobs={list(data["jobs"])}')

release = yaml.safe_load(Path('.github/workflows/release.yml').read_text())
assert 'release' in release['jobs']
assert 'docker/build-push-action@v6' in Path('.github/workflows/release.yml').read_text()
print('release workflow contains GHCR build/push')
