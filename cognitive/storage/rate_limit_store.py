"""
跨进程共享限流（SQLite 实现，零第三方依赖）。

为什么不用 Redis：
- 本项目是本地单用户系统，硬约束是"不引入 Redis/Celery/RQ"；
- SQLite 的写事务（BEGIN IMMEDIATE）本身就是跨进程互斥锁——同一时刻只有一个
  进程能拿到保留锁，因此"检查-追加"可在事务里原子完成，多进程不会放大额度。

数据模型：每次放行记一行 (key, hit_ts)；判定时数最近 window 秒内的行数。
- 不用"一个 key 存一个 JSON 数组"的方案：那需要读-改-写整块覆盖，并发会丢更新；
- 每行一条记录可以被多次 INSERT 累加，天然并发安全。

时间来源：调用方传入 now（秒），便于离线测试；线上用 time.time()。
窗口单位固定为秒。
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

import config


class SQLiteRateLimiter:
    """基于 SQLite 写事务的跨进程滑动窗口限流器。"""

    def __init__(self, db_path: Optional[Path] = None, window: float = 60.0) -> None:
        """
        :param db_path: 数据库文件；缺省 config.RATE_LIMIT_DB_PATH
        :param window: 滑动窗口长度（秒）
        """
        self.db_path = Path(db_path or config.RATE_LIMIT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.window = float(window)
        self._local = threading.local()
        self._connections: "dict[int, sqlite3.Connection]" = {}
        self._registry_lock = threading.Lock()
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        """当前线程的独立连接（isolation_level=None 便于显式控制事务）。"""
        connection = getattr(self._local, "conn", None)
        if connection is not None:
            return connection

        connection = sqlite3.connect(
            str(self.db_path),
            timeout=30,
            isolation_level=None,          # 关闭隐式事务，自己 BEGIN/COMMIT
            check_same_thread=False,        # 由 threading.local 保证单线程使用
        )
        # 不设 row_factory 时 fetchone() 返回 tuple，row["cnt"] 会 TypeError
        connection.row_factory = sqlite3.Row
        connection.execute("pragma journal_mode=wal")
        connection.execute("pragma busy_timeout=30000")
        self._local.conn = connection
        with self._registry_lock:
            self._connections[threading.get_ident()] = connection
        return connection

    def _init_schema(self) -> None:
        connection = self._conn()
        connection.execute(
            """
            create table if not exists rate_limit_hit (
                key     text not null,
                hit_ts  real not null
            )
            """
        )
        connection.execute(
            "create index if not exists idx_rate_limit_hit_key_ts"
            " on rate_limit_hit(key, hit_ts)"
        )

    def allow(self, key: str, now: float, max_calls: int) -> bool:
        """
        尝试放行一次请求。

        :param key: 来源标识（如 remote_addr）
        :param now: 当前时间戳（秒）
        :param max_calls: 窗口内最大次数；<=0 表示不限流
        :return: True 放行，False 超限
        """
        if not max_calls or max_calls <= 0:
            return True

        connection = self._conn()
        cutoff = float(now) - self.window
        # BEGIN IMMEDIATE 会立刻拿到写锁，把"清理 → 计数 → 插入"串成一个原子操作。
        # 多进程同时调用时，其余进程会阻塞在拿锁上，拿到后看到的是已提交的计数。
        connection.execute("BEGIN IMMEDIATE")
        try:
            # 顺带清理所有 key 的过期行，避免表无限增长
            connection.execute(
                "delete from rate_limit_hit where hit_ts <= ?", (cutoff,)
            )
            row = connection.execute(
                "select count(1) as cnt from rate_limit_hit"
                " where key = ? and hit_ts > ?",
                (key, cutoff),
            ).fetchone()
            count = int(row["cnt"]) if row else 0
            if count >= int(max_calls):
                connection.execute("rollback")
                return False

            connection.execute(
                "insert into rate_limit_hit (key, hit_ts) values (?, ?)",
                (key, float(now)),
            )
            connection.execute("commit")
            return True
        except Exception:
            try:
                connection.execute("rollback")
            except Exception:
                pass
            raise

    def close_all_connections(self) -> None:
        """关闭所有线程的连接（Windows 上临时库清理必需）。"""
        with self._registry_lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            try:
                connection.close()
            except Exception:
                pass
