
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from AyadFlowSync.github.ops import ProjectInspector, LFS, Auth

class TestProjectInspector:
    def test_detect_python(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests\n")
        r = ProjectInspector.inspect(tmp_path)
        assert r["type"] == "Python"
        assert r["language"] == "Python"

    def test_detect_nodejs(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"express": "^4"}}))
        r = ProjectInspector.inspect(tmp_path)
        assert r["type"] == "Node.js"

    def test_detect_unknown(self, tmp_path):
        r = ProjectInspector.inspect(tmp_path)
        assert r["type"] == "Unknown"

    def test_counts_files(self, tmp_path):
        for i in range(5):
            (tmp_path / f"file{i}.txt").write_text("x")
        r = ProjectInspector.inspect(tmp_path)
        assert r["files"] == 5

    def test_detects_git(self, tmp_path):
        r = ProjectInspector.inspect(tmp_path)
        assert r["has_git"] is False
        (tmp_path / ".git").mkdir()
        r2 = ProjectInspector.inspect(tmp_path)
        assert r2["has_git"] is True

    def test_detects_readme(self, tmp_path):
        (tmp_path / "README.md").write_text("# hi")
        r = ProjectInspector.inspect(tmp_path)
        assert r["readme"] == "README.md"

    def test_deep_python_libs(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests\nxxhash\npsutil\n")
        r = ProjectInspector.inspect(tmp_path, deep=True)
        assert "requests" in r["libraries"]

    def test_large_files_detection(self, tmp_path):
        small = tmp_path / "small.txt"
        small.write_bytes(b"x")
        large = tmp_path / "large.bin"
        large.write_bytes(b"x" * (91 * 1024 * 1024))  # 91MB
        found = LFS.detect_large_files(tmp_path, limit_mb=90)
        assert large in found
        assert small not in found

class TestAuth:
    def test_save_and_load(self, tmp_path):
        import AyadFlowSync.github.ops as ops_mod
        ops_mod.Auth._TOKEN_FILE = tmp_path / ".gh_token"
        Auth.save("test_token_abc")
        assert Auth.load() == "test_token_abc"
        Auth.clear()
        assert Auth.load() == ""
