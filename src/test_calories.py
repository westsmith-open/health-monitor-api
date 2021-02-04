import unittest

from calories import Calories
from users import Role
from exceptions import NotAllowedException, UnknownCalorieException
import database

BOB = "bob"
ALICE = "alice"


class TestCalories(unittest.TestCase):
    def setUp(self) -> None:
        self.db_session = database.get_db_session()
        database.recreate_db()
        self.calories = Calories(self.db_session)
        self.args = [BOB, "2020-06-01", "09:30", "banana", 89]

    def tearDown(self):
        self.db_session.close()

    def create(self, username, role, *args, **kwargs):
        """Helper function."""
        self.calories.set_user_session(username, role, 2000)
        return self.calories.create(*args, **kwargs)

    def read(self, username, role, *args, **kwargs):
        """Helper function."""
        self.calories.set_user_session(username, role, 2000)
        return self.calories.read(*args, **kwargs)

    def remove(self, username, role, entry_id):
        """Helper function."""
        self.calories.set_user_session(username, role, 2000)
        return self.calories.remove(entry_id)

    def test_create_read_entry(self):
        entry_id = self.create(BOB, Role.REGULAR, *self.args)["id"]
        actual = self.read(BOB, Role.REGULAR, entry_id)
        expected = {
            "id": 1,
            "date": "2020-06-01",
            "time": "09:30",
            "text": "banana",
            "number_of_calories": 89,
            "username": BOB,
            "below_expected": True,
        }
        self.assertEqual(expected, actual)

    def test_create_remove_entry(self):
        entry_id = self.create(BOB, Role.REGULAR, *self.args)["id"]
        self.remove(BOB, Role.REGULAR, entry_id)
        self.assertRaises(
            UnknownCalorieException, self.read, BOB, Role.REGULAR, entry_id
        )

    def test_create_with_other_users(self):
        self.assertRaises(
            NotAllowedException, self.create, ALICE, Role.REGULAR, *self.args
        )
        self.assertRaises(
            NotAllowedException, self.create, ALICE, Role.USER_MANAGER, *self.args
        )
        self.create(ALICE, Role.ADMIN, *self.args)

    def test_read_or_remove_with_other_users(self):
        entry_id = self.create(BOB, Role.REGULAR, *self.args)["id"]
        # Read entry
        self.assertRaises(NotAllowedException, self.read, ALICE, Role.REGULAR, entry_id)
        self.assertRaises(
            NotAllowedException, self.read, ALICE, Role.USER_MANAGER, entry_id
        )
        self.read(ALICE, Role.ADMIN, entry_id)
        # Remove entry
        self.assertRaises(
            NotAllowedException, self.remove, ALICE, Role.REGULAR, entry_id
        )
        self.assertRaises(
            NotAllowedException, self.remove, ALICE, Role.USER_MANAGER, entry_id
        )
        self.remove(ALICE, Role.ADMIN, entry_id)

    def test_filtering(self):
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
            self.create(BOB, Role.REGULAR, BOB, *eats)

        actual = self.read(BOB, Role.REGULAR, filter="time eq '12:00'")
        expected = {
            4: {
                "id": 4,
                "date": "2020-06-01",
                "time": "12:00",
                "text": "sausage roll",
                "number_of_calories": 244,
                "username": BOB,
            },
            5: {
                "id": 5,
                "date": "2020-06-01",
                "time": "12:00",
                "text": "salad",
                "number_of_calories": 21,
                "username": BOB,
            },
            6: {
                "id": 6,
                "date": "2020-06-01",
                "time": "12:00",
                "text": "lemon muffin",
                "number_of_calories": 350,
                "username": BOB,
            },
        }
        self.assertEqual(expected, actual)

        actual = self.read(
            BOB, Role.REGULAR, filter="(time eq '12:00') AND (text eq 'sausage roll')"
        )
        expected = {
            4: {
                "id": 4,
                "date": "2020-06-01",
                "time": "12:00",
                "text": "sausage roll",
                "number_of_calories": 244,
                "username": BOB,
            }
        }
        self.assertEqual(expected, actual)

        actual = self.read(BOB, Role.REGULAR, filter="number_of_calories lt 50")
        expected = {
            1: {
                "id": 1,
                "date": "2020-06-01",
                "time": "06:30",
                "text": "grapefruit",
                "number_of_calories": 42,
                "username": BOB,
            },
            3: {
                "id": 3,
                "date": "2020-06-01",
                "time": "06:30",
                "text": "white coffee",
                "number_of_calories": 25,
                "username": BOB,
            },
            5: {
                "id": 5,
                "date": "2020-06-01",
                "time": "12:00",
                "text": "salad",
                "number_of_calories": 21,
                "username": BOB,
            },
        }
        self.assertEqual(expected, actual)
