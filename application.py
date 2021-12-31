import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT symbol, SUM(shares) AS shares FROM stocks WHERE user_id=:uid GROUP BY symbol;", uid = session["user_id"])
    totalValue = 0
    if len(rows) != 0:
        for row in rows:
            total = 0
            #CHANGE1
            ROWDATA = lookup(row["symbol"])
            row["name"] = ROWDATA["name"]
            print(row)
            row["price"] = usd(ROWDATA["price"])
            total = ROWDATA["price"] * row["shares"]
            totalValue += total
            row["total"] = usd(total)
        credit = db.execute("SELECT cash FROM users WHERE id = :uid", uid = session["user_id"])
        #CHANGE2
        BALANCE = float(credit[0]["cash"])
        return render_template("index.html", rows = rows, balance = usd(BALANCE), totalValue = usd(totalValue + BALANCE))
    else:
        return render_template("index.html", message = "Empty portfolio")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    symbol = request.form.get("symbol")
    try:
        print(request.form.get('shares'))
        shares = int(request.form.get('shares'))
    except:
        return apology('Invalid Field',400)
    # shares = int(request.form.get("shares"))
    if not symbol or not shares:
        return apology("Enter both fields")
    response = lookup(symbol)
    if not response:
        return apology("Invalid symbol")
    symbol = response["symbol"]
    price = float(response["price"])
    #CHANGE3
    QUERY = db.execute("SELECT cash FROM users WHERE id = :uid", uid = session["user_id"])
    cashValue = float(QUERY[0]["cash"])
    if shares <= 0:
        return apology("Provide number of shares to buy")
    elif price * shares > cashValue:
        return apology("You don't have enough money")
    else:
        cashSpent = price * shares
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (:uid, :symbol, :shares, :price);", uid=session["user_id"], symbol = symbol, shares = shares, price = price * shares)
        db.execute("INSERT INTO stocks (user_id, symbol, shares) VALUES (:uid, :symbol, :shares);", uid=session["user_id"], symbol=symbol, shares = shares)
        db.execute("UPDATE users SET cash = :cash WHERE id = :uid", cash = cashValue - cashSpent, uid = session["user_id"])
        flash("Bought Successfully")
        return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM transactions WHERE user_id = :uid", uid = session["user_id"])
    return render_template("history.html", rows = rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""
    # User reached route via POST (as by submitting a form via POST)

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html", message = "get")
    symbol = request.form.get("symbol")
    response = lookup(symbol)
    if response is None:
        return apology("Enter a valid symbol")
    return render_template("quote.html", price = usd(response["price"]), symbol = response["symbol"], name = response["name"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    #forget any user_id
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must confirm your password", 400)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("your password doesn't match", 400)
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = :username", username = username)
        if len(rows) != 0:
            return apology("Username already exist")
        password = generate_password_hash(request.form.get("password"))
        id = db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)", username = username, password = password)
        #If id has a value (if the insertion to database was success, it'll return the primary key value and we stored it in id)
        if not id is None:
            session["user_id"] = id
        flash("Registered!")
        return redirect("/")
    else:
        return render_template("reg.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        rows = db.execute("SELECT symbol, SUM(shares) FROM stocks WHERE user_id = :uid GROUP BY symbol;", uid = session["user_id"])
        return render_template("sell.html", rows = rows)
    else:
        if not request.form.get("symbol"):
            return apology("Enter a valid symbol")
        elif not request.form.get("shares"):
            return apology("Enter amount of shares")
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        row = db.execute("SELECT SUM(shares) AS shares FROM stocks WHERE user_id = :uid AND symbol = :symbol;", uid = session["user_id"], symbol = symbol)
        if shares > int(row[0]["shares"]):
            return apology("TOO MANY SHARES")
        else:
            response = lookup(symbol)
            price = float(response["price"])
            #CHANGE4
            QUERY = db.execute("SELECT cash FROM users WHERE id = :uid", uid = session["user_id"])
            cashValue = float(QUERY[0]["cash"])
            cashValue += price * shares
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (:uid, :symbol, :shares, :price)",uid = session["user_id"], symbol = symbol, shares = shares, price = shares * price)
            db.execute("INSERT INTO stocks (user_id, symbol, shares) VALUES (:uid, :symbol, :shares);", uid=session["user_id"], symbol=symbol, shares = -shares)
            db.execute("UPDATE users SET cash = :cash WHERE id = :uid", cash = cashValue, uid = session["user_id"])
            return redirect("/")





def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
    # export API_KEY=pk_47f860a68954467c8e4fb1d14f0ce911