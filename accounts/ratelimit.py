import time
from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def check_rate_limit(key_prefix, identifier, limit=5, window_seconds=60):
    """
    Returns (is_allowed, seconds_until_reset)
    """
    cache_key = f"rl:{key_prefix}:{identifier}"
    now = time.time()
    timestamps = cache.get(cache_key, [])

    # Filter out timestamps older than window
    timestamps = [t for t in timestamps if now - t < window_seconds]

    if len(timestamps) >= limit:
        oldest = timestamps[0]
        reset_in = int(window_seconds - (now - oldest))
        return False, max(1, reset_in)

    timestamps.append(now)
    cache.set(cache_key, timestamps, window_seconds)
    return True, 0


def ratelimit_view(key_prefix, limit=10, window_seconds=60):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip = get_client_ip(request)
            allowed, reset_in = check_rate_limit(key_prefix, ip, limit=limit, window_seconds=window_seconds)
            if not allowed:
                return HttpResponse(
                    f"Too many requests. Please slow down and try again in {reset_in} seconds.",
                    status=429
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
