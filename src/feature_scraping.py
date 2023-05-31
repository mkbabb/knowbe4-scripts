"""
The following values on the webpage can be mapped to the corresponding values in the JSON:

"Phishing Available" can be determined by checking the value of "hasPhishing"
"AIDA Selected Templates Available" can be determined by checking the value of "phishingSettings.aidaSelectedAvailable"
"Training Available" can be determined by checking the value of "hasTraining"
"AIDA Optional Learning Available" can be determined by checking the value of "learnerExperienceSettings.aidaOptionalTrainingAvailable"
"Vishing Available" is not present in the JSON
"Physical QR Code Available" can be determined by checking the value of "hasPhysicalQr"
"Security Roles Available" is not present in the JSON
"Reporting API Available" is not present in the JSON
"User Event API Available" can be determined by checking the value of "hasUserEventApi"
"""
import json
import pathlib

import pandas as pd
import requests
from googleapiutils2 import Sheets, get_oauth2_creds
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

SHEET_URL = "https://docs.google.com/spreadsheets/d/14WRf-S-T5MFkk4zOm0Ejsr-3g83EYEQ6dUle9VrDp6I/edit#gid=0"


def get_csrf_token(s: Session):
    r = s.get(SESSION_URL)
    session_data = r.json()
    return session_data["kmsat"]["csrf"]


