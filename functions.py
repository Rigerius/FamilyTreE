import json
from datetime import datetime, date

def calculate_age(birth_date, death_date=None):
    if not birth_date:
        return None
    today = death_date if death_date else date.today()
    age = today.year - birth_date.year
    if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
        age -= 1
    return age


def init_family_data(family):
    if not family.data or family.data == "" or family.data == "{}":
        family.data = json.dumps({
            "persons": {},
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "version": "2.0"
            }
        })
    return json.loads(family.data)


def save_family_data(family, data):
    data["metadata"]["updated_at"] = datetime.now().isoformat()
    family.data = json.dumps(data)