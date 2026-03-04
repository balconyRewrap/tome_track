from rest_framework.throttling import AnonRateThrottle


class RegisterThrottle(AnonRateThrottle):
    scope = "register"

class LoginThrottle(AnonRateThrottle):
    scope = "login"

class PasswordResetThrottle(AnonRateThrottle):
    scope = "password_reset"