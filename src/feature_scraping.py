import json
import pathlib
from pprint import pprint

import requests
from requests import Session

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


def get_csrf_token(s: Session):
    r = s.get(SESSION_URL)
    session_data = r.json()
    return session_data["kmsat"]["csrf"]


def get_accounts(s: Session, per: int = 25, page: int = 1):
    q = {
        "query": "query Accounts($per: Int!, $page: Int!, $partnerId: Int, $status: AccountStatuses, $billingType: AccountBillingTypes, $search: String, $archivedUsers: Boolean, $sortField: AccountSortFields, $sortDirection: SortDirections, $otherPartnersAccounts: AccountPartnerInclusions) {\n  accounts(\n    per: $per\n    page: $page\n    partnerId: $partnerId\n    status: $status\n    billingType: $billingType\n    search: $search\n    archivedUsers: $archivedUsers\n    sortField: $sortField\n    sortDirection: $sortDirection\n    otherPartnersAccounts: $otherPartnersAccounts\n  ) {\n    nodes {\n      id\n      accountSettingsFlagNames\n      archived\n      billingType\n      pstCount\n      companyName\n      purchasedCourseCount\n      createdAt\n      domain\n      hasFreePst\n      hasFreePrt\n      hasFreeSpt\n      hasFreeUsb\n      numberOfSeats\n      userCount\n      partnerAccessExpiration\n      percentageUsersPhished\n      percentageUsersTrained\n      phishPronePercentage\n      latestRiskScore\n      subscriptionEndDate\n      resellerId\n      partnerDomain\n      partnerDisplayName\n      accountOwner {\n        id\n        confirmedAt\n      }\n      subscriptionObject {\n        id\n        friendlyName\n      }\n      purchasedSkus {\n        skuCode\n        status\n      }\n      languageSettings {\n        adminLocale\n      }\n    }\n    pagination {\n      pages\n      page\n      per\n      totalCount\n    }\n  }\n}\n",
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
        "query": "query accountShow($id: Int!) {\n  account(id: $id) {\n    id\n    accountSettingsFlagNames\n    accountType\n    anonymizePhishing\n    archived\n    betaEnabled\n    billingType\n    canDownloadModules\n    city\n    country\n    displayName\n    dmiEnabled\n    domain\n    defaultLocale\n    hasApi\n    hasIvr\n    hasPassless\n    hasPermissions\n    hasPhishing\n    hasPhysicalQr\n    hasSharedDomains\n    hasTraining\n    hasUserEventApi\n    numberOfSeats\n    partnerAccessExpiration\n    partnerDisplayName\n    partnerDomain\n    phishalertEnabled\n    phisherBeta\n    phisherEnabled\n    phisherSubscriptionEndDate\n    phoneNumber\n    refid\n    resellerId\n    samlEnabled\n    state\n    subscriptionEndDate\n    timeZone\n    trialExpirationDate\n    userCount\n    purchasedSkus {\n      skuCode\n      title\n      expiresAt\n      status\n    }\n    languageSettings {\n      adminLocale\n      trainingLocale\n    }\n    userProvisioning {\n      enabled\n      source\n      testMode\n    }\n    phishingSettings {\n      aidaSelectedAvailable\n    }\n    subscriptionObject {\n      subscriptionLevel\n      friendlyName\n      hasApi\n      hasUserEventApi\n      aidaSelectedEnabled\n      aidaRecommendedTrainingEnabled\n    }\n    accountOwners {\n      id\n      confirmedAt\n      email\n      firstName\n      lastName\n    }\n    accountSettingsKcm {\n      kcmEnabled\n      kcmSubscriptionEndDate\n    }\n    learnerExperienceSettings {\n      optionalTrainingEnabled\n      aidaOptionalTrainingEnabled\n      aidaOptionalTrainingAvailable\n    }\n    allowedDomains {\n      name\n    }\n    industry {\n      enumName\n    }\n    notesSettings {\n      general\n    }\n  }\n}\n",
        "variables": {"id": id},
    }
    return q


login_path = pathlib.Path("auth/knowbe4.json")
login_payload = json.loads(login_path.read_text())

with requests.Session() as s:
    s.headers.update(DEFAULT_HEADERS)
    r = s.post(LOGIN_URL, json=login_payload)

    csrf = get_csrf_token(s)
    s.headers.update({"X-CSRF-Token": csrf})

    for account in get_accounts(s):
        id, name = account["id"], account["companyName"]
        print(id, name)

        q = account_info_query(id=id)
        r = s.post(GRAPH_QL_URL, json=q)

        pprint(r.json())
