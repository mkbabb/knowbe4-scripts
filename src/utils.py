import pathlib
from functools import wraps
from itertools import chain
from pathlib import Path
from typing import Callable, Iterable, ParamSpec, TypeVar

import requests
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from requests import Session

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json;charset=utf-8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Safari/605.1.15",
    "X-CSRF-Token": "undefined",
    "X-Requested-With": "XMLHttpRequest",
}

LOGIN_URL = "https://training.knowbe4.com/spa/auth/login"

SESSION_URL = " https://training.knowbe4.com/spa/session"

GRAPH_QL_URL = "https://training.knowbe4.com/graphql"

QUERY_DIR = pathlib.Path("queries")

P = ParamSpec("P")
R = TypeVar("R")

PAGINATION_PER = 25
PAGINATION_START = 1


def create_gql_client(creds: dict) -> Client:
    with requests.Session() as s:
        s.headers.update(DEFAULT_HEADERS)
        s.post(LOGIN_URL, json=creds)

        csrf = get_csrf_token(s)
        s.headers.update({"X-CSRF-Token": csrf})

        transport = RequestsHTTPTransport(
            url=GRAPH_QL_URL,
            headers=s.headers,  # type: ignore
            cookies=s.cookies,
            use_json=True,
        )
        client = Client(transport=transport, fetch_schema_from_transport=True)
        return client


def get_csrf_token(s: Session):
    r = s.get(SESSION_URL)
    session_data = r.json()
    return session_data["kmsat"]["csrf"]


def find_arg_by_type(
    args: Iterable,
    kwargs: dict,
    type_: type,
) -> object:
    for arg in chain(args, kwargs.values()):
        if isinstance(arg, type_):
            return arg

    raise ValueError(f"Could not find an argument of type {type_}.")


def graphql_query(decorated_fn: Callable[P, R]) -> Callable[P, R]:
    @wraps(decorated_fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        query_file_name = f"{decorated_fn.__name__}.graphql"
        query_path = QUERY_DIR / query_file_name

        if not query_path.exists():
            raise FileNotFoundError(
                f"{query_file_name} does not exist in the defined QUERY_DIR."
            )

        query = gql(query_path.read_text())
        ret = decorated_fn(*args, **kwargs)

        client = find_arg_by_type(args, kwargs, Client)

        return client.execute(query, **ret)

    return wrapper


def paginated_query(query_fn: Callable[..., dict]) -> Callable[..., Iterable[dict]]:
    @wraps(query_fn)
    def wrapper(
        client: Client, per: int = PAGINATION_PER, page: int = PAGINATION_START
    ) -> Iterable[dict]:
        result_key = query_fn.__name__

        while True:
            result = query_fn(
                per=per,
                page=page,
                client=client,
            )

            yield from result[result_key]["nodes"]

            if (
                result[result_key]["pagination"]["page"]
                == result[result_key]["pagination"]["pages"]
            ):
                break

            page += 1

    return wrapper
