"""启动后台守护进程脚本
"""
import sys
import os

# 将当前目录加入 path，确保能找到 core
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.daemon import main

if __name__ == "__main__":
    print("正在启动后台守护进程...")
    print("按 Ctrl+C 停止")
    try:
        main()
    except KeyboardInterrupt:
        print("已停止")
