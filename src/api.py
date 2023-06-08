import pathlib
from typing import Iterable

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


def get_accounts(client: Client, per: int = 25, page: int = 1) -> Iterable[dict]:
    query_path = QUERY_DIR / "get_accounts.graphql"
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


def get_account_info(id: int, client: Client) -> dict:
    query_path = QUERY_DIR / "account_info.graphql"
    query = gql(query_path.read_text())

    return client.execute(query, variable_values={"id": id})


def parse_account_data(account_info: dict) -> dict:
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
        "Can Download Modules": account_data.get("canDownloadModules") == True,
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
