"""从仓库入口调用安装包中的记录辅助脚本。"""

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = (
        Path(__file__).resolve().parents[1]
        / "skills/rondel-main/scripts/records.py"
    )
    runpy.run_path(str(target), run_name="__main__")
