from unittest.mock import MagicMock

import redis

from src.api.state import RedisDictProxy, RedisListProxy, RedisSubDictProxy


def test_redis_dict_proxy_degradation():
    """Verify RedisDictProxy falls back to local in-memory dict when Redis operations fail."""
    # Initialize proxy with mocked redis client that raises errors
    proxy = RedisDictProxy(key_prefix="test_dict")
    proxy.redis = MagicMock()

    # Configure mock to raise a Redis ConnectionError
    proxy.redis.exists.side_effect = redis.exceptions.ConnectionError("Redis down")
    proxy.redis.get.side_effect = redis.exceptions.ConnectionError("Redis down")
    proxy.redis.set.side_effect = redis.exceptions.ConnectionError("Redis down")
    proxy.redis.delete.side_effect = redis.exceptions.ConnectionError("Redis down")

    # Set value (should fall back to local_dict)
    proxy["test_key"] = "test_value"
    assert proxy.local_dict["test_key"] == "test_value"

    # Get value (should fall back to local_dict)
    assert proxy["test_key"] == "test_value"

    # Contains check (should fall back to local_dict)
    assert "test_key" in proxy

    # Pop value (should fall back to local_dict)
    val = proxy.pop("test_key")
    assert val == "test_value"
    assert "test_key" not in proxy


def test_redis_sub_dict_proxy_degradation():
    """Verify RedisSubDictProxy falls back to local in-memory sub-dict when Redis fails."""
    parent = RedisDictProxy(key_prefix="test_parent", return_sub_proxy=True)
    parent.redis = MagicMock()
    parent.redis.delete.side_effect = redis.exceptions.TimeoutError("Redis timed out")
    parent.redis.hset.side_effect = redis.exceptions.TimeoutError("Redis timed out")
    parent.redis.hget.side_effect = redis.exceptions.TimeoutError("Redis timed out")
    parent.redis.hgetall.side_effect = redis.exceptions.TimeoutError("Redis timed out")
    parent.redis.hlen.side_effect = redis.exceptions.TimeoutError("Redis timed out")
    parent.redis.hexists.side_effect = redis.exceptions.TimeoutError("Redis timed out")

    # Fetch sub-proxy
    sub_proxy = parent["run_1"]
    assert isinstance(sub_proxy, RedisSubDictProxy)

    # Set item
    sub_proxy["field_1"] = "val_1"
    assert parent.local_dict["run_1"]["field_1"] == "val_1"

    # Get item
    assert sub_proxy["field_1"] == "val_1"

    # Contains check
    assert "field_1" in sub_proxy

    # Length check
    assert len(sub_proxy) == 1

    # Update check
    sub_proxy.update({"field_2": "val_2"})
    assert parent.local_dict["run_1"]["field_2"] == "val_2"


def test_redis_list_proxy_degradation():
    """Verify RedisListProxy and RedisListHelper fall back to local list on failure."""
    proxy = RedisListProxy(key_prefix="test_list")
    proxy.redis = MagicMock()
    proxy.redis.delete.side_effect = redis.exceptions.RedisError("General failure")
    proxy.redis.rpush.side_effect = redis.exceptions.RedisError("General failure")
    proxy.redis.lrange.side_effect = redis.exceptions.RedisError("General failure")
    proxy.redis.llen.side_effect = redis.exceptions.RedisError("General failure")
    proxy.redis.lindex.side_effect = redis.exceptions.RedisError("General failure")
    proxy.redis.exists.side_effect = redis.exceptions.RedisError("General failure")

    # Set list
    proxy["list_1"] = ["item_a", "item_b"]
    assert proxy.local_dict["list_1"] == ["item_a", "item_b"]

    # Append list item via helper
    helper = proxy["list_1"]
    helper.append("item_c")
    assert proxy.local_dict["list_1"] == ["item_a", "item_b", "item_c"]

    # Length check
    assert len(helper) == 3

    # Slice check
    assert helper[0:2] == ["item_a", "item_b"]

    # Pop list
    popped = proxy.pop("list_1")
    assert popped == ["item_a", "item_b", "item_c"]
