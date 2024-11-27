import json
import warnings
from datetime import datetime

import pandas as pd

# import psycopg2
import requests
# from sqlalchemy import create_engine

from config import Config

# Suppress the specific FutureWarning
warnings.filterwarnings("ignore", category=FutureWarning)


# 1. Get Access Token for Authentication
def get_access_token(api_access_url):
    """
    Fetches the OAuth2 access token required to authenticate API requests.
    """
    url = api_access_url + "/authentication/v1/authentication/login"
    headers = {
        "Content-Type": "application/json"  # This ensures the correct content type
    }
    # read .env/auth.json file into Data
    with open(".env/auth.json") as f:
        data = json.load(f)

    response = requests.post(
        url,
        headers=headers,
        json=data,
    )

    if response.status_code == 200:
        return response.json().get("token")
    else:
        print(f"Error fetching access token: {response.status_code}, {response.text}")
        return None


def get_restaurants(api_access_url, token):
    managementGroupGUID = "307daf3d-7a91-4edb-a3a0-3d620191d5b0"
    url = (
        api_access_url
        + "/restaurants/v1/groups/"
        + managementGroupGUID
        + "/restaurants"
    )
    headers = {
        "Toast-Restaurant-External-ID": "50ee1f12-58e4-41fe-a79c-fb7c857785a9",
        "Authorization": f"Bearer {token}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        guid_list = [item["guid"] for item in data]
        drop_list = [
            "426ba06d-699a-44bd-9f90-f93c36d2808c",
            "52249309-d7f0-423a-9c1a-a63306c6655a",
        ]
        guid_list = [item for item in guid_list if item not in drop_list]
        return guid_list
    else:
        print(f"Failed to fetch restaurants: {response.status_code}")
        print(response.json())
        return None


def get_restaurant_config(api_access_url, token):
    restaurantGUID = "50ee1f12-58e4-41fe-a79c-fb7c857785a9"
    url = api_access_url + "/configuration/v1/restaurants/" + restaurantGUID
    headers = {
        "Toast-Restaurant-External-ID": "50ee1f12-58e4-41fe-a79c-fb7c857785a9",
        "Authorization": f"Bearer {token}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(data)
    else:
        print(f"Failed to fetch restaurant config: {response.status_code}")
        print(response.json())


def get_todays_sales(api_access_url, token, guid):
    """
    Fetches today's orders from the Toast API.
    """
    url = api_access_url + "/orders/v2/ordersBulk"
    headers = {
        "Toast-Restaurant-External-ID": guid,
        "Authorization": f"Bearer {token}",
    }

    today = datetime.now().strftime("%Y%m%d")
    page_size = 100
    page = 1
    params = {"businessDate": today, "pageSize": page_size, "page": page}

    df = pd.DataFrame(
        columns=[
            "Date",
            "GUID",
            "Amount",
            "Check Numbers",
            "Guest Count",
            "Source",
            "Deleted",
            "Duration",
            "Voided",
            "Void Date",
        ],
    )
    df = df.astype(
        {
            "Date": "str",
            "GUID": "str",
            "Amount": "float",
            "Check Numbers": "str",
            "Guest Count": "int",
            "Source": "str",
            "Deleted": "bool",
            "Duration": "int",
            "Voided": "bool",
            "Void Date": "str",
        }
    )

    while True:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"Error fetching sales data: {response.status_code}, {response.text}")
            return None

        json_data = response.json()
        if not json_data:
            break

        data = []
        for order in json_data:
            date = order.get("businessDate", "")
            guest_count = order.get("guestCount", 0)
            source = order.get("source", "")
            deleted = order.get("deleted", False)
            duration = order.get("duration", 0)
            voided = order.get("voided", False)
            void_date = order.get("voidDate", "")

            total_amount = 0
            check_numbers = []

            for check in order.get("checks", []):
                total_amount += check.get("amount", 0)
                check_numbers.append(check.get("displayNumber", ""))
            row_data = {
                "Date": date,
                "GUID": guid,
                "Amount": total_amount,
                "Check Numbers": check_numbers,
                "Guest Count": guest_count,
                "Source": source,
                "Deleted": deleted,
                "Duration": duration,
                "Voided": voided,
                "Void Date": void_date,
            }
            data.append(row_data)
        new_df = pd.DataFrame(data)
        new_df = new_df.reindex(columns=df.columns, fill_value=False)
        if not new_df.empty:
            df = pd.concat([df, new_df], ignore_index=True)

        page += 1
        params["page"] = page

    return df


# 3. Filter Out Voided Orders
def filter_valid_orders(orders):
    """
    Filters out voided and deleted orders from the order list.
    """
    voided_orders = orders[orders["Voided"]]
    deleted_orders = orders[orders["Deleted"]]
    orders = orders[~orders["Deleted"]]
    orders = orders[~orders["Voided"]]
    print(f"Voided Orders: {voided_orders.shape[0]}")
    print(f"Deleted Orders: {deleted_orders.shape[0]}")

    return orders


# 4. Process Sales Data (calculate total sales, order count)
def process_sales_data(sales_data):
    # remove voided orders
    sales_data = filter_valid_orders(sales_data)
    sales_total_pivot = sales_data.pivot_table(
        index="GUID", values="Amount", aggfunc="sum"
    )
    sales_total_pivot = sales_total_pivot.reset_index()
    sales_total_pivot = sales_total_pivot.sort_values(by="Amount", ascending=False)
    print(sales_total_pivot)


def get_stock_status(api_access_url, token, guid):
    url = api_access_url + "/stock/v1/inventory"
    headers = {"Toast-Restaurant-External-ID": guid, "Authorization": f"Bearer {token}"}
    params = {"status": "OUT_OF_STOCK"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        json_data = response.json()
        data = []
        for stock in json_data:
            item = stock.get("guid", "")
            status = stock.get("status", "")
            quantity = stock.get("quantity", 0)
            row_data = {"GUID": item, "Status": status, "Quantity": quantity}
            data.append(row_data)
        df = pd.DataFrame(data)
        print(df)
    else:
        print(f"Failed to fetch stock status: {response.status_code}")
        print(response.json())
        return None


def get_menu_items(api_access_url, token, guid_list):
    menu_items = pd.DataFrame()
    url = api_access_url + "/config/v2/menuItems"
    for guid in guid_list:
        headers = {
            "Toast-Restaurant-External-ID": guid,
            "Authorization": f"Bearer {token}",
        }
        params = {
                "lastModified": "2024-11-20"
                }

        all_items = []

        while True:
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                json_data = response.json()
                for menu in json_data:
                    location_id = guid
                    item_id = menu.get("guid", "")
                    name = menu.get("name", "")
                    row_data = {
                        "Location ID": location_id,
                        "Item ID": item_id,
                        "Name": name,
                    }
                    all_items.append(row_data)

                page_token = response.headers.get("Toast-Next-Page-Token")

                if page_token:
                    params["pageToken"] = page_token
                else:
                    break
            else:
                print(f"Failed to fetch menu items: {response.status_code}")
                print(response.json())
                break
        df = pd.DataFrame(all_items)
        menu_items = pd.concat([menu_items, df], ignore_index=True)
    menu_items = (
        menu_items.groupby(["Item ID", "Name"])["Location ID"].agg(list).reset_index()
    )
    menu_items.sort_values(by="Name", inplace=True)
    print(menu_items)
    menu_items.to_csv("./output/menu_items.csv", index=False)


def get_menus(api_access_url, token, guid):
    url = api_access_url + "/config/v2/menus"
    headers = {"Toast-Restaurant-External-ID": guid, "Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        json_data = response.json()

        data = []

        for menu in json_data:
            for menu_group in menu.get("groups", []):
                print(menu_group)
                for menu_item in menu_group.get("menuItems", []):
                    row_data = {
                        "Location ID": guid,
                        "Item ID": menu_item.get("guid", ""),
                        "Item Name": menu_item.get("name", ""),
                        "POS Name": menu_item.get("posName", ""),
                        "Kitchen Display Name": menu_item.get("kitchenDisplayName", ""),
                        "Prep Station": ", ".join(menu_item.get("prepStations", [])),
                        "Prep Time": menu_item.get("prepTime", ""),
                        "Price": menu_item.get("price", 0),
                        "Pricing Strategy": menu_item.get("pricingStrategy", ""),
                        "Sales Category": menu_item.get("salesCategory", {}).get("name", ""),
                    }
                    data.append(row_data)
        df = pd.DataFrame(data)
        print(df)
        return
    else:
        print(f"Failed to fetch menus: {response.status_code}")
        print(response.json())
        return None


def get_menu_names(api_access_url, token, guid):
    url = api_access_url + "/config/v2/menus"
    headers = {"Toast-Restaurant-External-ID": guid, "Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        json_data = response.json()
        data = []
        for menu in json_data:
            location_id = guid
            menu_id = menu.get("guid", "")
            menu_name = menu.get("name", "")
            menu_groups = menu.get("groups", [])
            row_data = {"Location": location_id, "Menu ID": menu_id, "Menu Name": menu_name, "Menu Groups": menu_groups}
            data.append(row_data)
        df = pd.DataFrame(data)
    return df

# def get_employee_info(api_access_url, token, guid):

#     employee_id = "23660152-77c6-4c8c-9d7d-195c36fd6b7f"
#     url = api_access_url + "/labor/v1/employees/" + employee_id

#     headers = {
#       "Toast-Restaurant-External-ID": guid,
#       "Authorization": f"Bearer {token}"
#     }

#     response = requests.get(url, headers=headers)

#     data = response.json()
#     print(data)


# 5. Main Function to Run the Script
def main():
    # engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    # conn = psycopg2.connect(
    #     host=Config.HOST_SERVER,
    #     database=Config.PSYCOPG2_DATABASE,
    #     user=Config.PSYCOPG2_USER,
    #     password=Config.PSYCOPG2_PASS,
    # )
    # cur = conn.cursor()

    api_access_url = "https://ws-api.toasttab.com"

    # Step 1: Authenticate and get access token
    token = get_access_token(api_access_url)
    if not token:
        return
    access_token = ""
    for key, value in token.items():
        if key == "accessToken":
            access_token = value

    # get_restaurant guid list
    guid_list = get_restaurants(api_access_url, access_token)

    # menu items
    # get_menu_items(api_access_url, access_token, guid_list)

    # print restaurant menus
    # df = pd.DataFrame()
    # for guid in guid_list:
    #     menus = get_menu_names(api_access_url, access_token, guid)

    #     df = pd.concat([df, menus])

    # """Extract only the GUIDs from the Menu Groups column."""
    # df["Menu Group GUIDs"] = df["Menu Groups"].apply(lambda groups: [group["guid"] for group in groups])
    # # drop the Menu Groups column
    # df.drop(columns=["Menu Groups"], inplace=True)
    # # drop rows with empty Menu Group GUIDs
    # df = df[df["Menu Group GUIDs"].apply(len) > 0]
    # all_menu_groups = [guid for group_guids in df["Menu Group GUIDs"] for guid in group_guids]
    # unique_menu_groups = list(set(all_menu_groups))
    # print(unique_menu_groups)
    # print(len(unique_menu_groups))
    # df.to_csv("./output/menus.csv", index=False)

        # menus = get_menus(api_access_url, access_token, guid)
        # menu_groups = get_menu_groups(api_access_url, access_token, menus)


    # Step 2: Retrieve today's sales data
    sales_data = pd.DataFrame()
    for guid in guid_list:
        df = get_todays_sales(api_access_url, access_token, guid)
        sales_data = pd.concat([sales_data, df])
        # get_stock_status(api_access_url, access_token, guid)
    process_sales_data(sales_data)


if __name__ == "__main__":
    main()
