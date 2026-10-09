"""Per-application proxy settings and safe provider error messages."""
import os

import httpx


def trust_environment():
    return os.getenv('SOUNDTRACE_HTTP_TRUST_ENV', 'true').lower() not in ('false', '0', 'no')


def provider_error(error, service):
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        reason = {400: '请求参数或模型配置无效', 401: 'API Key 无效或已失效',
                  402: 'API 余额不足', 403: '账号或模型权限未开通',
                  404: '模型或服务地址不存在', 429: '请求过于频繁或额度不足'}.get(status)
        return f'{service}：{reason or "上游服务暂时不可用"}（HTTP {status}）；请确认后再重试'
    if isinstance(error, httpx.TimeoutException):
        return f'{service}响应超时，请确认上游任务状态后再重试，避免重复计费'
    if isinstance(error, httpx.RequestError):
        return f'{service}连接失败，请检查服务端网络与代理设置'
    return str(error) if isinstance(error, RuntimeError) else f'{service}返回异常，原始素材已保留'
