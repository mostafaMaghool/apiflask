from flask import Flask, request, jsonify
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

app = Flask(__name__)

# تابع ترجمه نام‌ها به فارسی با حفظ نام انگلیسی
def translate_keys(data):
    translation_map = {
        "property_id": "شناسه_مکان",
        "room_type_id": "شناسه_نوع_اتاق",
        "rate_plan_id": "شناسه_طرح_قیمت",
        "rack_rate": "قیمت_استاندارد",
        "daily_rate": "قیمت_روزانه",
        "purchase_rate": "قیمت_خرید",
        "baby_cot_daily_rate": "قیمت_سرپا_برای_کودک",
        "baby_cot_purchase_rate": "قیمت_خرید_سرپا_برای_کودک",
        "extend_bed_daily_rate": "قیمت_سرپا_اضافی_روزانه",
        "extend_bed_purchase_rate": "قیمت_خرید_سرپا_اضافی",
        "reservation_state": "وضعیت_رزرو",
        "min_stay": "حداقل_مدت_ماندن",
        "max_stay": "حداکثر_مدت_ماندن",
        "close_to_arrival": "نزدیک_به_ورود",
        "close_to_departure": "نزدیک_به_خروج",
        "closed": "بسته"
    }
    if isinstance(data, list):
        return [translate_keys(item) for item in data]
    elif isinstance(data, dict):
        translated_dict = {}
        for key, value in data.items():
            translated_key = f"{key} - {translation_map.get(key, key)}"
            translated_value = translate_keys(value)
            translated_dict[translated_key] = translated_value
        return translated_dict
    else:
        return data

# تابع برای گرفتن و پردازش داده‌ها
def fetch_and_group_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        room_rates = data["value"]["room_rates"]
        groups = {}
        for rate in room_rates:
            daily_rate = rate["daily_rate"]
            room_type_id = rate["room_type_id"]
            key = (daily_rate, room_type_id)
            day = rate["day"]
            if key not in groups:
                groups[key] = {
                    "property_id": rate["property_id"],
                    "room_type_id": rate["room_type_id"],
                    "rate_plan_id": rate["rate_plan_id"],
                    "day - از روز": day,
                    "day - تا روز": day,
                    "rack_rate": rate["rack_rate"],
                    "daily_rate": rate["daily_rate"],
                    "purchase_rate": rate["purchase_rate"],
                    "baby_cot_daily_rate": rate["baby_cot_daily_rate"],
                    "baby_cot_purchase_rate": rate["baby_cot_purchase_rate"],
                    "extend_bed_daily_rate": rate["extend_bed_daily_rate"],
                    "extend_bed_purchase_rate": rate["extend_bed_purchase_rate"],
                    "reservation_state": rate["reservation_state"]
                }
            else:
                groups[key]["day - تا روز"] = day
        grouped_data = {str(key): [details] for key, details in groups.items()}
        return grouped_data
    except Exception as e:
        print(f"خطا در دریافت یا پردازش داده‌ها از {url}: {e}")
        return {}

