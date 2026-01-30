from flask import Flask, request, render_template, jsonify, request, abort, redirect, url_for
from json import load as jsonload
#from pprint import pprint
# pprint has no uses
from database import executedb, make_table, integrity_error
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, \
    login_required, current_userf
from usermixin import User
import webbrowser
import time
import datetime

app = Flask(__file__)

app.config["SECRET_KEY"] = "7y39084q3479"

auth = LoginManager(app)
auth.login_view = 'login'

@auth.user_loader
def load_user(user_id):
    user = executedb(
        'SELECT * FROM users WHERE id = ?', (user_id,))
    if user is not None:
        return User(*tuple(user.values())[:3])
    return None

#@app.route("/", methods=["GET"])
#def index():
#    return render_template("index.html")

# @app.route("/<name>/")
# def name(name):
#     return render_template("name.html", name=name)

def show_error(error: str):
    return redirect(f"/error?payload={error}")

@app.route('/register')
@app.route('/register/')
def register():
    return render_template("register.html")

@app.route('/login')
@app.route('/login/')
def login():
    return render_template("login.html")

#@app.route("/domashka/")
#def domashka():
#    return render_template("domashka.html", link="https://www.youtube.com/@rockettechschool")

@app.route("/") # /posts
@app.route("/posts")
def posts():
    index_command = """
        SELECT posts.id, posts.title, posts.desc, posts.theme, posts.user_id, posts.views, users.username, count(post_likes.post_id) as likes
        FROM posts
        JOIN users ON posts.user_id=users.id
        LEFT JOIN post_likes ON posts.id = post_likes.post_id
        GROUP BY posts.id, posts.title, posts.desc, posts.theme, posts.user_id, posts.views, users.username
    """

    content = executedb(index_command, all=True)
    #pprint(content)

    # check for user authorization
    display_login = False
    if not current_user.is_authenticated:
        display_login = True
        user_likes = []
    else:
        result = executedb("SELECT post_id FROM post_likes WHERE user_id = ?", (current_user.id,), all=True)
        user_likes = [post["post_id"] for post in result]

    for post in content:
        if not post["theme"]:
            post["theme"] = "No theme"
    return render_template("test.html", posts=content, current_user=current_user, display_login=display_login, user_likes=user_likes)

@app.route("/post/<id>")
def post(id):
    content_command = """
        SELECT posts.id, posts.desc, posts.theme, posts.user_id, posts.views, COUNT(post_likes.post_id) AS likes

        FROM posts LEFT JOIN post_likes

        ON posts.id = post_likes.post_id

        WHERE id = ?
        GROUP BY posts.id, posts.desc, posts.theme, posts.user_id, posts.views
    """
    content = executedb(content_command, (id,))
    if not content["theme"]:
        content["theme"] = "No theme"
    
    # increase view count
    executedb("UPDATE posts SET views = views + 1 WHERE id = ?", (id,))
    
    # fetch likes
    user_likes = False
    if current_user.is_authenticated:
        user_likes = bool(executedb("SELECT post_id FROM post_likes WHERE user_id = ? AND post_id = ?", (current_user.id, content["id"]), all=True))

    # fetch comments
    comments = executedb("SELECT comments.id, comments.post_id, comments.content, comments.timestamp, users.username AS author_username FROM comments JOIN users ON comments.author_id = users.id WHERE comments.post_id = ?", (id,), all=True)

    return render_template("post.html", post=content, user_likes=user_likes, comments=comments)

@app.route("/add")
@login_required
def add_post():
    return render_template("add_post.html")

@app.route("/api/add_post", methods=['POST'])
@login_required
def api_add_post():
    body = request.form
    try:
        executedb(
            "INSERT INTO posts (title, desc, user_id) VALUES (?,?,?)",
            (body["title"],body["description"], current_user.id)
        )
    except Exception as e:
        print("Error: ", e)
        abort(500)
    return redirect(url_for("posts"))

@app.route("/api/register", methods=["POST"])
def api_register():
    body = request.form
    if not body:
        return show_error("kkfkfseoesfkp")
    
    if executedb("SELECT id FROM users WHERE username = ?", (body["username"],)):
        return show_error("User already exists")

    params = [body["username"], body["password"], body["email"]]
    for i in params:
        if not i:
            return show_error("One of the fields are missing")
    
    password = generate_password_hash(body["password"])
    params[1] = password
    
    executedb("INSERT INTO users (username, password, email) VALUES (?,?,?)",
              params)
    return redirect(url_for("login"))

@app.route("/api/login", methods=["POST"])
def api_login():
    body = request.form
    
    # get the user row
    user_row = executedb("SELECT * FROM users WHERE username = ?", (body["username"],))
    if not user_row:
        return 

    # structured params
    params = (body["username"], body["password"])
    for i in params: # check if fields missing
        if not i:
            return show_error("One of the fields are missing")
    
    verify_password = check_password_hash(user_row["password"], params[1])
    if not verify_password:
        return show_error("Password is wrong")

    user_mixin_friendly = user_row.copy()
    user_mixin_friendly["password_hash"] = user_row["password"]
    del user_mixin_friendly["password"]
    del user_mixin_friendly["email"]
    # and we get id, username, password

    login_user(User(**user_mixin_friendly))

    return redirect(url_for("posts"))

@app.route("/api/logout")
@login_required
def api_logout():
    logout_user()
    return redirect(url_for("posts"))

@app.route("/api/delete_post/<post_id>", methods=["POST"])
@login_required
def api_delete_post(post_id):
    post = executedb("SELECT * FROM posts WHERE id = ?", (post_id,))
    
    # post exist?
    if not post:
        return show_error("This post doesn't exist.")
    
    # user ownership?
    if post["user_id"] != current_user.id:
        return show_error("Its not your post.")
    
    try:
        executedb("DELETE FROM posts WHERE id = ?", (post_id,))
    except integrity_error:
        return abort(500)

    return redirect(url_for("posts"))

@app.route("/api/like/<post_id>")
@login_required
def api_like(post_id):
    # check if post exists
    if not executedb("SELECT id FROM posts WHERE id = ?", (post_id,)):
        return show_error("This post doesn't exist.")
    
    redir = request.args["redirect"]

    # check if post liked by user already
    if executedb("SELECT * FROM post_likes WHERE user_id = ? AND post_id = ?", (current_user.id, post_id)):
        # remove the like
        executedb("DELETE FROM post_likes WHERE user_id = ? AND post_id = ?", (current_user.id, post_id))
        print(f"Like removed from {post_id}")
        return redirect(redir)
    else:
        # make a new "like" entry
        executedb("INSERT INTO post_likes VALUES (?,?)", (post_id, current_user.id))
        print(f"Like added to {post_id}")
        return redirect(redir)

@app.route("/api/new_comment/<post_id>", methods=["POST"])
@login_required
def api_new_comment(post_id):
    form = request.form
    content = form["contents"]
    if not executedb("SELECT id FROM posts WHERE id = ?", (post_id,)):
        return show_error("This post doesn't exist.")
    executedb("INSERT INTO comments(post_id, content, timestamp, author_id) VALUES (?,?,?,?)",
              (post_id, content, time.time()//1, current_user.id))
    return redirect(f"/post/{post_id}")

@app.route("/error")
def error():
    return render_template("error.html", payload=request.args.get("payload", "Unknown error"), link=request.args.get("link", "/posts"))

webbrowser.open("http://127.0.0.1:5000")
app.run()