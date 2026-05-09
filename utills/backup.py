# utills/backup.py
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

# 备份文件存放目录
BACKUP_DIR = Path("db_backups")
# 保留最近 7 天的备份
RETENTION_DAYS = 7
# 假设系统 PATH 里有 mysqldump，如果没有就用绝对路径（Windows 可能要用 mysqldump.exe）
# MYSQLDUMP_BIN = "mysqldump"
# 本地测试改成从环境变量读取，如果有的话就用绝对路径，否则还是用 PATH 里的
MYSQLDUMP_BIN = os.getenv("MYSQLDUMP_PATH", "mysqldump")


def _get_db_config():
    """
    从环境变量里提取数据库连接信息。
    优先使用 DB_HOST, DB_PORT ...，如果没有再用 DATABASE_URL 解析。
    返回 (host, port, user, password, database)
    """
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    # 如果上面有任何一个缺少，尝试从 DATABASE_URL 解析
    if not all([host, port, user, password is not None, database]):
        db_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL", "")
        if db_url:
            try:
                parsed = urlparse(db_url)
                host = parsed.hostname or "127.0.0.1"
                port = str(parsed.port or 3306)
                user = parsed.username or "root"
                password = parsed.password or ""
                database = parsed.path.lstrip("/") or "vitalis"
            except Exception:
                pass

    # 信息不全就报错
    if not all([host, port, user, password is not None, database]):
        raise RuntimeError(
            "数据库连接信息不完整，请在 .env 中设置 DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME "
            "或提供有效的 DATABASE_URL"
        )
    return host, port, user, password, database


def _ensure_my_cnf(user, password, host, port):
    """
    在用户主目录下生成 ~/.my.cnf 文件，让 mysqldump 可以免密连接。
    这样就不用在命令行里暴露密码了。
    如果文件已存在且内容一样则跳过。
    """
    cnf_path = Path.home() / ".my.cnf"
    content = (
        "[client]\n"
        f"user={user}\n"
        f"password={password}\n"
        f"host={host}\n"
        f"port={port}\n"
    )

    need_write = False
    if cnf_path.exists():
        try:
            existing = cnf_path.read_text(encoding="utf-8")
            if existing.strip() != content.strip():
                need_write = True
        except Exception:
            need_write = True
    else:
        need_write = True

    if need_write:
        cnf_path.write_text(content, encoding="utf-8")
        # 在非 Windows 系统下，把权限改成只有当前用户可读写（安全要求）
        if os.name != "nt":
            os.chmod(cnf_path, 0o600)


def _cleanup_old_backups():
    """删除超过 7 天的旧备份文件"""
    if not BACKUP_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for f in BACKUP_DIR.iterdir():
        if not f.is_file():
            continue
        try:
            # 文件名格式：vitalis_backup_数据库名_年月日_时分秒.sql.gz
            # 例如：vitalis_backup_vitalis_20250509_020000.sql.gz
            stem = f.stem  # 去掉 .gz （比如 "vitalis_backup_vitalis_20250509_020000.sql"）
            # 对于 .sql.gz 文件，stem 是 "xxx.sql"，需要去掉最后的 .sql
            if stem.endswith('.sql'):
                stem = stem[:-4]
            parts = stem.split("_")
            # 最后两部分一定是 日期 和 时间
            if len(parts) >= 2:
                timestamp_str = parts[-2] + "_" + parts[-1]
                file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                if file_time < cutoff:
                    f.unlink()   # 删除文件
                    print(f"[备份清理] 删除过期备份: {f.name}")
        except (ValueError, IndexError):
            pass


def perform_backup():
    """
    执行一次数据库备份：
    1. 检查 mysqldump 是否存在
    2. 生成 ~/.my.cnf
    3. 执行 mysqldump，通过管道交给 gzip 压缩
    4. 写入 db_backups/ 目录
    5. 清理过期备份
    """
    # 检查 MYSQLDUMP_BIN 是否可执行
    if os.path.isfile(MYSQLDUMP_BIN):
        # 如果是绝对路径就直接用
        pass
    else:
        # 否则在 PATH 里找
        # 检查 mysqldump 命令是否可用
        if shutil.which(MYSQLDUMP_BIN) is None:
            raise RuntimeError(
                f"找不到 {MYSQLDUMP_BIN}，请安装 MySQL 客户端工具并加入 PATH"
            )

    host, port, user, password, database = _get_db_config()
    _ensure_my_cnf(user, password, host, port)

    # 创建备份目录
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    base_name = f"vitalis_backup_{database}_{timestamp}"

    # 构造 mysqldump 命令（使用 --defaults-file 指定配置文件，免密）
    dump_cmd = (
        f'"{MYSQLDUMP_BIN}" '
        f'--defaults-file="{Path.home() / ".my.cnf"}" '
        f'--default-character-set=utf8mb4 '    # ← 强制 utf8mb4，防止 emoji 丢失
        f'--single-transaction '               # ← 保证备份一致性（InnoDB）
        f'--routines '                         # ← 包含存储过程
        f'--triggers '                         # ← 包含触发器
        f'--databases {database}'
    )

    # 如果系统里有 gzip，就压缩备份文件（推荐）
    gzip_available = shutil.which("gzip") is not None

    if gzip_available:
        backup_file = BACKUP_DIR / f"{base_name}.sql.gz"
        print(f"[备份] 开始压缩备份数据库 {database} -> {backup_file}")
        # 打开目标文件，准备写入
        with open(backup_file, "wb") as f_out:
            # 启动两个子进程：mysqldump 和 gzip，用管道连接
            proc_dump = subprocess.Popen(
                dump_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            proc_gzip = subprocess.Popen(
                ["gzip"],
                stdin=proc_dump.stdout,
                stdout=f_out,
                stderr=subprocess.PIPE,
            )
            # 让 mysqldump 的 stdout 由 gzip 接管
            if proc_dump.stdout:
                proc_dump.stdout.close()

            # 等待两个进程都结束
            _, dump_stderr = proc_dump.communicate()
            _, gzip_stderr = proc_gzip.communicate()

            if proc_dump.returncode != 0:
                err_msg = dump_stderr.decode("utf-8", errors="ignore") if dump_stderr else "未知错误"
                raise RuntimeError(f"mysqldump 失败: {err_msg}")
            if proc_gzip.returncode != 0:
                err_msg = gzip_stderr.decode("utf-8", errors="ignore") if gzip_stderr else "未知错误"
                raise RuntimeError(f"gzip 压缩失败: {err_msg}")
    else:
        # 没有 gzip，直接保存为 .sql 文件
        backup_file = BACKUP_DIR / f"{base_name}.sql"
        print(f"[备份] gzip 不可用，保存为未压缩文件 -> {backup_file}")
        result = subprocess.run(
            dump_cmd,
            shell=True,
            capture_output=True,
            encoding="utf-8",  # 强制用 utf-8 解码 stdout / stderr
            errors="replace",  # 遇到无法解码的字节用 ? 代替，绝不抛异常
        )
        if result.returncode != 0:
            raise RuntimeError(f"mysqldump 失败: {result.stderr}")
        backup_file.write_text(result.stdout, encoding="utf-8")

    print(f"[备份] 成功备份至 {backup_file}")
    _cleanup_old_backups()
    return backup_file


# # 如果直接运行这个文件，就执行一次备份（方便手动测试）
# if __name__ == "__main__":
#     perform_backup()