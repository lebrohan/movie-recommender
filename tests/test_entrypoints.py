"""Entry-point behaviour for every pipeline stage, run from a foreign working directory.

- --help works for every stage with no settings at all.
- Every database stage fails fast, before any network, Ollama or database call, when DB_DSN is
  missing.
- ollama_embed_batch resolves the embedding model at call time, not import time.

Run from the repo root:  python -m pytest tests/test_entrypoints.py -q
"""

import pytest

ALL_STAGES = ["setup_db", "load_imdb", "embed", "match", "letterboxd_import", "letterboxd_pipeline"]

# (module, extra args) for the stages that need DB_DSN. match gets a username so it would reach
# the Letterboxd fetch if the DSN check did not come first.
DB_STAGES = [
    ("setup_db", []),
    ("load_imdb", []),
    ("embed", []),
    ("match", ["someuser", "--no-explain"]),
]

# A dead proxy turns any accidental network call into a ProxyError/ConnectionError.
DEAD_PROXY = {"HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}


@pytest.mark.parametrize("module", ALL_STAGES)
def test_help_exits_zero_without_settings(module, repo_root, tmp_path, run_python):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_python("-m", f"backend.{module}", "--help", cwd=elsewhere, pythonpath=repo_root)
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()


@pytest.mark.parametrize("module,args", DB_STAGES)
def test_missing_dsn_fails_fast_before_any_network(module, args, isolated_repo, tmp_path, run_python):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_python("-m", f"backend.{module}", *args, cwd=elsewhere,
                        pythonpath=isolated_repo, env=DEAD_PROXY)
    assert result.returncode != 0
    assert "DB_DSN" in result.stderr
    assert ".env.example" in result.stderr
    assert "ProxyError" not in result.stderr
    assert "ConnectionError" not in result.stderr


def test_ollama_embed_batch_resolves_model_at_call_time(monkeypatch):
    import backend.config as config
    import backend.utils as utils

    seen = {}

    def fake_embed(model, input):
        seen["model"] = model
        return {"embeddings": [[0.0]]}

    monkeypatch.delenv("EMBED_MODEL", raising=False)
    monkeypatch.setattr(config, "ENV_FILE", config.REPO_ROOT / "does-not-exist.env")
    monkeypatch.setattr(utils.ollama, "embed", fake_embed)
    monkeypatch.setenv("EMBED_MODEL", "late-bound-model")
    assert utils.ollama_embed_batch(["x"]) == [[0.0]]
    assert seen["model"] == "late-bound-model"
