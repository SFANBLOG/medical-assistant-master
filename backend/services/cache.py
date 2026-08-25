"""Redis 缓存封装：用于缓存检索结果 / 会话，降低重复向量计算与数据库压力。

设计要点：
- Redis 不可用时（未启用、未启动、网络异常）自动降级为「进程内内存缓存」，
  保证主流程始终可用，不会因为缓存层故障而报错。
- 所有值均以 JSON 序列化存储；key 为字符串，value 为可 JSON 序列化的对象。
- 连接仅惰性初始化一次；连接失败后标记禁用，避免每次请求都重试造成堆积。
"""
import json
import threading
import time

from config import Config

_local_cache: dict = {}
_local_lock = threading.Lock()
_client = None  # None=未初始化；False=已确认不可用；否则为 redis 客户端
_client_lock = threading.Lock()


def _enabled() -> bool:
    return Config.REDIS_ENABLE not in ("0", "false", "False", "no")


def _get_client():
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        if not _enabled():
            _client = False
            return None
        try:
            import redis

            c = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                password=Config.REDIS_PASSWORD or None,
                socket_connect_timeout=1,
                socket_timeout=1,
                decode_responses=True,
            )
            c.ping()
            _client = c
            return _client
        except Exception:  # noqa: BLE001 连接失败 -> 降级内存缓存
            _client = False
            return None


def get_json(key):
    """读取缓存；未命中或异常返回 None。"""
    c = _get_client()
    if c is not None:
        try:
            raw = c.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:  # noqa: BLE001
            return None
    # 内存兜底
    with _local_lock:
        item = _local_cache.get(key)
        if item and item[1] > time.time():
            return item[0]
        if item:
            _local_cache.pop(key, None)
    return None


def set_json(key, value, ttl=None) -> None:
    """写入缓存；ttl 缺省使用 Config.REDIS_TTL。"""
    ttl = ttl if ttl is not None else Config.REDIS_TTL
    c = _get_client()
    if c is not None:
        try:
            c.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
            return
        except Exception:  # noqa: BLE001 写入失败不阻塞主流程
            pass
    # 内存兜底
    with _local_lock:
        _local_cache[key] = (value, time.time() + ttl)


def cached_json(key, ttl, producer):
    """缓存读取：命中直接返回；未命中则调用 producer() 生成并写回缓存。"""
    hit = get_json(key)
    if hit is not None:
        return hit
    val = producer()
    if val is not None:
        set_json(key, val, ttl)
    return val


def clear_prefix(prefix: str) -> int:
    """按前缀清理缓存键，返回清理数量（仅 Redis 模式生效）。"""
    c = _get_client()
    if c is None:
        return 0
    try:
        keys = c.keys(f"{prefix}*")
        if keys:
            return c.delete(*keys)
    except Exception:  # noqa: BLE001
        return 0
    return 0
