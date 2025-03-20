



def unstable_api(*args, **kwargs):
    """
    This decorator is used to mark an API as unstable. This means that the API
    is not guaranteed to be stable and may change in the future. It is
    recommended to avoid using unstable APIs in production code.
    """
    def decorator(func):
        return func
    return decorator


def deprecated_api(*args, **kwargs):
    """
    This decorator is used to mark an API as deprecated. This means that the API
    is no longer recommended for use and may be removed in the future. It is
    recommended to avoid using deprecated APIs in new code.
    """
    def decorator(func):
        return func
    return decorator



def experimental_api(*args, **kwargs):
    """
    This decorator is used to mark an API as experimental. This means that the
    API is still in development and may change or be removed in the future.
    It is recommended to avoid using experimental APIs in production code.
    """
    def decorator(func):
        return func
    return decorator


def stable_api(*args, **kwargs):
    """
    This decorator is used to mark an API as stable. This means that the API
    is guaranteed to be stable and will not change in the future. It is
    recommended to use stable APIs in production code.
    """
    def decorator(func):
        return func
    return decorator