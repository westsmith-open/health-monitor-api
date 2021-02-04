import datetime
import os
import traceback

import jwt
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from exceptions import (
    InvalidTokenException,
    InvalidRequestException,
    UnknownCalorieException,
    NotAllowedException,
    UnknownUserException,
    InitialAdminRoleException,
    UserAlreadyExistsException,
)
from users import Users, UserManagement

app = Flask(__name__)
app.config["SECRET_KEY"] = (
    os.environ["SECRET_KEY"] if "SECRET_KEY" in os.environ else "bad_secret"
)


def check_token_and_set_session(user_manage):
    if "access-token" in request.headers:
        token = request.headers["access-token"]
    else:
        raise InvalidTokenException
    data = jwt.decode(token, app.config["SECRET_KEY"])
    user_manage.set_user_session(data["username"])


#  Create user
def register(user_manager):
    request_data = request.get_json()
    if (
        "username" not in request_data
        or "password" not in request_data
        or "expected_calories_per_day" not in request_data
    ):
        raise InvalidRequestException
    hashed_password = generate_password_hash(request_data["password"])
    user_manager.create(
        request_data["username"],
        hashed_password,
        request_data["expected_calories_per_day"],
    )
    return jsonify({"message": "Successfully registered."})


def read_users(user_manage: Users):
    user_dict = user_manage.read()
    return jsonify({"users": user_dict})


def read_user(user_manage: Users, username):
    user_dict = user_manage.read(username)
    return jsonify({"user": user_dict})


def remove_user(user_manage: Users, username):
    user_manage.remove(username)
    return jsonify({"message": "User successfully deleted."})


def update_user(user_manage: Users, username):
    if len(request.json) != 1:
        raise InvalidRequestException
    if "password" in request.json:
        password_hash = generate_password_hash(request.json["password"])
        user_manage.update_password(username, password_hash)
    elif "expected_calories_per_day" in request.json:
        user_dict = user_manage.update_expected_calories_per_day(
            username, request.json["expected_calories_per_day"]
        )
        return jsonify({"user": user_dict})
    elif "role" in request.json:
        user_dict = user_manage.update_role(username, request.json["role"])
        return jsonify({"user": user_dict})
    else:
        raise InvalidRequestException
    return jsonify({"message": "Password successfully changed."})


def create_calorie(user_manager: Users):
    calorie_dict = user_manager.calories.create(**request.json)
    return jsonify({"calorie": calorie_dict})


def read_calories(user_manager: Users):
    calories_dict = user_manager.calories.read(**request.args)
    return jsonify({"calories": calories_dict})


def read_calorie(user_manager: Users, calorie_id):
    calorie_dict = user_manager.calories.read(calorie_id)
    return jsonify({"calorie": calorie_dict})


def remove_calorie(user_manager: Users, calorie_id):
    user_manager.calories.remove(calorie_id)
    return jsonify({"message": "Calorie successfully deleted."})


def eval_and_respond(user_manage, funcs):
    ret_val = {}
    try:
        for func in funcs:
            if isinstance(func, list):
                ret_val = func[0](user_manage, *func[1:])
            else:
                ret_val = func(user_manage)
    except UnknownCalorieException:
        return jsonify({"error": "Calorie not found."}), 404
    except NotAllowedException:
        return jsonify({"error": "Not authorized."}), 403
    except UserAlreadyExistsException:
        return jsonify({"error": "User already exists."}), 400
    except InvalidRequestException:
        return jsonify({"error": "Invalid request."}), 400
    except UnknownUserException:
        return jsonify({"error": "User not found."}), 404
    except InitialAdminRoleException:
        return jsonify({"error": "Can't change admin username or role."}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    return ret_val


def create_admin_user():
    with UserManagement() as user_management:
        password_hash = generate_password_hash(
            os.environ["ADMIN_PASSWORD"] if "ADMIN_PASSWORD" in os.environ else "admin"
        )
        user_management.create_initial_admin(password_hash)


@app.route("/login", methods=["POST"])
def login():
    json = request.get_json()
    with UserManagement() as user_manage:
        user_orm = user_manage.non_session_read(json["username"])
    if not user_orm:
        return jsonify({"error": "Wrong username or password."}), 401
    if check_password_hash(user_orm.hashed_password, json["password"]):
        payload = {
            "username": json["username"],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
        }
        token = jwt.encode(payload, app.config["SECRET_KEY"])
        return jsonify({"auth_token": token.decode()})
    return jsonify({"error": "Wrong username or password."}), 401


@app.route("/users", methods=["GET", "POST"])
def users():
    with UserManagement() as user_manage:
        if request.method == "GET":
            funcs = [check_token_and_set_session, read_users]
        else:  # POST
            funcs = [register]
        response = eval_and_respond(user_manage, funcs)
    return response


@app.route("/users/<username>", methods=["GET", "PUT", "DELETE"])
def user(username):
    with UserManagement() as user_manage:
        if request.method == "GET":
            funcs = [check_token_and_set_session, [read_user, username]]
            response = eval_and_respond(user_manage, funcs)
        elif request.method == "DELETE":
            funcs = [check_token_and_set_session, [remove_user, username]]
            response = eval_and_respond(user_manage, funcs)
        else:  # PUT
            funcs = [check_token_and_set_session, [update_user, username]]
            response = eval_and_respond(user_manage, funcs)
    return response


@app.route("/calories", methods=["GET", "POST"])
def calories():
    with UserManagement() as user_manage:
        if request.method == "GET":
            funcs = [check_token_and_set_session, read_calories]
        else:  # POST
            funcs = [check_token_and_set_session, create_calorie]
        response = eval_and_respond(user_manage, funcs)
    return response


@app.route("/calories/<calorie_id>", methods=["GET", "PUT", "DELETE"])
def calorie(calorie_id):
    with UserManagement() as user_manage:
        if request.method == "GET":
            funcs = [check_token_and_set_session, [read_calorie, calorie_id]]
            response = eval_and_respond(user_manage, funcs)
        else:  # DELETE:
            funcs = [check_token_and_set_session, [remove_calorie, calorie_id]]
            response = eval_and_respond(user_manage, funcs)
    return response


create_admin_user()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
