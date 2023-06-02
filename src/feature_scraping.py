import json
import pathlib
import numpy as np
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


FEATURES_COLS = [
    "name",
    "All Features Available",
    "Phishing Available",
    "AIDA Selected Templates Available",
    "Training Available",
    "AIDA Optional Learning Available",
    "Physical QR Code Available",
    "Security Roles Available",
    "Reporting API Available",
    "User Event API Available",
]


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

    account_information = {
        "Account Type": account_data.get("accountType"),
        "Account Admins": ", ".join(
            [
                f"{owner.get('firstName')} {owner.get('lastName')} ({owner.get('email')})"
                for owner in account_data.get("accountOwners", [])
            ]
        ),
        "Account Notes": account_data.get("notesSettings", {}).get("general"),
        "Referral ID": account_data.get("refid"),
        "Allowed Domains": ", ".join(
            [domain.get("name") for domain in account_data.get("allowedDomains", [])]
        ),
    }

    subscription_information = {
        "Billing Type": account_data.get("billingType"),
        "Subscription End Date": account_data.get("subscriptionEndDate"),
        "Number of Seats": account_data.get("numberOfSeats"),
        "Active Users": account_data.get("userCount"),
    }

    organization_information = {
        "Address": f'{account_data.get("city")}, {account_data.get("state")}, {account_data.get("country")}',
        "Industry": account_data.get("industry", {}).get("enumName"),
        "Time Zone": account_data.get("timeZone"),
        "Default Admin Console Language": account_data.get("languageSettings", {}).get(
            "adminLocale"
        ),
        "Default Training Language": account_data.get("languageSettings", {}).get(
            "trainingLocale"
        ),
    }

    account_features = {
        "Phishing Available": account_data.get("hasPhishing") == True,
        "AIDA Selected Templates Available": account_data.get(
            "phishingSettings", {}
        ).get("aidaSelectedAvailable")
        == True,
        "Training Available": account_data.get("hasTraining") == True,
        "AIDA Optional Learning Available": account_data.get(
            "learnerExperienceSettings", {}
        ).get("aidaOptionalTrainingEnabled")
        == True,
        "Physical QR Code Available": account_data.get("hasPhysicalQr") == True,
        "Security Roles Available": account_data.get("hasPermissions") == True,
        "Reporting API Available": account_data.get("partnerSubscriptionHasApi")
        == True,
        "User Event API Available": account_data.get(
            "partnerSubscriptionHasUserEventApi"
        )
        == True,
    }

    account_settings = {
        "SAML Enabled": account_data.get("samlEnabled") == True,
        "Passwordless Enabled": account_data.get("hasPassless") == True,
        "DMI Enabled": account_data.get("dmiEnabled") == True,
        "AIDA Optional Learning Enabled": account_data.get(
            "learnerExperienceSettings", {}
        ).get("aidaOptionalTrainingEnabled")
        == True,
        "User Provisioning Enabled": account_data.get("userProvisioning", {}).get(
            "enabled"
        )
        == True,
        "User Provisioning Test Mode": account_data.get("userProvisioning", {}).get(
            "testMode"
        )
        == True,
        "Phish Alert Enabled": account_data.get("phishalertEnabled") == True,
    }

    other_products = {
        "PhishER Enabled": account_data.get("phisherEnabled") == True,
        "KCM Enabled": account_data.get("accountSettingsKcm", {}).get("kcmEnabled")
        == True,
    }

    purchased_add_ons = {
        "Purchased Add-ons": ", ".join(
            [
                f"{sku.get('title')} Status: {sku.get('status')} {sku.get('expiresAt')}"
                for sku in account_data.get("purchasedSkus", [])
            ]
        ),
    }

    account_data = {
        **account_information,
        **subscription_information,
        **organization_information,
        **account_features,
        **account_settings,
        **other_products,
        **purchased_add_ons,
    }

    all_available = all(account_features.values())

    return {
        "All Features Available": all_available,
        **account_data,
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


def update_data(sheets: Sheets):
    client = create_client()
    sheets.clear(SHEET_URL, "Sheet1")

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

        sheets.batch_update(SHEET_URL, data={slc: [account_data]}, batch_size=30)

    sheets.batched_update_remaining(SHEET_URL)
    sheets.resize_columns(SHEET_URL, "Sheet1", width=None)


def get_data(sheets: Sheets) -> pd.DataFrame:
    return sheets.to_frame(sheets.values(SHEET_URL, "Sheet1")).set_index("id")


def apply_style_to_df(
    spreadsheet_id: str,
    sheet_name: str,
    diff_ixs: pd.DataFrame,
    sheets: Sheets,
):
    sheet_id = sheets.get(SHEET_URL, sheet_name)["properties"]["sheetId"]

    cell_format = sheets._create_cell_format(
        bold=True,
        # background_color="#F2E8E8",
        cell_format={
            "backgroundColor": {"red": 0.95, "green": 0.9, "blue": 0.9, "alpha": 1}
        },
    )

    diff_cells = diff_ixs.stack()
    diff_cells = diff_cells[diff_cells]

    requests = []
    for cell in diff_cells.index:
        *row_id, column_name = cell

        row = diff_ixs.index.get_loc(tuple(row_id)) + 2
        col = diff_ixs.columns.get_loc(column_name) + 2

        body = sheets._create_format_body(
            sheet_id,
            start_row=row,
            end_row=row,
            start_col=col,
            end_col=col,
            cell_format=cell_format,
        )
        requests.append(body)

    sheets.batch_update_spreadsheet(spreadsheet_id, body={"requests": requests})


def get_delta(prev_df: pd.DataFrame, curr_df: pd.DataFrame):
    prev_df = prev_df.reindex_like(curr_df)

    stacked_df = pd.concat(
        [curr_df, prev_df], keys=["Current", "Previous"], names=["Version"]
    ).sort_index(level=0)

    ixs = (curr_df != prev_df) & ~(curr_df.isna() & prev_df.isna())
    tmp = ixs.index[ixs.any(axis=1)]
    stacked_df = stacked_df[stacked_df.index.get_level_values(1).isin(tmp)]

    stacked_df_ixs = stacked_df[ixs]
    diff_ixs = ~pd.isna(stacked_df_ixs)

    return (
        stacked_df,
        diff_ixs,
    )


if __name__ == "__main__":
    creds = get_oauth2_creds("auth/friday-institute-reports.credentials.json")
    sheets = Sheets(creds)

    sheets.reset_sheet(SHEET_URL, "Delta")

    prev_df = get_data(sheets=sheets)
    # update_data(sheets=sheets)
    curr_df = get_data(sheets=sheets)

    t_prev_df = prev_df[FEATURES_COLS]
    t_curr_df = curr_df[FEATURES_COLS]

    delta_df, diff_ixs = get_delta(t_prev_df, t_curr_df)
    delta_df.reset_index(level=0, drop=False, inplace=True)

    sheets.update(SHEET_URL, "Delta", sheets.from_frame(delta_df))
    sheets.format(
        SHEET_URL,
        "Delta!1:1",
        bold=True,
    )
    apply_style_to_df(
        SHEET_URL,
        "Delta",
        diff_ixs,
        sheets,
    )
