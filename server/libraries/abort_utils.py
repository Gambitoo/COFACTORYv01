from threading import Event
from functools import wraps

# Shared abort event
abort_event = Event()

def check_abort():
    """Check if abort has been requested and raise exception if so"""
    if abort_event.is_set():
        raise AbortedException("Algorithm execution was aborted")
    
def abortable_loop(iterable, check_interval=10):
    """
    Wrapper for loops that checks for abort periodically
    
    Args:
        iterable: The iterable to loop over
        check_interval: Check for abort every N iterations
    
    Yields:
        Items from the iterable
    
    Raises:
        AbortedException: If abort is requested
    """
    for i, item in enumerate(iterable):
        if i % check_interval == 0:
            check_abort()
        yield item
    
class AbortedException(Exception):
    """Custom exception for algorithm abortion"""
    pass