"""Project-wide constants for Family Budget."""

# Session
SESSION_MAX_AGE = 86400 * 30  # 30 days
DEMO_SESSION_MAX_AGE = 3600  # 1 hour

# Login rate limiting
LOGIN_RATE_LIMIT_MAX = 5
LOGIN_RATE_LIMIT_WINDOW = 300  # seconds

# Feedback rate limiting
FEEDBACK_RATE_LIMIT = 5  # max submissions
FEEDBACK_RATE_LIMIT_WINDOW = 3600  # seconds (1 hour)

# Password reset
RESET_TOKEN_EXPIRY_HOURS = 1

# Validation
MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 6
