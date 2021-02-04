from flask_testing import TestCase
import app
from users import Role
import urllib.parse
import requests


class TestCalorieCounter(TestCase):
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
        expected = {"calorie": {**calorie, "id": 1, "below_expected": True}}

        body, code = self.post(f"/calories", bob, calorie)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

        body, code = self.get(f"/calories/1", bob)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

    def test_get_calories(self):
        cals = {
            1: self.make_calorie("2020-06-01", "06:30", "grapefruit", 42),
            2: self.make_calorie("2020-06-01", "06:30", "protein pancake", 182),
        }
        self.post(f"/calories", bob, cals[1])
        self.post(f"/calories", bob, cals[2])
        expected = {
            "calories": {
                "1": {"id": 1, **cals[1], "below_expected": True},
                "2": {"id": 2, **cals[2], "below_expected": True},
            }
        }
        body, code = self.get(f"/calories?username=bob", bob)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

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
        for eats in bob_eats:
            self.post("/calories", bob, self.make_calorie(*eats))
        filter = urllib.parse.quote_plus("time eq '12:00'")
        body, code = self.get(f"/calories?username=bob&filter={filter}", bob)
        expected_eats = {
            4: ["2020-06-01", "12:00", "sausage roll", 244],
            5: ["2020-06-01", "12:00", "salad", 21],
            6: ["2020-06-01", "12:00", "lemon muffin", 350],
        }
        expected = {"calories": {}}
        for i, eats in expected_eats.items():
            expected["calories"][str(i)] = {"id": i, **(self.make_calorie(*eats))}
        self.assertEqual(200, code, body.get("error", ""))
        self.assertEqual(expected, body)

    def test_calorie_per_day(self):
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
        bob_eats = [
            ["2020-06-01", "06:30", "grapefruit", 42],
            ["2020-06-01", "06:30", "protein pancake", 182],
            ["2020-06-01", "06:30", "white coffee", 25],
            ["2020-06-01", "12:00", "sausage roll", 244],
            ["2020-06-01", "12:00", "salad", 21],  # total 514
            ["2020-06-01", "12:00", "lemon muffin", 350],  # over expected total
            ["2020-06-01", "18:30", "vegetarian lentil chilli", 148],
        ]
        expected_below_expected = {
            1: True,
            2: True,
            3: True,
            4: True,
            5: True,  # total 514
            6: False,  # over expected total
            7: False,
        }
        for eats in bob_eats:
            body, code = self.post("/calories", bob, self.make_calorie(*eats))
            self.assertEqual(200, code, body.get("error", ""))
            self.assertEqual(
                expected_below_expected[body["calorie"]["id"]],
                body["calorie"]["below_expected"],
            )

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

        # Confirm Bob no longer exist then re-add him
        body, code = self.get("/users", admin)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertNotIn(bob, body["users"])
        body, code = self.post(
            "/users", data={"expected_calories_per_day": 2000, **bob_creds}
        )
        self.assertEqual(200, code, body.get("error", ""))

        # Double check Bob exists now
        body, code = self.get("/users", admin)
        self.assertEqual(200, code, body.get("error", ""))
        self.assertIn(bob, body["users"])
        self.assertIn(bob, body["users"])
        self.current_calorie_counter = bob

    def login(self, user):
        token = None
        creds = bob_creds if user == bob else admin_creds
        if user == bob and self.bob_token:
            token = self.bob_token
        elif user == admin and self.admin_token:
            token = self.admin_token

        if not token:
            response = self.client.post("/login", json=creds)
            token = response.json["auth_token"]
            if user == bob:
                self.bob_token = token
            else:
                self.admin_token = token
        return token

    def get(self, url, user):
        """Login if no auth tokens, then run get."""
        token = self.login(user)
        response = self.client.get(url, headers={"access-token": token})
        return response.json, response.status_code

    def delete(self, url, user):
        """Login if no auth tokens, then run delete."""
        token = self.login(user)
        response = self.client.delete(url, headers={"access-token": token})
        return response.json, response.status_code

    def post(self, url, user=None, data=None):
        """Login if no auth tokens, then run post."""
        if user:
            token = self.login(user)
            response = self.client.post(url, headers={"access-token": token}, json=data)
        else:
            response = self.client.post(url, json=data)
        self.assertIsNotNone(response.json, response.status_code)
        return response.json, response.status_code

    def put(self, url, user, data):
        """Login if no auth tokens, then run post."""
        token = self.login(user)
        response = self.client.put(url, headers={"access-token": token}, json=data)
        return response.json, response.status_code

    def create_app(self):
        return app.app

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


admin = "admin"
bob = "bob"
bob_creds = {"username": bob, "password": "password"}
admin_creds = {"username": admin, "password": "admin"}
