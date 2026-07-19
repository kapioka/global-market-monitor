import importlib.util
import sys
from pathlib import Path


def load_release_package_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "create_release_package.py"
    spec = importlib.util.spec_from_file_location("create_release_package", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generated_and_secret_adjacent_paths_are_excluded():
    module = load_release_package_module()

    assert module.is_excluded("project/reports/report.html")
    assert module.is_excluded("project/cache/historical_prices.csv")
    assert module.is_excluded(".tmp/security/security_audit_summary.json")
    assert module.is_excluded("release/global-market-monitor.zip")
    assert module.is_excluded("docs/visual-evidence/example.png")
    assert module.is_excluded("local.secret.json")
    assert module.is_excluded("deploy.pem")
    assert module.is_excluded("project/cache.db.sqlite3")
    assert module.is_excluded("project/cache.db.sqlite3-wal")
    assert module.is_excluded("project/cache.db.sqlite3-shm")
    assert module.is_excluded("project/cache.db.backup")
    assert module.is_excluded("docs/market_data_storage_baseline.json")
    assert module.is_excluded("docs/market_data_storage_migration_result.json")


def test_source_and_sample_docs_are_included():
    module = load_release_package_module()

    assert not module.is_excluded("README.md")
    assert not module.is_excluded("scripts/create_release_package.py")
    assert not module.is_excluded("docs/sample/sample_report_summary.json")
