"""deploy/deploy.sh against throwaway git repositories, with stand-ins for gh, sudo, curl and pip."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parent.parent / "deploy" / "deploy.sh"

pytestmark = pytest.mark.skipif(not shutil.which("bash") or not shutil.which("git"), reason="needs bash and git")

STUBS = {
    # CI status for the commit, as `gh run list ... -q` would print it
    "gh": 'echo "${GH_CI-completed success}"\n',
    "sudo": 'echo "sudo $*" >> "$LOG"\n',
    "pip": 'echo "pip $*" >> "$LOG"\n',
    # /health reports the version of the code in the live folder (as after a restart), unless HEALTH_VERSION is set
    "curl": 'v=${HEALTH_VERSION:-$(sed -n \'s/^APP_VERSION = "\\(.*\\)"$/\\1/p\' "$LIVE_DIR/app.py")}\n'
            'echo "{\\"status\\":\\"ok\\",\\"version\\":\\"$v\\"}"\n',
}


class Site:
    def __init__(self, tmp):
        self.tmp = tmp
        self.origin, self.work, self.live = tmp / "origin.git", tmp / "work", tmp / "live"
        self.log = tmp / "log"
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for name, body in STUBS.items():
            stub = bin_dir / name
            stub.write_text("#!/usr/bin/env bash\n" + body)
            stub.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "LIVE_DIR": str(self.live), "SITE": "https://example.test", "PIP": str(bin_dir / "pip"),
            "LOG": str(self.log), "HEALTH_TRIES": "2", "HEALTH_DELAY": "0",
            "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.test",
            "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.test",
        }
        self.git(tmp, "init", "--quiet", "--bare", "--initial-branch=main", str(self.origin))
        self.git(tmp, "clone", "--quiet", str(self.origin), str(self.work))
        self.first = self.release("1.0", "flask==1\n")
        self.git(tmp, "clone", "--quiet", str(self.origin), str(self.live))
        self.log.write_text("")

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def release(self, version, requirements=None):
        """Commits a new APP_VERSION (and optionally requirements) and pushes it to origin/main."""
        (self.work / "app.py").write_text(f'APP_VERSION = "{version}"\n')
        if requirements is not None:
            (self.work / "requirements.txt").write_text(requirements)
        self.git(self.work, "add", ".")
        self.git(self.work, "commit", "--quiet", "-m", f"v{version}")
        self.git(self.work, "push", "--quiet", "origin", "HEAD:main")
        return self.git(self.work, "rev-parse", "HEAD")

    def deploy(self, *args, **env):
        return subprocess.run(["bash", str(DEPLOY), *args], env={**self.env, **env}, capture_output=True, text=True)

    def head(self):
        return self.git(self.live, "rev-parse", "HEAD")

    def calls(self):
        return self.log.read_text().splitlines()


@pytest.fixture
def site(tmp_path):
    return Site(tmp_path)


RESTART = "sudo -n systemctl restart baby-calculator"
PIP_INSTALL = "pip install --quiet -r requirements.txt"


def test_nothing_to_do(site):
    result = site.deploy()
    assert result.returncode == 0 and "nothing to do" in result.stdout
    assert site.calls() == []


def test_deploys_new_version(site):
    new = site.release("2.0")
    result = site.deploy()
    assert result.returncode == 0, result.stderr
    assert site.head() == new
    assert f"live at {new[:7]}, version 2.0" in result.stdout
    assert site.calls() == [RESTART]  # requirements unchanged: no pip


def test_installs_changed_requirements(site):
    site.release("2.0", "flask==2\n")
    assert site.deploy().returncode == 0
    assert site.calls() == [PIP_INSTALL, RESTART]


def test_check_changes_nothing(site):
    site.release("2.0")
    result = site.deploy("--check")
    assert result.returncode == 0 and "nothing changed" in result.stdout
    assert site.head() == site.first and site.calls() == []


@pytest.mark.parametrize("ci", ["in_progress ", "completed failure", ""])
def test_refuses_until_ci_passed(site, ci):
    site.release("2.0")
    result = site.deploy(GH_CI=ci)
    assert result.returncode == 1 and "deploy after it passes" in result.stderr
    assert site.head() == site.first and site.calls() == []


def test_refuses_local_edits(site):
    site.release("2.0")
    (site.live / "app.py").write_text('APP_VERSION = "edited"\n')
    result = site.deploy()
    assert result.returncode == 1 and "uncommitted changes" in result.stderr
    assert site.head() == site.first and site.calls() == []


def test_refuses_diverged_live_folder(site):
    (site.live / "extra.txt").write_text("committed only on the server\n")
    site.git(site.live, "add", ".")
    site.git(site.live, "commit", "--quiet", "-m", "local")
    local = site.head()
    site.release("2.0")
    result = site.deploy()
    assert result.returncode == 1 and "is not part of origin/main" in result.stderr
    assert site.head() == local and site.calls() == []


@pytest.mark.parametrize("requirements, expected_calls", [
    (None, [RESTART, RESTART]),
    ("flask==2\n", [PIP_INSTALL, RESTART, PIP_INSTALL, RESTART]),  # the old requirements are reinstalled too
])
def test_rolls_back_when_health_check_fails(site, requirements, expected_calls):
    site.release("2.0", requirements)
    result = site.deploy(HEALTH_VERSION="1.0")  # the new version never shows up on /health
    assert result.returncode == 1
    assert "rolling back" in result.stderr and f"rolled back, live at {site.first[:7]}" in result.stderr
    assert site.head() == site.first
    assert site.calls() == expected_calls
