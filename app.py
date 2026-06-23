######################################
# VERSUS skeleton app.py
# CS460 Final Project
######################################
# Covers the core: register/login, create bracket, browse, view.
# Students extend with: predictions, voting, round-closing (stored
# procedure), triggers, leaderboard (window functions), recursive CTE,
# follows, comments, indexes.
###################################################

import flask
from flask import Flask, request, render_template, redirect, url_for
import mysql.connector
import flask_login
import datetime

app = Flask(__name__)
app.secret_key = "super secret string"  # Change this!

# These will need to be changed according to your credentials.
DB_USER = "root"
DB_PASSWORD = "Cs460pw!123"
DB_NAME = "versus"
DB_HOST = "localhost"


def get_conn():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )


conn = get_conn()


# begin code used for login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)


def getUserList():
    cursor = conn.cursor()
    cursor.execute("SELECT username from Users")
    rows = cursor.fetchall()
    cursor.close()
    return rows


class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(username):
    users = getUserList()
    if not (username) or username not in str(users):
        return
    user = User()
    user.id = username
    return user


@login_manager.request_loader
def request_loader(request):
    users = getUserList()
    username = request.form.get("username")
    if not (username) or username not in str(users):
        return
    user = User()
    user.id = username
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM Users WHERE username = '{0}'".format(username))
    data = cursor.fetchall()
    cursor.close()
    pwd = str(data[0][0])
    user.is_authenticated = request.form["password"] == pwd
    return user


