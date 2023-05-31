import json
import pathlib
import time

import pandas as pd
import requests
from googleapiutils2 import Sheets, SheetSlice, get_oauth2_creds
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

SHEET_URL = "https://docs.google.com/spreadsheets/d/14WRf-S-T5MFkk4zOm0Ejsr-3g83EYEQ6dUle9VrDp6I/edit#gid=0"


def get_csrf_token(s: Session):
    r = s.get(SESSION_URL)
    session_data = r.json()
    return session_data["kmsat"]["csrf"]


def get_accounts(client: Client, per: int = 25, page: int = 1):
    query_path = QUERY_DIR / "accounts_query.graphql"
    query = gql(query_path.read_text())

    while True:
        result = client.execute(
            query,
            variable_values={
                "per": per,
                "page": page,
                "search": "",
                "archivedUsers": False,
                "status": "ACTIVE",
                "billingType": "ANY",
                "sortField": "ORGANIZATION",
                "sortDirection": "ASCENDING",
                "otherPartnersAccounts": "ALL",
            },
        )

        yield from result["accounts"]["nodes"]

        if (
            result["accounts"]["pagination"]["page"]
            == result["accounts"]["pagination"]["pages"]
        ):
            break

        page += 1


def get_account_info(id: int, client: Client):
    query_path = QUERY_DIR / "account_info_query.graphql"
    query = gql(query_path.read_text())

    return client.execute(query, variable_values={"id": id})


def parse_account_data(account_info: dict):
    account_data = account_info["account"]

    pretty_names_payload = {
        "Phishing Available": account_data.get("hasPhishing"),
        "AIDA Selected Templates Available": account_data.get(
            "phishingSettings", {}
        ).get("aidaSelectedAvailable")
        == True,
        "AIDA Optional Learning Available": account_data.get(
            "learnerExperienceSettings", {}
        ).get("aidaOptionalTrainingEnabled")
        == True,
        "Training Available": account_data.get("hasTraining"),
        "Physical QR Code Available": account_data.get("hasPhysicalQr"),
        "Security Roles Available": account_data.get("hasPermissions"),
        "Reporting API Available": account_data.get("partnerSubscriptionHasApi"),
        "User Event API Available": account_data.get(
            "partnerSubscriptionHasUserEventApi"
        ),
        # "Vishing Available": account_data.get("hasIvr"),
    }

    all_available = all(pretty_names_payload.values())

    return {
        "All Features Available": all_available,
        **pretty_names_payload,
    }


def create_client() -> Client:
    login_path = pathlib.Path("auth/knowbe4.json")
    login_payload = json.loads(login_path.read_text())

    with requests.Session() as s:
        s.headers.update(DEFAULT_HEADERS)
        s.post(LOGIN_URL, json=login_payload)

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


THROTTLE_TIME = 30
BATCH_SIZE = 30


def batch_update(sheet_url: str, data: dict, sheets: Sheets, dump: bool = False):
    if not dump and data is not None:
        sheets._batched_data |= data

    prev_time = sheets._prev_time
    curr_time = time.perf_counter()

    dt = curr_time - prev_time if prev_time is not None else THROTTLE_TIME

    if dump or (dt >= THROTTLE_TIME and len(sheets._batched_data) >= BATCH_SIZE):
        sheets._prev_time = curr_time

        sheets.batch_update(sheet_url, sheets._batched_data, align_columns=True)
        sheets._batched_data = {}


def get_data(sheets: Sheets):
    client = create_client()

    for n, account in enumerate(get_accounts(client=client)):
        n += 1

        id, name = account["id"], account["companyName"]
        name = str(name).strip().replace("/", "-")

        account_data = {
            "id": id,
            "name": name,
        }

        try:
            account_info = get_account_info(id, client=client)
            account_data |= parse_account_data(account_info)
        except Exception as e:
            print("Failed to parse account data for", id, name)

        slc = SheetSlice["Sheet1", n + 1, ...]
        data = {slc: [account_data]}

        batch_update(SHEET_URL, data=data, sheets=sheets)

    batch_update(SHEET_URL, data={}, sheets=sheets, dump=True)


if __name__ == "__main__":
    creds = get_oauth2_creds("auth/friday-institute-reports.credentials.json")
    sheets = Sheets(creds)

    sheets._batched_data = {}
    sheets._prev_time = None

    get_data(sheets=sheets)
