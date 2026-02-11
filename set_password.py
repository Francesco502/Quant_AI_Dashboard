#!/usr/bin/env python3
"""
密码设置工具
用于生成密码哈希，配合 .env 文件中的 APP_LOGIN_PASSWORD_HASH 使用
"""
import sys
import os
import getpass

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def generate_hash(password: str) -> str:
    """生成 bcrypt 密码哈希"""
    try:
        import bcrypt
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        return password_hash
    except ImportError:
        print("错误：需要安装 bcrypt 库")
        print("请运行: pip install bcrypt")
        sys.exit(1)


def set_password(password: str = None) -> None:
    """生成密码哈希并提示设置到 .env"""
    # 如果没有提供密码，交互式输入
    if password is None:
        password = getpass.getpass("请输入密码: ")
        password_confirm = getpass.getpass("请再次输入密码确认: ")
        
        if password != password_confirm:
            print("错误：两次输入的密码不一致！")
            sys.exit(1)
        
        if not password:
            print("错误：密码不能为空！")
            sys.exit(1)
    
    password_hash = generate_hash(password)
    
    print("\n密码哈希已生成:")
    print(f"  {password_hash}")
    print("\n使用方法:")
    print(f"  1. 在 .env 文件中设置: APP_LOGIN_PASSWORD_HASH={password_hash}")
    print(f"  2. 或设置环境变量: export APP_LOGIN_PASSWORD_HASH=\"{password_hash}\"")
    print("\n提示：重启服务后生效")


def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "hash":
            # 生成密码哈希
            password = sys.argv[2] if len(sys.argv) > 2 else None
            set_password(password)
        
        elif command == "help" or command == "--help":
            print("用法:")
            print("  python set_password.py          # 交互式设置密码")
            print("  python set_password.py hash      # 生成密码哈希")
            print("  python set_password.py hash PWD  # 直接哈希指定密码")
        
        else:
            print(f"未知命令: {command}")
            print("使用 --help 查看帮助")
            sys.exit(1)
    else:
        # 交互式设置
        print("=" * 60)
        print("Quant-AI Dashboard - 密码设置工具")
        print("=" * 60)
        print()
        print("本工具用于生成密码哈希，请将生成的哈希设置到 .env 文件中。")
        print()
        set_password()


if __name__ == "__main__":
    main()
