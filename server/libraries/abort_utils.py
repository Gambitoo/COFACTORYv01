from threading import Event
from functools import wraps

# Per-user abort events
user_abort_events = {}

def get_user_abort_event(user_id):
    """Get or create abort event for a specific user"""
    if user_id not in user_abort_events:
        user_abort_events[user_id] = Event()
    return user_abort_events[user_id]

def check_abort(user_id):
    """Check if abort has been requested for a specific user and raise exception if so"""
    abort_event = get_user_abort_event(user_id)
    if abort_event.is_set():
        raise AbortedException(f"Algorithm execution was aborted for user {user_id}")

def clear_user_abort_event(user_id):
    """Clear abort event for a specific user"""
    abort_event = get_user_abort_event(user_id)
    abort_event.clear()

def set_user_abort_event(user_id):
    """Set abort event for a specific user"""
    abort_event = get_user_abort_event(user_id)
    abort_event.set()

def cleanup_user_abort_event(user_id):
    """Remove abort event for a user (call when algorithm completes)"""
    if user_id in user_abort_events:
        del user_abort_events[user_id]
    
def abortable_loop(iterable, user_id, check_interval=10):
    """
    Wrapper for loops that checks for abort periodically for a specific user
    
    Args:
        iterable: The iterable to loop over
        user_id: The user ID to check abort for
        check_interval: Check for abort every N iterations
    
    Yields:
        Items from the iterable
    
    Raises:
        AbortedException: If abort is requested for this user
    """
    for i, item in enumerate(iterable):
        if i % check_interval == 0:
            check_abort(user_id)
        yield item
    
class AbortedException(Exception):
    """Custom exception for algorithm abortion"""
    pass