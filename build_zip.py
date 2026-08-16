"""打包安装包 zip：排除敏感/生成文件，输出 homework-reminder.zip。

用法:
    python build_zip.py
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 打进安装包的文件/目录（相对项目根）
INCLUDE = [
    "安装.bat",
    "卸载.bat",
    "使用说明.txt",
    "install.py",
    "refresh_cookies.py",
    "check_username.py",
    "requirements.txt",
    "config.example.json",
    "README.md",
    "LICENSE",
    "src",  # 整个源码包
]


def should_skip(rel: str) -> bool:
    """跳过缓存/敏感文件（config.json 不在 INCLUDE，无需处理）。"""
    parts = Path(rel).parts
    if "__pycache__" in parts:
        return True
    return rel.endswith(".pyc")


def main() -> int:
    out_name = "homework-reminder.zip"
    out_path = ROOT / out_name

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in INCLUDE:
            p = ROOT / item
            if p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file():
                        rel = f.relative_to(ROOT).as_posix()
                        if should_skip(rel):
                            continue
                        zf.write(f, rel)
            elif p.is_file():
                zf.write(p, p.relative_to(ROOT).as_posix())
            else:
                print(f"跳过不存在的项: {item}")
    print(f"已打包: {out_name} ({out_path.stat().st_size} 字节)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
