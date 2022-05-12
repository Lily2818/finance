import datetime
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
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
@login_required #cannot access the page without the login
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    current_stock_db = db.execute("SELECT symbol, shares, price FROM transactions WHERE user_id =?", user_id)
    current_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    current_cash = current_cash_db[0]["cash"]
    return render_template("index.html", current_stock=current_stock_db, current_cash=current_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method=="GET":
        return render_template("buy.html")
    else:
        current_shares=request.form.get("shares")
        current_symbol=request.form.get("symbol")
        if not current_shares:
            return apology("Number of Shares required")
        if not current_symbol:
            return apology("Symbol Required")

        stock = lookup(current_symbol)
        if stock == None:
            return apology("Stock Does Not Exist")
        if int(current_shares) <= 0 :
            return apology("Shares must be greater than 0")

        #check price of shares of stocks
        stock_price = int(current_shares) * stock["price"]

        user_id = session["user_id"]
        current_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)#returns a list with a dictionary
        current_cash = current_cash_db[0]["cash"] #get 1st element of the list in dict & the value of key:value pair [{cash:10000}]
        
        if current_cash < stock_price: #check if cash is more than stock price
            return apology("No sufficient cash")
        remaining_cash = current_cash - stock_price

        #UPDATE table_name SET column1 = value1, column2 = value2, ...WHERE condition;
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remaining_cash, user_id ) #if cash is > stock price, update the users db

        #INSERT INTO table_name (column1, column2, column3, ...)VALUES (value1, value2, value3, ...);
        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transaction_date)VALUES (?, ?,?,?,?)", user_id, current_symbol, current_shares, stock_price, date)
        return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    history_db=db.execute("SELECT * FROM transactions WHERE user_id = ?", user_id)
    return render_template("history.html", history=history_db)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear() #remove all previous cookies

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    if request.method== "GET":
        return render_template("quote.html")
    else:
        current_symbol = request.form.get("symbol")
        if not current_symbol:
            return apology("Symbol Required")

        stock = lookup(current_symbol) # will return two options- none or dictionary(sym,name,price)
        if stock == None:
            return apology("Stock Does Not Exist")#next step : create quoted.html
        return render_template("quoted.html", quoted=stock)#quoted-where we store information on "stock"


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        #GET DATA FROM THE FORM
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not username:
            return apology("Username Required")
        if not password:
            return apology("Password Required")
        if not confirm_password:
            return apology("Password Required")
        if password != confirm_password:
            return apology("Passwords Do Not Match")
        #create variable to store pword; Hash user's pword  with generate_pword_hash;hash secures the pword
        hash_pword = generate_password_hash(password) #call function gen_pword_hash & store result in variable

        #check all data from sql if username already exists
        check_usernames = db.execute("SELECT * FROM users WHERE username = ?", username)
        #if username doesnt exist, check_usernames will be an empty list
        #if username already exists, check_usernames will be a list with one item(dictionary)
        if len(check_usernames) != 0:
            return apology("Username already exists")
        #INSERT INTO table_name (column1, column2, column3, ...)VALUES (value1, value2, value3, ...);
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_pword)
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_id = session["user_id"]
        sell_stock_db = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", sell_stock= sell_stock_db)

    else:
        current_symbol = request.form.get("symbol")
        current_shares = request.form.get("shares")
        if not current_shares:
            return apology("Number of Shares Required")
        if int(current_shares) < 1:
            return apology("Shares must be greater than 0")

        #need to know price of the symbol * current_shares
        stock = lookup(current_symbol)
        total_sale =  int(current_shares) * stock["price"]
        user_id = session["user_id"]
        current_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        current_cash = current_cash_db[0]["cash"]
        remaining_cash = current_cash + total_sale

        #update remaining user's cash
        #UPDATE table_name SET column1 = value1, column2 = value2, ...WHERE condition;
        db.execute("UPDATE users SET cash= ? WHERE id = ? ",remaining_cash, user_id)

        date = datetime.datetime.now()
       #INSERT INTO table_name (column1, column2, column3, ...)VALUES (value1, value2, value3, ...);
        db.execute("INSERT INTO transactions(user_id, symbol, shares, price, transaction_date)VALUES (?, ?, ?, ?, ?)", user_id, current_symbol, (-1) * current_shares, total_sale, date)
        return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
