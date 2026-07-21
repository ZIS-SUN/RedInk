"""跨运行环境备份/恢复演练脚本的端到端测试。"""

import os
import subprocess
import threading
from pathlib import Path

from werkzeug.serving import make_server


def test_backup_restore_drill_round_trips_data_and_local_storage(
    monkeypatch,
    tmp_path: Path,
):
    """演练脚本应通过真实 HTTP API 验证 v2 备份、恢复与全量替换语义。"""
    data_root = tmp_path / "data"
    monkeypatch.setenv("REDINK_DATA_DIR", str(data_root))

    # 发布账号服务是进程级单例；确保本测试实例绑定到隔离数据目录。
    from backend.services import publish

    monkeypatch.setattr(publish, "_service_instance", None)

    from backend.app import create_app

    app = create_app()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "drill-backup-restore.sh"
    env = os.environ.copy()

    try:
        result = subprocess.run(
            ["bash", str(script), f"http://127.0.0.1:{server.server_port}"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        publish._service_instance = None

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "RESULT: PASS" in output
    assert "manifest v2" in output
    assert "localStorage" in output
