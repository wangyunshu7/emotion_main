class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, fields=None):
        self.status, self.code, self.message = status, code, message
        self.fields = fields or []


def missing():
    raise AppError(404, "RESOURCE_NOT_FOUND", "内容不存在或已失效")


def conflict(code="VERSION_CONFLICT", message="内容已变化，请刷新后重试"):
    raise AppError(409, code, message)
