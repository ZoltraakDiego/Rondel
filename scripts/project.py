"""从仓库入口调用安装包中的记录辅助脚本。"""

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    target = (
        Path(__file__).resolve().parents[1]
        / "skills/rondel-main/scripts/records.py"
    )
    sys.path.insert(0, str(target.parent))
    runpy.run_path(str(target), run_name="__main__")
