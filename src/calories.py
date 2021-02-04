from role import Role
from exceptions import NotAllowedException, UnknownCalorieException
from database import Calorie
import os
import requests
import urllib.parse


class Calories:
    def __init__(self, db_session):
        self._storage = _Storage(db_session)
        self._current_user = None
        self._current_role = None
        self._expected_calories_per_day = None

    def set_user_session(self, username, role, exp_cal_pd):
        self._current_user = username
        self._current_role = role
        self._expected_calories_per_day = exp_cal_pd

    def create(self, username, date, time, text, number_of_calories=0):
        if self._current_user != username and self._current_role != Role.ADMIN:
            raise NotAllowedException

        calories_today = self._storage.get_total_calories_for_day(date)
        below_expected = True
        if calories_today + number_of_calories > self._expected_calories_per_day:
            below_expected = False

        calorie = Calorie(
            text=text,
            number_of_calories=number_of_calories,
            username=username,
            date=date,
            time=time,
            below_expected=below_expected,
        )
        cal_dict = self._storage.create(calorie).__dict__.copy()
        cal_dict.pop("_sa_instance_state")
        return cal_dict

    def remove(self, entry_id):
        entry = self._storage.get(entry_id)
        if not entry:
            raise UnknownCalorieException
        if (
            entry
            and self._current_user != entry.username
            and self._current_role != Role.ADMIN
        ):
            raise NotAllowedException
        self._storage.remove(entry_id)

    def read(self, entry_id=None, filter=None, username=None):
        if entry_id:
            entry = self._storage.get(entry_id)
            if not entry:
                raise UnknownCalorieException
            if (
                entry
                and self._current_user != entry.username
                and self._current_role != Role.ADMIN
            ):
                raise NotAllowedException
            entry_dict = vars(entry)
            entry_dict.pop("_sa_instance_state")
            return entry_dict

        if username:
            if self._current_user != username and self._current_role != Role.ADMIN:
                raise NotAllowedException
            if filter:
                entries = self._storage.get_where(filter, username)
                ret_val = {}
                for r in entries:
                    ret_val[r[0]] = {
                        "id": r[0],
                        "text": r[1],
                        "number_of_calories": r[2],
                        "username": r[3],
                        "date": r[4],
                        "time": r[5],
                    }
                return ret_val
            else:
                entries = self._storage.get_by_username(username)
                ret_val = {}
                for entry in entries:
                    entry_dict = vars(entry)
                    entry_dict.pop("_sa_instance_state")
                    ret_val[entry.id] = entry_dict
                return ret_val
        else:
            if filter:
                entries = self._storage.get_where(filter)
                ret_val = {}
                for r in entries:
                    ret_val[r[0]] = {
                        "id": r[0],
                        "text": r[1],
                        "number_of_calories": r[2],
                        "username": r[3],
                        "date": r[4],
                        "time": r[5],
                    }
                return ret_val
            else:
                entries = self._storage.get_all()
                ret_val = {}
                for entry in entries:
                    entry_dict = vars(entry)
                    entry_dict.pop("_sa_instance_state")
                    ret_val[entry.id] = entry_dict
                return ret_val


class _Storage:
    def __init__(self, db_session):
        self._db_session = db_session

    def remove(self, entry_id):
        self._db_session.query(Calorie).filter(Calorie.id == entry_id).delete()
        self._db_session.commit()

    def create(self, cal_obj):
        self._db_session.add(cal_obj)
        self._db_session.commit()
        return self._db_session.query(Calorie).get(cal_obj.id)

    def get(self, entry_id):
        return self._db_session.query(Calorie).get(entry_id)

    def get_all(self):
        return self._db_session.query(Calorie)

    def get_by_username(self, username):
        return self._db_session.query(Calorie).filter(Calorie.username == username)

    def get_where(self, search_filter, username=None):
        query = "SELECT * FROM calorie WHERE "
        query += (
            search_filter.replace("eq", "=")
            .replace("ne", "<>")
            .replace("gt", ">")
            .replace("lt", "<")
        )
        query += f" AND username = '{username}'" if username else ""
        print(query)
        return self._db_session.execute(query)

    def get_total_calories_for_day(self, the_date):
        query = f"SELECT SUM(number_of_calories) FROM calorie WHERE date='{the_date}'"
        for x in self._db_session.execute(query):
            return x[0] if x[0] else 0
        return 0
