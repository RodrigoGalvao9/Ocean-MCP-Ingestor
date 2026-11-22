"""Cliente HTTP com timeout e novas tentativas controlados (toda fonte externa usa isto)."""

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

USER_AGENT = "ocean-maritime/0.1 (+https://github.com/RodrigoGalvao9/Ocean-MCP-Ingestor)"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class SourceUnavailable(RuntimeError):
    """A fonte externa não respondeu de forma utilizável (após as novas tentativas)."""

    def __init__(
        self, message: str, *, status_code: int | None = None, retry_after: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def build_client(**kwargs) -> httpx.Client:
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("follow_redirects", True)
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    return httpx.Client(headers=headers, **kwargs)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code >= 500
    return False


@retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    reraise=True,
)
def _send(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    response = client.request(method, url, **kwargs)
    response.raise_for_status()
    return response


def request(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    """Faz a requisição com até 3 tentativas; falha vira SourceUnavailable."""
    try:
        return _send(client, method, url, **kwargs)
    except httpx.HTTPError as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            raise SourceUnavailable(
                f"{method} {url}: {exc}",
                status_code=exc.response.status_code,
                retry_after=exc.response.headers.get("Retry-After"),
            ) from exc
        raise SourceUnavailable(f"{method} {url}: {exc}") from exc
