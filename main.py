import ok
import sys
import os
import traceback
from src.config import apply_frozen_runtime_paths, config
from src.ui.SponsorDialog import install_sponsor_dialog

if __name__ == '__main__':
    try:
        install_sponsor_dialog()
        # PyInstaller --onefile mode: 数据在临时目录，配置/日志/截图保存在 exe 旁
        config = apply_frozen_runtime_paths(config)
        ok = ok.OK(config)
        ok.start()
    except Exception as e:
        log_path = os.path.join(os.path.dirname(sys.executable), "error.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Error: {e}\n\n")
            traceback.print_exc(file=f)
        raise
