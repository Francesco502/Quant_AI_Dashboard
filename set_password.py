#!/usr/bin/env python3
"""
密码设置工具
用于将密码保存到本地配置文件，避免使用系统环境变量
"""
import sys
import os
import json
import getpass

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def set_password(password: str = None, use_hash: bool = False) -> None:
    """设置登录密码并保存到配置文件"""
    config_file = os.path.join(".streamlit", "login_config.json")
    
    # 确保目录存在
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
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
    
    config = {}
    
    if use_hash:
        # 使用 bcrypt 哈希
        try:
            import bcrypt
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            config["password_hash"] = password_hash
            print(f"密码哈希已生成并保存到: {config_file}")
            print("提示：下次启动时，系统会自动从配置文件读取密码")
        except ImportError:
            print("错误：需要安装 bcrypt 库")
            print("请运行: pip install bcrypt")
            sys.exit(1)
    else:
        # 使用明文密码（不推荐用于生产环境）
        config["password"] = password
        print(f"密码已保存到: {config_file}")
        print("提示：下次启动时，系统会自动从配置文件读取密码")
        print("警告：明文密码仅适合开发/测试环境，生产环境请使用哈希模式")
    
    # 保存配置
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print("配置已保存成功！")
    except Exception as e:
        print(f"保存配置失败: {e}")
        sys.exit(1)


def clear_password() -> None:
    """清除已保存的密码配置"""
    config_file = os.path.join(".streamlit", "login_config.json")
    if os.path.exists(config_file):
        try:
            os.remove(config_file)
            print("密码配置已清除")
        except Exception as e:
            print(f"清除配置失败: {e}")
            sys.exit(1)
    else:
        print("未找到密码配置文件")


def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "set":
            use_hash = "--hash" in sys.argv or "-h" in sys.argv
            password = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
            set_password(password, use_hash)
        
        elif command == "clear":
            clear_password()
        
        elif command == "hash":
            # 生成密码哈希
            if len(sys.argv) > 2:
                password = sys.argv[2]
            else:
                password = getpass.getpass("请输入密码: ")
            
            try:
                import bcrypt
                salt = bcrypt.gensalt()
                password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
                print("\n密码哈希:")
                print(password_hash)
                print("\n使用方法:")
                print(f"  python set_password.py set --hash")
                print(f"  或设置环境变量: APP_LOGIN_PASSWORD_HASH={password_hash}")
            except ImportError:
                print("错误：需要安装 bcrypt 库")
                print("请运行: pip install bcrypt")
                sys.exit(1)
        
        else:
            print(f"未知命令: {command}")
            sys.exit(1)
    else:
        # 交互式设置
        print("=" * 60)
        print("Quant-AI Dashboard - 密码设置工具")
        print("=" * 60)
        print()
        print("请选择操作：")
        print("  1. 设置密码（明文，保存到配置文件）")
        print("  2. 设置密码（哈希，保存到配置文件，推荐）")
        print("  3. 清除已保存的密码")
        print("  4. 仅生成密码哈希（不保存）")
        print()
        choice = input("请选择 (1/2/3/4): ").strip()
        
        if choice == "1":
            set_password(use_hash=False)
        elif choice == "2":
            set_password(use_hash=True)
        elif choice == "3":
            clear_password()
        elif choice == "4":
            password = getpass.getpass("请输入密码: ")
            try:
                import bcrypt
                salt = bcrypt.gensalt()
                password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
                print("\n密码哈希:")
                print(password_hash)
            except ImportError:
                print("错误：需要安装 bcrypt 库")
                sys.exit(1)
        else:
            print("无效选择")
            sys.exit(1)


if __name__ == "__main__":
    main()