# تابع دریافت اطلاعات نوع اتاق و طرح قیمت از صفحه اصلی هتل
def fetch_room_details(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"خطا در دریافت اطلاعات از {url}: {e}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    target_tag = soup.find("h1", class_="subtitle-1 header-3-xl fw-bold mb-2 mb-xl-0 me-xl-4")
    target_text = target_tag.text.strip() if target_tag else "تگ مورد نظر پیدا نشد"
    global special_tag_text
    special_tag_text = target_text
    room_names = []
    div_tags = soup.find_all("div", class_="d-flex align-items-center mb-4")
    for div in div_tags:
        h3_tag = div.find("h3", class_="subtitle-3 fw-bold mb-0")
        if h3_tag:
            room_names.append(h3_tag.text.strip())
    hidden_inputs = soup.find_all("input", {"type": "hidden"})
    room_data = []
    current_room_name = None
    for input_tag in hidden_inputs:
        name = input_tag.get("name")
        value = input_tag.get("value")
        if name == "roomTypeId":
            current_room_name = room_names.pop(0) if room_names else None
            room_data.append((name, value, current_room_name))
        elif name == "ratePlanId" and current_room_name is not None:
            room_data.append((name, value, current_room_name))
    return room_data

# تابع ساخت URL جدید بر اساس پارامترهای ورودی
def generate_url(base_url, check_in, check_out, room_type_id, rate_plan_id):
    params = {
        "check_in": check_in,
        "check_out": check_out,
        "from_date": check_in,
        "to_date": check_out,
        "rate_plan_id": rate_plan_id,
        "room_type_id": room_type_id
    }
    for key, value in params.items():
        placeholder = f"{{{key}}}"
        if placeholder in base_url:
            base_url = base_url.replace(placeholder, value)
    return base_url

# تابع فیلتر کردن داده‌ها برای نمایش
def filter_data_for_display(data):
    filtered_data = [["Rack Rate", "Daily Rate", "Room Type ID", "Day From", "Day To", "Room Name"]]
    for key, value_list in data.items():
        rack_rate = value_list[0].get("rack_rate - قیمت_استاندارد", None)
        daily_rate = value_list[0].get("daily_rate - قیمت_روزانه", None)
        room_type_id = value_list[0].get("room_type_id - شناسه_نوع_اتاق", None)
        day_from = value_list[0].get("day - از روز - day - از روز", None)
        day_to = value_list[0].get("day - تا روز - day - تا روز", None)
        room_name = value_list[0].get("room_name", None)
        if all([rack_rate, daily_rate, room_type_id, day_from, day_to, room_name]):
            filtered_data.append([rack_rate, daily_rate, room_type_id, day_from, day_to, room_name])
    return filtered_data

# تنظیمات اولیه
BASE_URL = "https://www.eghamat24.com/properties/199/room-rates?check_in={check_in}&check_out={check_out}&from_date={from_date}&rate_plan_id={rate_plan_id}&room_type_id={room_type_id}&to_date={to_date}"

@app.route("/api/fetch_data", methods=["GET"])
def api_fetch_data():
    target_url = request.args.get("url")
    if not target_url:
        return jsonify({"error": "Missing Target URL"}), 400

    TODAY = datetime.today().strftime("%Y-%m-%d")
    NEW_TO_DATE = "2025-03-28"
    room_details = fetch_room_details(target_url)
    if not room_details:
        return jsonify({"error": "No Room Data Found"}), 404

    all_grouped_data = {}
    grouped_room_details = {}
    for name, value, room_name in room_details:
        if name == "roomTypeId":
            current_room_type_id = value
            grouped_room_details.setdefault(current_room_type_id, {"rate_plans": [], "room_name": room_name})
        elif name == "ratePlanId" and "current_room_type_id" in locals():
            grouped_room_details[current_room_type_id]["rate_plans"].append(value)

    for room_type_id, details in grouped_room_details.items():
        rate_plan_ids = details["rate_plans"]
        room_name = details["room_name"]
        for rate_plan_id in rate_plan_ids:
            url = generate_url(
                BASE_URL,
                check_in=TODAY,
                check_out=NEW_TO_DATE,
                room_type_id=room_type_id,
                rate_plan_id=rate_plan_id
            )
            grouped_data = fetch_and_group_data(url)
            if grouped_data:
                translated_data = {key: translate_keys(value) for key, value in grouped_data.items()}
                for key, value in translated_data.items():
                    value[0]["room_name"] = room_name
                all_grouped_data.update(translated_data)

    output_data = {
        "special_tag": special_tag_text,
        "filtered_data": filter_data_for_display(all_grouped_data)
    }
    return jsonify(output_data)

if __name__ == "__main__":
    app.run(debug=True, port=5000)