"""
A new page looks like this:
@app.route('new_page_name')
def new_page_function():
    return new_page_html
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return """
            <form action='login' method='POST'>
                <input type='text' name='username' id='username' placeholder='username' />
                <input type='password' name='password' id='password' placeholder='password' />
                <input type='submit' name='submit' />
            </form><br />
            <a href='/'>Home</a>
        """
    # The request method is POST (page is receiving data)
    username = request.form["username"]
    cursor = conn.cursor()
    # check if username is registered
    cursor.execute("SELECT password FROM Users WHERE username = '{0}'".format(username))
    data = cursor.fetchall()
    cursor.close()
    if data:
        pwd = str(data[0][0])
        if request.form["password"] == pwd:
            user = User()
            user.id = username
            flask_login.login_user(user)
            return redirect(url_for("home"))
    # information did not match
    return "<a href='/login'>Try again</a><br />\
            <a href='/register'>or make an account</a>"


@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template("unauth.html")


# you can specify specific methods (GET/POST) in the function header instead
# of inside the function body
@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register_user():
    try:
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        bio = request.form.get("bio")
    except:
        print("couldn't find all tokens")
        return redirect(url_for("register"))
    cursor = conn.cursor()
    if isUsernameUnique(username):
        cursor.execute(
            "INSERT INTO Users (username, email, password, bio) VALUES ('{0}', '{1}', '{2}', '{3}')".format(
                username, email, password, bio or ""
            )
        )
        conn.commit()
        cursor.close()
        # log user in
        user = User()
        user.id = username
        flask_login.login_user(user)
        return render_template("hello.html", name=username, message="account created")
    else:
        cursor.close()
        print("username already in use")
        return redirect(url_for("register"))


def isUsernameUnique(username):
    # use this to check if a username has already been registered
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM Users WHERE username = '{0}'".format(username))
    rows = cursor.fetchall()
    cursor.close()
    return len(rows) == 0


def getUserIdFromUsername(username):
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM Users WHERE username = '{0}'".format(username))
    row = cursor.fetchone()
    cursor.close()
    return row[0] if row else None


def getUsernameFromUserId(uid):
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM Users WHERE user_id = '{0}'".format(uid))
    row = cursor.fetchone()
    cursor.close()
    return row[0] if row else None


# end login code


# begin bracket creation code
@app.route("/create", methods=["GET", "POST"])
@flask_login.login_required
def create_bracket():
    if request.method == "POST":
        uid = getUserIdFromUsername(flask_login.current_user.id)
        title = request.form.get("title")
        description = request.form.get("description")
        entrant_count = int(request.form.get("entrant_count"))
        cursor = conn.cursor()

        # 1. insert the bracket row
        cursor.execute(
            "INSERT INTO Brackets (host_id, title, description, entrant_count) VALUES ('{0}', '{1}', '{2}', '{3}')".format(
                uid, title, description or "", entrant_count
            )
        )
        cursor.execute("SELECT LAST_INSERT_ID()")
        bracket_id = cursor.fetchone()[0]

        # 2. insert all entrants in seed order
        entrant_ids = []
        for seed in range(1, entrant_count + 1):
            entrant_name = request.form.get("entrant_" + str(seed))
            cursor.execute(
                "INSERT INTO Entrants (bracket_id, seed, name) VALUES ('{0}', '{1}', '{2}')".format(
                    bracket_id, seed, entrant_name
                )
            )
            cursor.execute("SELECT LAST_INSERT_ID()")
            entrant_ids.append(cursor.fetchone()[0])

        # 3. create Round 1 matchups (seed pairs: 1v2, 3v4, ...)
        round_1_slots = entrant_count // 2
        for slot in range(1, round_1_slots + 1):
            a = entrant_ids[(slot - 1) * 2]
            b = entrant_ids[(slot - 1) * 2 + 1]
            cursor.execute(
                "INSERT INTO Matchups (bracket_id, round, slot, entrant_a_id, entrant_b_id) VALUES ('{0}', 1, '{1}', '{2}', '{3}')".format(
                    bracket_id, slot, a, b
                )
            )

        # 4. create empty shells for later rounds
        slots = round_1_slots // 2
        round_num = 2
        while slots >= 1:
            for slot in range(1, slots + 1):
                cursor.execute(
                    "INSERT INTO Matchups (bracket_id, round, slot) VALUES ('{0}', '{1}', '{2}')".format(
                        bracket_id, round_num, slot
                    )
                )
            slots //= 2
            round_num += 1

        conn.commit()
        cursor.close()
        return redirect(url_for("view_bracket", bracket_id=bracket_id))
    else:
        return render_template("create.html")


# end bracket creation code


# begin browse code
def getAllBrackets():
    cursor = conn.cursor()
    cursor.execute(
        "SELECT b.bracket_id, b.title, b.status, b.entrant_count, b.created_at, u.username "
        "FROM Brackets b JOIN Users u ON b.host_id = u.user_id "
        "ORDER BY b.created_at DESC"
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


@app.route("/browse", methods=["GET"])
def browse():
    brackets = getAllBrackets()
    return render_template("browse.html", brackets=brackets)


# end browse code


# begin bracket view code
def getBracketInfo(bracket_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT b.bracket_id, b.title, b.description, b.status, b.entrant_count, u.username "
        "FROM Brackets b JOIN Users u ON b.host_id = u.user_id "
        "WHERE b.bracket_id = '{0}'".format(bracket_id)
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def getMatchupsForBracket(bracket_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT m.matchup_id, m.round, m.slot,ea.entrant_id, ea.name,eb.entrant_id, eb.name, ew.name, m.votes_a, m.votes_b "
        "FROM Matchups m "
        "LEFT JOIN Entrants ea ON ea.entrant_id = m.entrant_a_id "
        "LEFT JOIN Entrants eb ON eb.entrant_id = m.entrant_b_id "
        "LEFT JOIN Entrants ew ON ew.entrant_id = m.winner_entrant_id "
        "WHERE m.bracket_id = '{0}' "
        "ORDER BY m.round, m.slot".format(bracket_id)
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


@app.route("/bracket<bracket_id>", methods=["GET"])
def view_bracket(bracket_id):
    bracket = getBracketInfo(bracket_id)
    matchups = getMatchupsForBracket(bracket_id)

    # comments
    comments = {}
    for matchup in matchups:
        matchup_id = matchup[0]
        comments[matchup_id] = getcommentformatchup(matchup_id)

    # for user
    a = []
    if flask_login.current_user.is_authenticated:
        u = getUserIdFromUsername(flask_login.current_user.id)
        a = achievements(u)
    return render_template("bracket.html", bracket=bracket, matchups=matchups, a=a,comments=comments)


# end bracket view code

# prediction route


@app.route("/submit_prediction", methods=["POST"])
@flask_login.login_required
def submitprediction():
    u = getUserIdFromUsername(flask_login.current_user.id)
    cursor = conn.cursor()
    # print(request.form)
    try:
        submitted_at = datetime.datetime.now()
        for key in request.form:
            if key.startswith("pick_"):
                cursor.execute(
                    """
                INSERT INTO Predictions(user_id, matchup_id, entrant_id, submitted_at)
                VALUES(%s,%s,%s,%s)
                """,
                    (u, key.split("_")[1], request.form[key], submitted_at),
                )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(e)
    cursor.close()
    return redirect(url_for("view_bracket", bracket_id=request.form.get("bracket_id")))


@app.route("/vote", methods=["POST"])
@flask_login.login_required
def vote():
    cursor = conn.cursor()
    matchup_id = request.form.get("matchup_id")
    voted_for = request.form.get("entrant_id")
    for key, value in request.form.items():
        if key.startswith("matchup_id"):
            matchup_id = value
        elif key.startswith("entrant_id"):
            voted_for = value

    if matchup_id and voted_for:
        try:
            cursor.execute(
                """ INSERT INTO Votes(user_id, matchup_id, voted_for)
                  VALUES(%s,%s,%s)""",
                (
                    getUserIdFromUsername(flask_login.current_user.id),
                    matchup_id,
                    voted_for,
                ),
            )
            cursor.execute(
                """ UPDATE Matchups
                SET votes_a=votes_a+CASE WHEN entrant_a_id=%s THEN 1 ELSE 0 END,
                     votes_b=votes_b+CASE WHEN entrant_b_id=%s THEN 1 ELSE 0 END
                WHERE matchup_id=%s""",
                (voted_for, voted_for, matchup_id),
            )
            conn.commit()
            return redirect(
                url_for("view_bracket", bracket_id=request.form.get("bracket_id"))
            )
        except mysql.connector.errors.IntegrityError:
            conn.rollback()
            return redirect(
                url_for("view_bracket", bracket_id=request.form.get("bracket_id"))
            )
        except Exception as e:
            conn.rollback()
            return redirect(
                url_for("view_bracket", bracket_id=request.form.get("bracket_id"))
            )
        finally:
            cursor.close()


@app.route("/close_round", methods=["POST"])
@flask_login.login_required
def close_round():
    cursor = conn.cursor()

    try:
        bid = request.form.get("bracket_id")
        r = request.form.get("round")
        cursor.callproc("close_round", [bid, r])
        conn.commit()
        return redirect(url_for("view_bracket", bracket_id=bid))
    except Exception as e:
        conn.rollback()
        print(e)
        return redirect(url_for("view_bracket", bracket_id=bid))
    finally:
        cursor.close()


def achievements(u):
    cursor = conn.cursor()
    cursor.execute(
        """ SELECT a.name 
                   FROM User_Achievements ua
                   JOIN Achievements a 
                   ON ua.achievement_code=a.achievement_code
                   WHERE ua.user_id=%s""",
        (u,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


@app.route("/profile/<username>", methods=["GET"])
def profile(username):
    user_id = getUserIdFromUsername(username)
    if user_id:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE user_id=%s", (user_id,))
        user = cursor.fetchone()
        
        cursor.execute("SELECT u.username FROM Follows f JOIN Users u ON f.follower_id=u.user_id WHERE f.followed_id=%s",(user_id,))
        followers=cursor.fetchall()
        
        cursor.execute("SELECT u.username FROM Follows f JOIN Users u ON f.followed_id=u.user_id WHERE f.follower_id=%s",(user_id,))
        following=cursor.fetchall()
        


        cursor.close()
        user_achievements = achievements(user_id)
        return render_template(
            "profile.html",
              user=user, 
              achievements=user_achievements,
              followers=followers,
              following=following,
        )
    else:
        return "User not found", 404


@app.route("/comment", methods=["POST"])
@flask_login.login_required
def add():
    user_id = getUserIdFromUsername(flask_login.current_user.id)
    matchup_id = request.form.get("matchup_id")
    content = request.form.get("content")

    if user_id and matchup_id and content:
        cursor = conn.cursor()
        cursor.execute(
            """
                       INSERT INTO Comments(user_id,matchup_id, content)
                       VALUES(%s,%s,%s)""",
            (user_id, matchup_id, content),
        )
        conn.commit()
        cursor.close()
    return redirect(request.referrer)


def getcommentformatchup(matchup_id):
    cursor = conn.cursor()
    cursor.execute(
        """
                   SELECT c.content, u.username, c.created_at
                   FROM Comments c 
                   JOIN USERS u on c.user_id=u.user_id 
                   WHERE c.matchup_id=%s
                   ORDER BY c.created_at DESC """,
        (matchup_id,),
    )
    comments = cursor.fetchall()
    cursor.close()
    return comments


@app.route("/follows/<username>",methods=["POST"])
@flask_login.login_required
def follows(username):
    follower_id=getUserIdFromUsername(flask_login.current_user.id)
    followed_id=getUserIdFromUsername(username)
    cursor=conn.cursor()
    cursor.execute(
        "SELECT 1 FROM Follows WHERE follower_id=%s AND followed_id=%s",(follower_id,followed_id),
    
    )
    if cursor.fetchone():
        cursor.execute(
         "DELETE FROM Follows WHERE follower_id=%s AND followed_id=%s",(follower_id,followed_id)
       
        )
    else:
        try:
          cursor.execute(
            "INSERT INTO Follows(follower_id,followed_id)VALUES(%s,%s)",(follower_id,followed_id))
        except mysql.connector.errors.DatabaseError:
           conn.rollback()
    conn.commit()
    cursor.close()
    return redirect(url_for("profile",username=username))
    
        
        
@app.route("/leaderboard")
def leaderboard():
    cursor=conn.cursor()
    cursor.execute("""
                   SELECT u.username, SUM(p.points_earned) as total_points,
                   RANK() OVER(ORDER BY SUM(p.points_earned) DESC) as rnk,
                   DENSE_RANK() OVER (ORDER BY SUM(p.points_earned) DESC) as d,
                   PERCENT_RANK() OVER (ORDER BY SUM(p.points_earned) DESC) as pre
                   FROM Predictions p JOIN Users u ON p.user_id =u.user_id
                   GROUP BY u.user_id, u.username
                   ORDER BY total_points DESC""")
    rows=cursor.fetchall()
    cursor.close()
    me=flask_login.current_user.id if flask_login.current_user.is_authenticated else None
    return render_template("leaderboard.html",rows=rows,me=me)




@app.route("/champion/<bracket_id>")
def champion(bracket_id):
    cursor=conn.cursor()
    query="""
    WITH RECURSIVE champion AS(
    SELECT matchup_id,round, winner_entrant_id
    FROM Matchups
    WHERE bracket_id=%s
    AND round=(
    SELECT MAX(round)
    FROM Matchups
    WHERE bracket_id=%s)
    UNION ALL
    SELECT m.matchup_id,m.round,m.winner_entrant_id 
    FROM Matchups m 
    JOIN champion c
    ON m.winner_entrant_id=c.winner_entrant_id
    WHERE m.bracket_id=%s 
    AND m.round=c.round-1)
    
    SELECT champion.round, Entrants.name 
    FROM champion
    JOIN Entrants
    ON champion.winner_entrant_id=Entrants.entrant_id
    ORDER BY champion.round;"""
    cursor.execute(query,(bracket_id, bracket_id, bracket_id))
    path=cursor.fetchall()
    cursor.close()
    return render_template("champion.html",rows=path)





# default page
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        flask_login.logout_user()
    try:
        username = flask_login.current_user.id
        return render_template("hello.html", name=username, message="welcome to VERSUS")
    except AttributeError:  # not logged in
        return render_template("hello.html", message=None)


if __name__ == "__main__":
    # this is invoked when in the shell you run
    # $ python app.py
    app.debug = True
    app.run(port=5001, debug=True)
