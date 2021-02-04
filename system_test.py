import unittest
import requests
from enum import IntEnum
import json
import os
import urllib.parse


class TestCalorieCounter(unittest.TestCase):
    def test_get_own_user(self):
        body, code = self.get(f"/users/{bob}", bob)
        self.assertEqual(200, code)
        self.assertEqual(
            {
                "username": "bob",
                "role": Role.REGULAR,
                "expected_calories_per_day": 2000,
            },
            body["user"],
        )

    def test_register_twice(self):
        """Check we can only register a user once."""
        body, code = self.post(
            f"/users", bob, {"expected_calories_per_day": 2000, **bob_creds}
        )
        self.assertEqual(400, code)
        self.assertEqual({"error": "User already exists."}, body)

    def test_bad_register(self):
        """Fail gracefully when we post a user missing information (expected_calories_per_day)."""
        body, code = self.post(f"/users", bob, bob_creds)
        self.assertEqual(400, code)
        self.assertEqual({"error": "Invalid request."}, body)

    def test_change_pasword(self):
        body, code = self.put(f"/users/{bob}", bob, {"password": "password2"})
        self.assertEqual(200, code)
        self.assertEqual({"message": "Password successfully changed."}, body)

        body, code = self.post(
            f"/login", data={"username": bob, "password": "password2"}
        )
        self.assertEqual(200, code)
        self.bob_token = body["auth_token"]

        body, code = self.post(f"/login", data=bob_creds)
        self.assertEqual(401, code)
        self.assertEqual({"error": "Wrong username or password."}, body)

        body, code = self.put(f"/users/{bob}", bob, {"password": "password"})
        self.assertEqual(200, code)
        self.assertEqual({"message": "Password successfully changed."}, body)

    def test_change_role(self):
        # Get admin to make an entry and check Bob can't read it
        self.current_calorie_counter = admin
        body, _ = self.post(
            "/calories",
            admin,
            self.make_calorie("2020-06-01", "06:30", "grapefruit", 42),
        )
        self.current_calorie_counter = bob
        admin_calorie_id = body["calorie"]["id"]
        body, code = self.get(f"/calories/{admin_calorie_id}", bob)
        self.assertEqual(403, code)
        self.assertEqual({"error": "Not authorized."}, body)

        # Check Bob can't make himself an admin or a user manager
        body, code = self.put(f"/users/{bob}", bob, {"role": Role.USER_MANAGER})
        self.assertEqual(403, code)
        self.assertEqual({"error": "Not authorized."}, body)
        body, code = self.put(f"/users/{bob}", bob, {"role": Role.ADMIN})
        self.assertEqual(403, code)
        self.assertEqual({"error": "Not authorized."}, body)

        # User the admin user to make Bob an admin and check he can then read the "admin calorie"
        _, code = self.put(f"/users/{bob}", admin, {"role": Role.ADMIN})
        self.assertEqual(200, code)
        _, code = self.get(f"/calories/{admin_calorie_id}", bob)
        self.assertEqual(200, code)

    def test_delete_user(self):
        body, code = self.delete(f"/users/{bob}", bob)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual({"message": "User successfully deleted."}, body)

        body, code = self.post(f"/login", data=bob_creds)
        self.assertEqual(401, code, body.get("error", ""))
        self.assertEqual({"error": "Wrong username or password."}, body)

    def test_get_calorie(self):
        calorie = self.make_calorie("2020-06-01", "06:30", "grapefruit", 42)
        body, code = self.post(f"/calories", bob, calorie)
        id_created = body["calorie"]["id"]
        expected = {"calorie": {**calorie, "id": id_created, "below_expected": True}}
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

        body, code = self.get(f"/calories/{id_created}", bob)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

    def test_get_calories(self):
        """Add calories for Bob and Sally. Check Bob can only retrieve his entries."""
        # Make some Calorie entries for Bob
        bob_eats = [
            ["2020-06-01", "06:30", "grapefruit", 42],
            ["2020-06-01", "06:30", "protein pancake", 182],
            ["2020-06-01", "06:30", "white coffee", 25],
            ["2020-06-01", "12:00", "sausage roll", 244],
            ["2020-06-01", "12:00", "salad", 21],
            ["2020-06-01", "12:00", "lemon muffin", 350],
            ["2020-06-01", "18:30", "vegetarian lentil chilli", 148],
        ]
        expected = {"calories": {}}
        for eats in bob_eats:
            calorie_dict = self.make_calorie(*eats)
            body, code = self.post("/calories", bob, calorie_dict)
            self.assertEqual(200, code, body.get("error", ""))
            new_id = body["calorie"]["id"]
            expected["calories"][str(new_id)] = {
                "id": new_id,
                "below_expected": True,
                **calorie_dict,
            }

        # Check Bob can't make an entry for Sally
        body, code = self.post(
            "/calories",
            sally,
            self.make_calorie("2020-06-02", "07:30", "corn flakes with milk", 338),
        )
        self.assertEqual(403, code, body.get("error", ""))
        self.assertEqual({"error": "Not authorized."}, body)

        # Create an entry for Sally as Sally
        self.current_calorie_counter = sally
        body, code = self.post(
            "/calories",
            sally,
            self.make_calorie("2020-06-02", "07:30", "corn flakes with milk", 338),
        )
        self.assertEqual(200, code, body.get("error", ""))

        # Get back all the Calories for Bob (which won't have Sally's entry in it)
        self.current_calorie_counter = bob
        body, code = self.get(f"/calories?username=bob", bob)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

        # Bob tries to get back all the entries for Sally, which he can't do
        body, code = self.get(f"/calories?username=sally", bob)
        self.assertEqual(403, code, body.get("error", ""))
        self.assertEqual({"error": "Not authorized."}, body)

    def test_calorie_filter(self):
        bob_eats = [
            ["2020-06-01", "06:30", "grapefruit", 42],
            ["2020-06-01", "06:30", "protein pancake", 182],
            ["2020-06-01", "06:30", "white coffee", 25],
            ["2020-06-01", "12:00", "sausage roll", 244],
            ["2020-06-01", "12:00", "salad", 21],
            ["2020-06-01", "12:00", "lemon muffin", 350],
            ["2020-06-01", "18:30", "vegetarian lentil chilli", 148],
        ]
        new_ids = []
        for eats in bob_eats:
            body, code = self.post("/calories", bob, self.make_calorie(*eats))
            self.assertEqual(200, code, body.get("error", ""))
            new_ids.append(body["calorie"]["id"])
        filter = urllib.parse.quote_plus("time eq '12:00'")
        body, code = self.get(f"/calories?username=bob&filter={filter}", bob)
        expected_eats = {
            new_ids[3]: ["2020-06-01", "12:00", "sausage roll", 244],
            new_ids[4]: ["2020-06-01", "12:00", "salad", 21],
            new_ids[5]: ["2020-06-01", "12:00", "lemon muffin", 350],
        }
        expected = {"calories": {}}
        for i, eats in expected_eats.items():
            expected["calories"][str(i)] = {"id": i, **(self.make_calorie(*eats))}
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

        # Create an entry for Sally and check that admin can read back what Sally and Bob had for breakfast
        self.current_calorie_counter = sally
        body, _ = self.post(
            "/calories",
            sally,
            self.make_calorie("2020-06-01", "07:30", "corn flakes with milk", 338),
        )
        sallys_breakfast_id = body["calorie"]["id"]
        filter = urllib.parse.quote_plus("time lt '12:00'")
        body, code = self.get(f"/calories?filter={filter}", admin)
        self.assertEqual(200, code, body.get("error", ""))
        expected_eats = {
            new_ids[0]: ["2020-06-01", "06:30", "grapefruit", 42, bob],
            new_ids[1]: ["2020-06-01", "06:30", "protein pancake", 182, bob],
            new_ids[2]: ["2020-06-01", "06:30", "white coffee", 25, bob],
            sallys_breakfast_id: [
                "2020-06-01",
                "07:30",
                "corn flakes with milk",
                338,
                sally,
            ],
        }
        expected = {"calories": {}}
        for i, eats in expected_eats.items():
            expected["calories"][str(i)] = {"id": i, **(self.make_calorie(*eats))}
        self.assertEqual(expected, body)

    def test_calorie_provider(self):
        """
        Required HEADERS when accessing Nutritionix V2 API endpoints:
        x-app-id: Your app ID issued from developer.nutritionix.com)
        x-app-key: Your app key issued from developer.nutritionix.com)
        x-remote-user-id:  A unique identifier to represent the end-user who
        is accessing the Nutritionix API.  If in development mode, set this to 0.
        This is used for billing purposes to determine the number of active users your app has.
        """
        if not NUTRITIONIX_APP_ID:
            self.fail(
                "Set NUTRITIONIX_APP_ID and NUTRITIONIX_APP_KEY to run this test "
                "(See https://www.nutritionix.com/business/api)."
            )
        xremoteuserid = "0"
        response = requests.get(
            "https://trackapi.nutritionix.com/v2/search/instant?query=grapefruit",
            headers={
                "x-app-id": NUTRITIONIX_APP_ID,
                "x-app-key": NUTRITIONIX_APP_KEY,
                "x-remote-user-id": xremoteuserid,
            },
        )
        expected_calories = response.json()["branded"][0]["nf_calories"]

        calorie = self.make_calorie("2020-06-01", "06:30", "grapefruit")
        body, code = self.post(f"/calories", bob, calorie)
        expected = {
            "calorie": {
                **calorie,
                "id": body["calorie"]["id"],
                "below_expected": True,
                "number_of_calories": expected_calories,
            }
        }
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

    def test_calorie_per_day(self):
        # Change Bob's expected Calorie count to 800
        body, code = self.put(f"/users/{bob}", bob, {"expected_calories_per_day": 800})
        self.assertEqual(200, code, body.get("error", ""))
        expected = {
            "user": {
                "username": bob,
                "expected_calories_per_day": 800,
                "role": Role.REGULAR.value,
            }
        }
        self.assertEqual(expected, body)

        # Check that entries will start to be marked as over-expected when the total is greater than 800
        bob_eats = [
            (True, ["2020-06-01", "06:30", "grapefruit", 42]),
            (True, ["2020-06-01", "06:30", "protein pancake", 182]),
            (True, ["2020-06-01", "06:30", "white coffee", 25]),
            (True, ["2020-06-01", "12:00", "sausage roll", 244]),
            (True, ["2020-06-01", "12:00", "salad", 21]),  # total 514
            (
                False,
                ["2020-06-01", "12:00", "lemon muffin", 350],
            ),  # over expected total
            (False, ["2020-06-01", "18:30", "vegetarian lentil chilli", 148]),
        ]
        for under_expected, eats in bob_eats:
            body, code = self.post("/calories", bob, self.make_calorie(*eats))
            self.assertEqual(200, code, body.get("error", ""))
            self.assertEqual(under_expected, body["calorie"]["below_expected"])

    def setUp(self) -> None:
        self.bob_token = None
        self.admin_token = None
        self.sally_token = None

        #  use admin user to remove all users (apart from admin) and calories
        body, code = self.get("/users", admin)
        self.assertEqual(200, code, body.get("error", ""))
        for user in body["users"]:
            if user != "admin":
                body, code = self.delete(f"/users/{user}", admin)
                self.assertEqual(200, code, body.get("error", ""))
        body, code = self.get("/calories", admin)
        self.assertEqual(200, code, body.get("error", ""))
        for calorie_id in body["calories"]:
            body, code = self.delete(f"/calories/{calorie_id}", admin)
            self.assertEqual(200, code, body.get("error", ""))

        # Confirm Bob and Sally no longer exist then re-add them
        body, code = self.get("/users", admin)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertNotIn(bob, body["users"])
        self.assertNotIn(sally, body["users"])
        body, code = self.post(
            "/users", data={"expected_calories_per_day": 2000, **bob_creds}
        )
        self.assertEqual(200, code, body.get("error", ""))
        body, code = self.post(
            "/users", data={"expected_calories_per_day": 2000, **sally_creds}
        )
        self.assertEqual(200, code, body.get("error", ""))

        # Double check Bob and Sally do exist now
        body, code = self.get("/users", admin)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertIn(bob, body["users"])
        self.assertIn(bob, body["users"])
        self.current_calorie_counter = bob

    def login(self, user):
        if user == bob:
            token = self.bob_token
            creds = bob_creds
        elif user == admin:
            token = self.admin_token
            creds = admin_creds
        elif user == sally:
            token = self.sally_token
            creds = sally_creds
        else:
            self.fail()

        if not token:
            response = requests.post(url_root + "/login", json=creds)
            token = json.loads(response.content)["auth_token"]
            if user == bob:
                self.bob_token = token
            elif user == admin:
                self.admin_token = token
            else:
                self.sally_token = token
        return token

    def get(self, url, user):
        """Login if no auth tokens, then run get."""
        token = self.login(user)
        response = requests.get(url_root + url, headers={"access-token": token})
        return response.json(), response.status_code

    def post(self, url, user=None, data=None):
        """Login if no auth tokens, then run post."""
        if user:
            token = self.login(user)
            response = requests.post(
                url_root + url, headers={"access-token": token}, json=data
            )
        else:
            response = requests.post(url_root + url, json=data)
        return response.json(), response.status_code

    def delete(self, url, user):
        """Login if no auth tokens, then run delete."""
        token = self.login(user)
        response = requests.delete(url_root + url, headers={"access-token": token})
        return response.json(), response.status_code

    def put(self, url, user, data):
        """Login if no auth tokens, then run post."""
        token = self.login(user)
        response = requests.put(
            url_root + url, headers={"access-token": token}, json=data
        )
        return response.json(), response.status_code

    def make_calorie(self, date, time, text, number_of_calories=None, username=None):
        if number_of_calories:
            return {
                "date": date,
                "time": time,
                "text": text,
                "number_of_calories": number_of_calories,
                "username": username if username else self.current_calorie_counter,
            }
        else:
            return {
                "date": date,
                "time": time,
                "text": text,
                "username": username if username else self.current_calorie_counter,
            }


class Role(IntEnum):
    REGULAR = 1
    USER_MANAGER = 2
    ADMIN = 3


admin = "admin"
bob = "bob"
sally = "sally"
bob_creds = {"username": bob, "password": "password"}
sally_creds = {"username": sally, "password": "cats"}
admin_creds = {"username": admin, "password": "admin"}
url_root = "http://127.0.0.1:5000"
NUTRITIONIX_APP_ID = (
    os.environ["NUTRITIONIX_APP_ID"] if "NUTRITIONIX_APP_ID" in os.environ else None
)
NUTRITIONIX_APP_KEY = (
    os.environ["NUTRITIONIX_APP_KEY"] if "NUTRITIONIX_APP_KEY" in os.environ else None
)
