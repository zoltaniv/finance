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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get all user's shares from transactions
    rows = db.execute(
        "SELECT symbol, company, SUM(shares) AS allshares, price, dealprice FROM transactions WHERE id = :userid GROUP BY symbol", userid=session["user_id"])
    '''i = 0
    for dic in rows:
        if dic["allshares"] == 0:
            rows.pop(i)
            i += 1
        else:
            i += 1'''

    user = db.execute("SELECT * FROM users WHERE id = :userid",
                      userid=session["user_id"])

    username = user[0]["username"]
    cash = user[0]["cash"]
    capital = cash

    # return apology("1")
    # Get fresh price of all shares
    for row in rows:
        share = lookup(row["symbol"])
        row["price"] = share["price"]
        # Get the price of all shares
        row["dealprice"] = row["price"] * row["allshares"]
        # Get all the capital
        capital += row["dealprice"]

    for row in rows:
        row["price"] = usd(row["price"])
        row["dealprice"] = usd(row["dealprice"])

    # Formats values to the money format
    capital = usd(capital)
    cash = usd(cash)

    return render_template("index.html", rows=rows, cash=cash, capital=capital, username=username)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        userid = session["user_id"]

        # Ensure symbol was submitted
        if not symbol or symbol.isspace():
            return apology("You must provide the symbol of company!", 400)
        # Ensure shares was submitted
        elif not shares or not shares.isnumeric():
            return apology("You must provide the right quantity of shares!", 400)

        # Ensure symbol exist and get its price
        share = lookup(request.form.get("symbol"))

        if share is None:
            return apology("Sorry, this symbol does not exist", 400)
        # ................................................................................
        sharename = share["name"]
        shareprice = share["price"]
        sharesymbol = share["symbol"]
        shares = int(shares)

        # Check how much maney in user
        user = db.execute(
            "SELECT * FROM users WHERE id = :userid", userid=userid)
        usercash = user[0]["cash"]

        # Price of shares
        dealprice = shareprice * shares

        # Is there enough monay for buying shares
        if usercash < dealprice:
            return apology("You have not enough monay to buy the number of shares!", 400)

        # Buy shares
        usercash = usercash - dealprice
        action = "buy"
        # Add trasaction in the trasactions table
        db.execute("INSERT INTO transactions (id, action, symbol, company, price, shares, dealprice) VALUES (:userid, :action, :sharesymbol, :sharename, :shareprice, :shares, :dealprice)",
                   userid=userid, action=action, sharesymbol=sharesymbol, sharename=sharename, shareprice=shareprice, shares=shares, dealprice=dealprice)

        # Change cash in the users table
        db.execute("UPDATE users SET cash = :usercash WHERE id = :userid",
                   usercash=usercash, userid=userid)

        # Redirect user to home page
        return redirect("/")

    else:
        user = db.execute("SELECT * FROM users WHERE id = :userid",
                      userid=session["user_id"])
        username = user[0]["username"]
        
        return render_template("buy.html", username=username)


@app.route("/check", methods=["GET"])
def check():

    username = request.args.get("username")

    # Ensure username was submitted
    if not username:
        return apology("Must provide username", 400)

    name = db.execute("SELECT username FROM users WHERE username = :username",
                        username=request.args.get("username"))
    
    if len(name) == 0:
        return jsonify(username=True)
    else:
        return jsonify(username=False)
    

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute(
        "SELECT action, symbol, company, price, shares, dealprice, date FROM transactions WHERE id = :userid", userid=session["user_id"])
    
    user = db.execute("SELECT * FROM users WHERE id = :userid",
                      userid=session["user_id"])
    username = user[0]["username"]
    return render_template("history.html", username=username, rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
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

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol of company", 400)

        # Get the symbol of the company
        company = request.form.get("symbol")
        # Get information about the company in the dict structure
        inf = lookup(company)
        
        if inf == None:
            return apology("The symbol of company not exist", 400)

        # Pass the information to the quote.html and return the page
        user = db.execute("SELECT * FROM users WHERE id = :userid",
                      userid=session["user_id"])
        username = user[0]["username"]
        return render_template("quoted.html", username=username, inf=inf)

    else:
        user = db.execute("SELECT * FROM users WHERE id = :userid",
                      userid=session["user_id"])
        username = user[0]["username"]
        return render_template("quote.html", username=username)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username", 400)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("Must provide password", 400)
        
        # Ensure confirmation was submitted
        if not request.form.get("confirmation"):
            return apology("Must provide confirmation", 400)
        
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        if password != confirmation:
            return apology("Your password and confirmation are different", 400)

        # Query database for username
        checkname = db.execute("SELECT * FROM users WHERE username = :username",
                               username=request.form.get("username"))

        # Check username exist
        if checkname:
            return apology("Your username already exists! You must provide another username!", 400)

        # Hash the password of the user
        hash_pwrd = generate_password_hash(request.form.get("password"))

        # Insert a new user to the database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash_pwrd)",
                   username=request.form.get("username"), hash_pwrd=hash_pwrd)

        # Query database for username
        newuser = db.execute("SELECT * FROM users WHERE username = :username",
                             username=request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = newuser[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Save data of request in the variables
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        userid = session["user_id"]

        # Ensure symbol was submitted
        if not symbol or symbol.isspace():
            return apology("You must provide the symbol of company!", 403)
        # Ensure shares was submitted
        elif not shares or not shares.isnumeric():
            return apology("You must provide the right quantity of shares!", 403)

        shares = int(shares)
        ok = 0

        # Check how much shares in user
        user = db.execute(
            "SELECT symbol, SUM(shares) AS allshares FROM transactions WHERE id = :userid GROUP BY symbol", userid=userid)

        for r in user:
            if r["symbol"] == symbol and r["allshares"] >= shares:
                ok = 1
                break

        if ok == 0:
            return apology("You don't have shares")

        # Ensure symbol exist and get its price
        share = lookup(symbol)

        if share is None:
            return apology("Sorry, this symbol does not exist", 403)
        # ................................................................................
        sharename = share["name"]
        shareprice = share["price"]
        sharesymbol = share["symbol"]
        dealprice = 0

        # Check how much maney in user
        line = db.execute(
            "SELECT * FROM users WHERE id = :userid", userid=userid)
        usercash = line[0]["cash"]

        # Price of shares
        dealprice = shareprice * shares
        # Sell shares
        usercash = usercash + dealprice
        # Decrise number of shares
        shares *= -1
        action = "sell"

        # Add trasaction in the trasactions table
        db.execute("INSERT INTO transactions (id, action, symbol, company, price, shares, dealprice) VALUES (:userid, :action, :sharesymbol, :sharename, :shareprice, :shares, :dealprice)",
                   userid=userid, action=action, sharesymbol=sharesymbol, sharename=sharename, shareprice=shareprice, shares=shares, dealprice=dealprice)

        # Change cash in the users table
        db.execute("UPDATE users SET cash = :usercash WHERE id = :userid",
                   usercash=usercash, userid=userid)

        # Redirect user to home page
        return redirect("/")

    else:
        rows = db.execute(
            "SELECT symbol FROM transactions WHERE id = :userid GROUP BY symbol", userid=session["user_id"])
        user = db.execute("SELECT * FROM users WHERE id = :userid",
                      userid=session["user_id"])
        username = user[0]["username"]
        return render_template("sell.html", username=username, rows=rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
