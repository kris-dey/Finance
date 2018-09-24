from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

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
    transactions = db.execute("SELECT symbol,quantity,price,userId FROM history WHERE userId=:userId GROUP BY symbol;", userId=session['user_id'])
    money = 0

    for symbols in transactions:
        symbol = symbols["symbol"]
        shares = symbols["quantity"]
        stock = lookup(symbol)
        total = shares * stock["price"]
        db.execute("UPDATE history SET price=:price WHERE userId=:userId AND symbol=:symbol", price=usd(stock["price"]), userId=session['user_id'], symbol=symbol)

    updatedMoney = db.execute("SELECT cash FROM users WHERE userId=:userId", userId=session['user_id'])

    money += updatedMoney[0]["cash"]

    updated_portfolio = db.execute("SELECT * from history WHERE userId=:userId", userId=session['user_id'])

    return render_template("index.html", stocks=updated_portfolio, cash=usd(updatedMoney[0]["cash"]), total = usd(money) )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        symbol = lookup(request.form.get("symbol"))

        if not symbol:
            return apology("Not a valid symbol")

        numberShares = int(request.form.get("shares"))

        if numberShares < 0 or not numberShares:
            return apology("Shares must be positive")

        totalCost = numberShares * symbol['price']

        userMoney = db.execute("SELECT cash FROM users WHERE userId=:user_id;", user_id=session["user_id"])
        userMoney = int(userMoney[0]['cash'])

        if totalCost > userMoney:
            return apology("Low Money")
        else:

            db.execute("INSERT INTO history (symbol, quantity, price, userId, total) VALUES (:symbol, :quantity, :price, :userId, :total);", symbol=symbol['symbol'], quantity=numberShares, price=symbol['price'], userId=session["user_id"], total = numberShares*symbol['price'])

            db.execute("UPDATE users SET cash=cash-:total_price WHERE userId=:user_id;", total_price=totalCost, user_id=session["user_id"])

            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT * from history WHERE userId=:userId", userId=session["user_id"])

    return render_template("history.html")


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
        session["user_id"] = rows[0]["userId"]

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

    if request.method == "POST":

        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Missing Symbol")

        return render_template("quoted.html", q=quote)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("Missing username")

        elif not request.form.get("password"):
            return apology("Missing password")

        elif not request.form.get("confirmation"):
            return apology("Missing confirmation password")

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match")

        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")))

        if not result:
            return apology("UserId alreafy exits")

        session[request.form.get("username")] = result

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        symbol = lookup(request.form.get("symbol"))
        numberShares = int(request.form.get("shares"))

        if not symbol:
            return apology("Enter valid Symbol")

        if not numberShares or numberShares <= 0:
            return apology("Enter a positive number for quantity of shares")

        stocks_held = db.execute("SELECT SUM(quantity) FROM history WHERE userId=:userId AND symbol=:symbol;", userId=session['user_id'], symbol=symbol['symbol'])

        if not stocks_held[0]['SUM(quantity)'] :
            return apology("No stock of this symbol")

        if numberShares > stocks_held[0]['SUM(quantity)']:
            return apology("Not enough stocks to sell")

        db.execute("INSERT INTO history (symbol, quantity, price, userId) VALUES (:symbol, :quantity, :price, :userId);", symbol=symbol['symbol'], quantity=-numberShares, price=symbol['price'], userId=session["user_id"])

        db.execute("UPDATE users SET cash = cash + :total_price WHERE userId = :user_id;", total_price=numberShares*symbol['price'], user_id=session["user_id"])

        return redirect('/')

    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
