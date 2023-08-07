from typing import Iterable

from gql import Client

from .utils import graphql_query, paginated_query, PAGINATION_START, PAGINATION_PER


@paginated_query
@graphql_query
def accounts(
    client: Client, per: int = PAGINATION_PER, page: int = PAGINATION_START
) -> dict:
    return {
        "variable_values": {
            "per": per,
            "page": page,
            "search": "",
            "archivedUsers": False,
            "status": "ACTIVE",
            "billingType": "ANY",
            "sortField": "ORGANIZATION",
            "sortDirection": "ASCENDING",
            "otherPartnersAccounts": "ALL",
        }
    }


@paginated_query
@graphql_query
def users(
    client: Client, per: int = PAGINATION_PER, page: int = PAGINATION_START
) -> dict:
    return {
        "variable_values": {
            "per": per,
            "page": page,
            "status": "ACTIVE",
            "sortField": "ORGANIZATION",
            "sortDirection": "ASCENDING",
        }
    }


@paginated_query
@graphql_query
def partnerAdmins(
    client: Client, per: int = PAGINATION_PER, page: int = PAGINATION_START
) -> dict:
    return {
        "variable_values": {
            "per": per,
            "page": page,
            "search": "",
            "sortField": "EMAIL",
            "sortDirection": "ASCENDING",
        }
    }


@graphql_query
def accountShow(id: int, client: Client) -> dict:
    return {"variable_values": {"id": id}}


@graphql_query
def signInAsPartner(id: int, client: Client) -> dict:
    return {
        "variable_values": {
            "id": id,
        }
    }


@graphql_query
def partnerAdminCreate(partnerId: int, attributes: dict, client: Client) -> dict:
    return {"variable_values": {"partnerId": partnerId, "attributes": attributes}}


@graphql_query
def userGrantAdmin(id: int, client: Client) -> dict:
    return {"variable_values": {"userIds": [id]}}


@graphql_query
def introspect(client: Client) -> dict:
    return


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
