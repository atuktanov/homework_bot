class HTTPError(Exception):
    """Ошибка кода состояния HTTP."""

    pass


class JSONDecodeError(ValueError):
    """Ошибка декодирования JSON."""

    pass


class APIFormatError(TypeError, KeyError):
    """Ошибка формата ответа API."""

    pass


class StatusError(KeyError):
    """Ошибка статуса ДЗ."""

    pass


class EnvVarsError(NameError):
    """Ошибка переменных окружения."""

    pass
