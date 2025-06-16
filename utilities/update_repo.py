import os
import shutil
import subprocess


def refresh_repo():
    """Delete /mini_os and clone repo fresh."""
    target = "/mini_os"
    if os.path.isdir(target):
        shutil.rmtree(target)
    subprocess.run([
        "git",
        "clone",
        "https://github.com/paulthomason/mini_os.git",
        target,
    ], check=True)


if __name__ == "__main__":
    refresh_repo()
