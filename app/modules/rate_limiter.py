"""
Simple rate limiter for password reset functionality
"""
import time
from collections import defaultdict, deque
from threading import Lock

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(deque)
        self.lock = Lock()
    
    def is_allowed(self, key, max_requests=3, window_minutes=15):
        """
        Check if a key (IP or email) is allowed to make a request
        Default: 3 requests per 15 minutes
        """
        with self.lock:
            now = time.time()
            window_seconds = window_minutes * 60
            
            # Clean old requests
            while self.requests[key] and now - self.requests[key][0] > window_seconds:
                self.requests[key].popleft()
            
            # Check if limit exceeded
            if len(self.requests[key]) >= max_requests:
                return False
            
            # Add current request
            self.requests[key].append(now)
            return True
    
    def get_remaining_time(self, key, window_minutes=15):
        """Get remaining time in seconds before next request is allowed"""
        with self.lock:
            if not self.requests[key]:
                return 0
            
            oldest_request = self.requests[key][0]
            window_seconds = window_minutes * 60
            elapsed = time.time() - oldest_request
            
            if elapsed >= window_seconds:
                return 0
            
            return int(window_seconds - elapsed)

# Global rate limiter instance
password_reset_limiter = RateLimiter()
