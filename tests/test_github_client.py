
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from AyadFlowSync.github.client import GitRunner, GitHubAPI

class TestGitRunner:
    def test_has_git_or_not(self):
        # يجب أن يُعيد bool
        result = GitRunner.has_git()
        assert isinstance(result, bool)

    def test_is_git_repo_false(self, tmp_path):
        assert GitRunner.is_git_repo(tmp_path) is False

    def test_is_git_repo_true(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert GitRunner.is_git_repo(tmp_path) is True

    def test_verify_token_empty(self):
        result = GitRunner.verify_token("")
        assert result is False

    def test_kill_no_process(self):
        runner = GitRunner(Path("/tmp"))
        runner.kill()  # يجب ألا يرفع استثناء

class TestGitHubAPI:
    def test_requires_token(self):
        try:
            GitHubAPI("")
            assert False, "Should raise"
        except ValueError:
            pass

    def test_init_with_token(self):
        api = GitHubAPI("fake_token_123")
        assert api is not None
