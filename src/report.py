import json
import pathlib

import jinja2
import pandas as pd
import requests
from googleapiutils2 import Sheets, get_oauth2_creds
from jinja2_markdown import MarkdownExtension

import src.api as api
from src.utils import create_gql_client

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


def update_feature_data(sheets: Sheets, spreadsheet_id: str, creds: dict):
    client = create_gql_client(creds)

    for n, account in enumerate(api.accounts(client=client)):
        n += 1

        id, name = account["id"], account["companyName"]
        name = str(name).strip().replace("/", "-")

        account_data = {
            "id": id,
            "name": name,
        }

        try:
            account_info = api.accountShow(id=id, client=client)
            account_data |= api.parse_account_data(account_info)
            print(account_data)
        except Exception as e:
            print("Failed to parse account data for", id, name)


def get_feature_df(sheets: Sheets, spreadsheet_id: str) -> pd.DataFrame | None:
    df = sheets.to_frame(sheets.values(spreadsheet_id))

    if df is None:
        return None
    else:
        return df.set_index("id")


def apply_diff_style_to_df(
    spreadsheet_id: str,
    sheet_name: str,
    diff_ixs: pd.DataFrame,
    sheets: Sheets,
):
    sheet_id = sheets.get(spreadsheet_id, sheet_name)["properties"]["sheetId"]

    cell_format = sheets._create_cell_format(
        bold=True,
        background_color="#F2E8E8",
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

    stacked_df.sort_index(inplace=True, level=1)
    diff_ixs.sort_index(inplace=True, level=1)

    return (
        stacked_df,
        diff_ixs,
    )


def create_email_body(params: dict):
    report_template_path = pathlib.Path("templates/knowbe4_report.md")

    jinja_env = jinja2.Environment(loader=jinja2.BaseLoader)
    jinja_env.add_extension(MarkdownExtension)

    template = jinja_env.from_string(report_template_path.read_text())

    return template.render(**params)


def send_emails(to: str, subject: str, body: str, zapier_url: str):
    body = {
        "to": to,
        "subject": subject,
        "body": body,
    }  # type: ignore
    r = requests.post(zapier_url, json=body)
    r.raise_for_status()

    return r.json()


# def main():
#     config_path = pathlib.Path("auth/config.json")
#     config = json.loads(config_path.read_text())

#     zapier_url = config["zapier"]["url"]

#     knowbe4_features_url = config["google"]["urls"]["knowbe4_features"]

#     creds = get_oauth2_creds(config["google"]["credentials_path"])
#     sheets = Sheets(creds)

#     knowbe4_creds = json.loads(
#         pathlib.Path(config["knowbe4"]["credentials_path"]).read_bytes()
#     )

#     prev_df = get_feature_df(sheets=sheets, spreadsheet_id=knowbe4_features_url)

#     update_feature_data(
#         sheets=sheets, spreadsheet_id=knowbe4_features_url, creds=knowbe4_creds
#     )

#     if prev_df is None:
#         print("No previous data found, skipping delta")
#         return

#     sheets.reset_sheet(knowbe4_features_url, "Delta")
#     curr_df = get_feature_df(sheets=sheets, spreadsheet_id=knowbe4_features_url)

#     t_prev_df = prev_df[FEATURES_COLS]
#     t_curr_df = curr_df[FEATURES_COLS]

#     delta_df, diff_ixs = get_delta(prev_df=t_prev_df, curr_df=t_curr_df)

#     if not len(delta_df):
#         print("No changes found, skipping delta")
#         return

#     delta_df.reset_index(level=0, drop=False, inplace=True)

#     sheets.update(knowbe4_features_url, "Delta", sheets.from_frame(delta_df))
#     sheets.format(
#         knowbe4_features_url,
#         SheetSlice["Delta", 1, ...],
#         bold=True,
#     )
#     sheets.resize_columns(knowbe4_features_url, "Delta", width=None)

#     apply_diff_style_to_df(
#         knowbe4_features_url,
#         "Delta",
#         diff_ixs,
#         sheets,
#     )

#     email_list = sheets.to_frame(sheets.values(knowbe4_features_url, "Email List"))
#     to = email_list["email"].tolist()

#     curr_date = datetime.now().strftime("%Y-%m-%d")
#     subject = f"{curr_date} KnowBe4 Report"

#     body = create_email_body(
#         {
#             "curr_date": curr_date,
#             "delta_df": delta_df,
#             "file_url": knowbe4_features_url,
#         }
#     )

#     send_emails(
#         to=to,
#         subject=subject,
#         body=body,
#         zapier_url=zapier_url,
#     )


def main():
    config_path = pathlib.Path("auth/config.json")
    config = json.loads(config_path.read_text())

    knowbe4_features_url = config["google"]["urls"]["knowbe4_features"]

    creds = get_oauth2_creds(config["google"]["credentials_path"])
    sheets = Sheets(creds)

    knowbe4_creds = json.loads(
        pathlib.Path(config["knowbe4"]["credentials_path"]).read_bytes()
    )

    update_feature_data(
        sheets=sheets, spreadsheet_id=knowbe4_features_url, creds=knowbe4_creds
    )


if __name__ == "__main__":
    main()
