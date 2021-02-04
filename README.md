# Health Monitor API

## Background

This is a REST API that allows a user to count calories and monitor exercise. Users can create an account and log in.
Once logged in, they can send updates about what food they have eaten, which is stored in a database.

## Approach

This system has been implemented in Python using Flask for the REST API and a relational database
as the persistence layer (PostgreSQL or SQLite). Each HTTP request causes a user manager (Users) and calorie
manager (Calories) to be instantiated. These objects handle the bulk of the request logic and interactions with 
the database.

The user manager class (Users) does the following:

* Handles telling the calorie manager who is logged in
* Sets up the database session
* Interacts with User data in the database
* Protects the wrong user accessing another user's User data

The calorie manager class (Calories) does the following:
 
* Calculating whether a calorie has exceeded a user's expected calories
* Executing filters
* Protects the wrong user accessing another user's Calorie data
* Interacts with Calorie data in the database

For authentication the system uses JWT tokens which contain an expiry date and the users's username.
On login, this token is returned back to the client. Every other call will use this
token (provided in the header).

All request logic (apart from login) are run within a eval_and_respond function. This does the job
of running the functions required by the request inside a try block. This handling on this block converts internal
exceptions to HTTP errpr responses. This way, all the error handling can be managed in one place.

## Installation

To install and run you will need Docker. Follow these steps to run the API:

1. In the ```docker-compose.yml``` change the following environment variables:
   * ```DATABASE_URL``` - This is a sqlalchemy URL setup for the system test PostgreSQL database. Point this at the database of your
   choice (PostgreSQL has been tested)
   * ```SECRET_KEY``` - Pick a unique key for encoding JWT tokens.
   * ```ADMIN_PASSWORD``` - Pick an initial password for the "admin" user
1. In the ```docker-compose.yml```, remove the postgres service unless using (used for system testing)
1. Open a terminal in this directory
1. Run ```docker-compose build```
1. Run ```docker-compose up -d```

## Usage

### User roles

To initialise the system on a blank database a user called "admin" is created. This user has a role of
admin and the password will be set via the "ADMIN_PASSWORD" environment variable otherwise will default to "admin".

| User role |  Enum value used on REST interface and stored in database | What can the role do |
|---|---|---|
| n/a | n/a | A non-autherised REST call can create any number of regular users. | 
|regular | 1| Add and remove calories they own.  Change the expected calories and password for themselves. Remove themselves.|
|user manager | 2| Add and remove calories they own. Make any change to any non-admin users apart from changing a users role to admin. Removing users will remove any calories that user owns (database cascade). |
|admin |3| Can make any change to users or calories apart from removing or changing the role of the initial "admin" user. |



### Valid requests


| Action |  HTTP Method  | URL  |  Request body | Header  |
|---|---|---|---|---|
| Register user  | POST  | /users  |```{"username": "bob", "password": "password", "expected_calories_per_day": "2000"}```  |   |
| Login | POST  |  /login |  ```{"username": "bob", "password": "password"}```  |   |
| Get all users  | GET  |  /users |   | "access-token": token  | `
| Get Bob's user record  | GET  |  /users/bob |   | "access-token": token  | `
| Change Bob's password  | PUT  |  /users/bob | ```{"password": "password"}```  | "access-token": token  |
| Change Bob's role to admin  | PUT  |  /users/bob | ```{"role": 3}```  | "access-token": token  |
| Change Bob's expected calories a day  | PUT  |  /users/bob | ```{"expected_calories_per_day": 800}```  | "access-token": token  |
| Delete user Bob  | DELETE  |  /users/bob |   | "access-token": token  | 
| Create a calorie entry  | POST  |  /calories |  ```{"date": "2020-06-01", "time": "09:30", "text": "banana", "number_of_calories": 89,"username": "bob}``` | "access-token": token  | 
| Get calorie id 1 | GET  |  /calories/1 |   | "access-token": token  | 
| Get all calories  | GET  |  /calories |   | "access-token": token  | 
| Get all calories owned by Bob | GET  |  /calories?username=bob |   | "access-token": token  | 
| Get all calories owned by Bob using filter ```time eq '12:00'``` | GET  |  /calories?username=bob&filter=time+eq+%2712%3A00%27 |   | "access-token": token  | 
| Get all calories using filter ```time eq '12:00'``` | GET  |  /calories?filter=time+eq+%2712%3A00%27 |   | "access-token": token  | 
| Delete calorie 1  | DELETE  |  /calories/1 |   | "access-token": token  | 

### Expected return values

Apart from unexpected 500 errors, all requests will return a json object with one or more of the following keys:

| JSON Key |  Description  | Example |
|---|---|---|
|auth_token| Returned by /login on a successful login. Passed to most other calls as the access-token header.|```{'auth_token': 'eyJ0eXAiOi'}``` (truncated example) |
|message| Informational returned by successful deletions and password changes.|```{"message": "Password successfully changed."} ```|
|error| Returned for all 400 errors. Can be generated by any request| ```{"error": "User not found."}```|
|calorie| Returned by all calls to /calories/:id. Value is a single calorie object. | ```{'calorie': {'below_expected': True, 'date': '2020-06-01', 'id': 1, 'number_of_calories': 42, 'text': 'grapefruit', 'time': '06:30', 'username': 'admin'}}``` |
|calories| Returned by all calls to /calories (including those with query parameters). Value is an object where the key is ```id``` mapping to calorie a object. | ```{'calories': {'4': {'date': '2020-06-01', 'id': 4, 'number_of_calories': 244, 'text': 'sausage roll', 'time': '12:00', 'username': 'bob'}, '5': {'date': '2020-06-01', 'id': 5, 'number_of_calories': 21, 'text': 'salad', 'time': '12:00', 'username': 'bob'}, '6': {'date': '2020-06-01', 'id': 6, 'number_of_calories': 350, 'text': 'lemon muffin', 'time': '12:00', 'username': 'bob'}}}```|
|user| Returned by all calls to /user/:username, apart from when a password is changed. Value is a single user object.|```{'user': {'expected_calories_per_day': 800, 'role': 1, 'username': 'bob'}}``` |
|users| Returned by all calls to /users. Value is an object where the key is ```username``` mapping to a user object. | ```{'users': {'admin': {'expected_calories_per_day': 2000, 'role': 3, 'username': 'admin'}, 'bob': {'expected_calories_per_day': 2000, 'role': 1, 'username': 'bob'}}}```|

## How to run the tests

To run the all tests you will need Python 3.7 and Docker. You will also need an account with nutritionix 
(see https://developer.nutritionix.com/signup). Follow these steps to run the tests:

1. Open a terminal in this directory
1. Run ```python3 -m venv venv```
1. Run ```. venv/bin/activate```
1. Run ```pip install -r requirements.txt```
1. Run ```python -m unittest discover src```. This will run all the unit tests.
1. In the ```docker-compose.yml``` file, replace ```get_a_nutritionix_app_id``` with your nutritionix app id.
1. In the ```docker-compose.yml``` file, replace ```get_a_nutritionix_app_key``` with your nutritionix app key.
1. Run ```docker-compose build```
1. In a separate terminal in this directory, run ```docker-compose up``` and wait for no more output from that terminal.
   Leave that terminal open.
1. Run ```python -m unittest system_test.py```. This will run all the system tests.
1. In the terminal running docker-compose hit ctrl-c.