def get_accounts(s: Session, per: int = 25, page: int = 1):
    q = {
        "query": "query Accounts($per: Int!, $page: Int!, $partnerId: Int, $status: AccountStatuses, $billingType: AccountBillingTypes, $search: String, $archivedUsers: Boolean, $sortField: AccountSortFields, $sortDirection: SortDirections, $otherPartnersAccounts: AccountPartnerInclusions) {\n  accounts(\n    per: $per\n    page: $page\n    partnerId: $partnerId\n    status: $status\n    billingType: $billingType\n    search: $search\n    archivedUsers: $archivedUsers\n    sortField: $sortField\n    sortDirection: $sortDirection\n    otherPartnersAccounts: $otherPartnersAccounts\n  ) {\n    nodes {\n      id\n      accountSettingsFlagNames\n      archived\n      billingType\n      pstCount\n      companyName\n      purchasedCourseCount\n      createdAt\n      domain\n      hasFreePst\n      hasFreePrt\n      hasFreeSpt\n      hasFreeUsb\n      numberOfSeats\n      userCount\n      partnerAccessExpiration\n      percentageUsersPhished\n      percentageUsersTrained\n      phishPronePercentage\n      latestRiskScore\n      subscriptionEndDate\n     partnerDomain\n      partnerDisplayName\n      accountOwner {\n        id\n        confirmedAt\n      }\n      subscriptionObject {\n        id\n        friendlyName\n      }\n      purchasedSkus {\n        skuCode\n        status\n      }\n      languageSettings {\n        adminLocale\n      }\n    }\n    pagination {\n      pages\n      page\n      per\n      totalCount\n    }\n  }\n}\n",
        "variables": {
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
    }

    while True:
        r = s.post(GRAPH_QL_URL, json=q)
        data = r.json()

        yield from data["data"]["accounts"]["nodes"]

        if (
            data["data"]["accounts"]["pagination"]["page"]
            == data["data"]["accounts"]["pagination"]["pages"]
        ):
            break

        q["variables"]["page"] += 1  # type: ignore


def account_info_query(id: int):
    q = {
        "query": "query accountShow($id: Int!) {\n  account(id: $id) {\n    id\n    accountSettingsFlagNames\n    accountType\n    anonymizePhishing\n    archived\n    betaEnabled\n    billingType\n    canDownloadModules\n    city\n    country\n    displayName\n    dmiEnabled\n    domain\n    defaultLocale\n    hasApi\n    hasIvr\n    hasPassless\n    hasPermissions\n    hasPhishing\n    hasPhysicalQr\n    hasSharedDomains\n    hasTraining\n    hasUserEventApi\n    numberOfSeats\n    partnerAccessExpiration\n    partnerDisplayName\n    partnerDomain\n    phishalertEnabled\n    phisherBeta\n    phisherEnabled\n    phisherSubscriptionEndDate\n    phoneNumber\n    refid\n    partnerId\n    samlEnabled\n    state\n    subscriptionEndDate\n    timeZone\n    trialExpirationDate\n    userCount\n    partnerSubscriptionHasApi\n    partnerSubscriptionHasUserEventApi\n    purchasedSkus {\n      skuCode\n      title\n      expiresAt\n      status\n    }\n    languageSettings {\n      adminLocale\n      trainingLocale\n    }\n    userProvisioning {\n      enabled\n      source\n      testMode\n    }\n    phishingSettings {\n      aidaSelectedAvailable\n    }\n    subscriptionObject {\n      subscriptionLevel\n      friendlyName\n      hasApi\n      hasUserEventApi\n      aidaSelectedEnabled\n      aidaRecommendedTrainingEnabled\n    }\n    accountOwners {\n      id\n      confirmedAt\n      email\n      firstName\n      lastName\n    }\n    accountSettingsKcm {\n      kcmEnabled\n      kcmSubscriptionEndDate\n    }\n    learnerExperienceSettings {\n      optionalTrainingEnabled\n      aidaOptionalTrainingEnabled\n      aidaOptionalTrainingAvailable\n    }\n    allowedDomains {\n      name\n    }\n    industry {\n      enumName\n    }\n    notesSettings {\n      general\n    }\n  }\n}\n",
        "variables": {"id": id},
    }
    return q


def parse_account_data(account_info: dict):
    account_data = account_info["data"]["account"]

    pretty_names_payload = {
        "Phishing Available": account_data["hasPhishing"],
        "AIDA Selected Templates Available": account_data["phishingSettings"][
            "aidaSelectedAvailable"
        ],
        "Training Available": account_data["hasTraining"],
        "AIDA Optional Learning Available": account_data["learnerExperienceSettings"][
            "optionalTrainingEnabled"
        ]
        == True,
        "Vishing Available": account_data["hasIvr"],
        "Physical QR Code Available": account_data["hasPhysicalQr"],
        "Security Roles Available": account_data["hasPermissions"],
        "Reporting API Available": account_data["partnerSubscriptionHasApi"],
        "User Event API Available": account_data["partnerSubscriptionHasUserEventApi"],
    }

    all_available = all(pretty_names_payload.values())

    return {
        **pretty_names_payload,
        "all_available": all_available,
    }


login_path = pathlib.Path("auth/knowbe4.json")
login_payload = json.loads(login_path.read_text())

accounts = []

with requests.Session() as s:
    s.headers.update(DEFAULT_HEADERS)
    r = s.post(LOGIN_URL, json=login_payload)

    csrf = get_csrf_token(s)
    s.headers.update({"X-CSRF-Token": csrf})

    for account in get_accounts(s):
        id, name = account["id"], account["companyName"]
        name = str(name).strip().replace("/", "-")
        print(id, name)

        q = account_info_query(id=id)
        r = s.post(GRAPH_QL_URL, json=q)

        account_data = {
            "id": id,
            "name": name,
        }

        try:
            account_info = r.json()
            account_info_path = pathlib.Path(f"data/{name}.json")
            account_info_path.write_text(json.dumps(account_info, indent=2))

            account_data |= parse_account_data(account_info)
        except Exception as e:
            print("Failed to parse account data for", id, name)

        accounts.append(account_data)

df = pd.DataFrame(accounts)

creds = get_oauth2_creds("auth/friday-institute-reports.credentials.json")
sheets = Sheets(creds)

sheets.clear(SHEET_URL, "Sheet1")
sheets.update(SHEET_URL, "Sheet1", sheets.from_frame(df))
sheets.resize_columns(SHEET_URL, "Sheet1", width=None)
