"""Lua scripts for atomic commercial-quota enforcement.

Every counter mutation (store token reservation/commit/release and consumer
daily message reservation) runs inside a single Redis EVAL so concurrent
requests cannot overshoot the limit (spec §9, §27).
"""

TOKEN_RESERVE_LUA = """
-- KEYS[1] = ai:quota:{store_id}:{billing_period}   (hash: used, reserved)
-- ARGV[1] = token limit, ARGV[2] = requested budget, ARGV[3] = ttl seconds
local used = tonumber(redis.call('HGET', KEYS[1], 'used') or '0')
local reserved = tonumber(redis.call('HGET', KEYS[1], 'reserved') or '0')
local limit = tonumber(ARGV[1])
local requested = tonumber(ARGV[2])
local available = limit - used - reserved
if available < requested then
    return {0, used, reserved, available}
end
redis.call('HSET', KEYS[1], 'reserved', reserved + requested)
redis.call('EXPIRE', KEYS[1], ARGV[3])
return {1, used, reserved + requested, limit - used - (reserved + requested)}
"""

TOKEN_COMMIT_LUA = """
-- KEYS[1] = ai:quota:{store_id}:{billing_period}
-- ARGV[1] = actual tokens consumed, ARGV[2] = ttl seconds
local used = tonumber(redis.call('HGET', KEYS[1], 'used') or '0')
local reserved = tonumber(redis.call('HGET', KEYS[1], 'reserved') or '0')
local actual = tonumber(ARGV[1])
local new_used = used + actual
local new_reserved = math.max(0, reserved - actual)
redis.call('HSET', KEYS[1], 'used', new_used, 'reserved', new_reserved)
redis.call('EXPIRE', KEYS[1], ARGV[2])
return {new_used, new_reserved}
"""

TOKEN_RELEASE_LUA = """
-- KEYS[1] = ai:quota:{store_id}:{billing_period}
-- ARGV[1] = reserved amount to release, ARGV[2] = ttl seconds
local used = tonumber(redis.call('HGET', KEYS[1], 'used') or '0')
local reserved = tonumber(redis.call('HGET', KEYS[1], 'reserved') or '0')
local release = tonumber(ARGV[1])
local new_reserved = math.max(0, reserved - release)
redis.call('HSET', KEYS[1], 'reserved', new_reserved)
redis.call('EXPIRE', KEYS[1], ARGV[2])
return {used, new_reserved}
"""

CONSUMER_RESERVE_LUA = """
-- KEYS[1] = ai:consumer:{store_id}:{session_id}:{date}
-- ARGV[1] = daily message limit, ARGV[2] = ttl to end of day
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
local limit = tonumber(ARGV[1])
if limit <= 0 then
    return {0, used}
end
if used >= limit then
    return {0, used}
end
redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[2])
return {1, used + 1}
"""

TOKEN_KEY = "ai:quota:{store_id}:{billing_period}"
CONSUMER_KEY = "ai:consumer:{store_id}:{session_id}:{date}"
