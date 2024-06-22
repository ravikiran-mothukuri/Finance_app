import os

from cs50 import SQL # type: ignore
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    cash = db.execute("SELECT cash from users where id= ? ", user_id)[0]["cash"]

    holdings = db.execute(
        "SELECT symbol, SUM(shares) as shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id)

    total_cash = 0
    # for each_share in holdings:

    portfolio = []
    total_value = 0

    for holding in holdings:
        symbol = holding["symbol"]
        print(symbol)
        shares = holding["shares"]  # 10
        stock = lookup(symbol)

        price = stock["price"]  # 120
        total = shares * price  # 10*120
        total_value += total  # 1200+
        portfolio.append({"symbol": symbol, "shares": shares,
                         "price": usd(price), "total": usd(total)})

    Total = cash + total_value

    return render_template("index.html", portfolio=portfolio, cash=usd(cash), total=usd(Total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("Missing Symbol")
        ans = lookup(symbol)
        if not ans:
            return apology("Invalid Symbol")
        if not shares:
            return apology("Missing Shares")
        if not shares.isdigit():
            return apology("Shares are Integer number")
        shares = int(shares)
        if shares <= 0:
            return apology("Shares number should be positive")

        symbol = ans["symbol"]
        cost = ans["price"]
        print("Cost: ", cost)
        total_cost = float(cost*shares)
        user_id = session["user_id"]
        rows = db.execute("SELECT cash from users where id= ?", user_id)
        present_money = float(rows[0]["cash"])
        if (present_money < total_cost):
            return apology("Insufficient Money")

        update_money = present_money-total_cost
        db.execute("UPDATE users set cash= ? where id= ?", update_money, user_id)
        db.execute("INSERT into transactions (user_id,symbol,shares,price) values (?,?,?,?) ",
                   user_id, symbol, shares, cost)
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    rows = db.execute(
        "SELECT symbol,shares,price,transacted from transactions where user_id= ?", user_id)

    return render_template("history.html", rows=rows)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        if not symbol:
            return apology("Enter Symbol please!!!")
        if symbol <= 'A' or symbol >= 'Z':
            return apology("Invalid Symbol")
        answer = lookup(symbol)
        price = answer["price"]
        symbol = answer["symbol"]
        price = usd(price)
        return render_template("quoted.html", cost=price, symbol=symbol)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        name = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not name:
            return apology("UserName is Blank", 400)
        if not password:
            return apology("Password is Blank", 400)
        if password != confirmation:
            return apology("Password didn't match", 400)
        hash_password = generate_password_hash(password)
        try:
            id = db.execute("INSERT INTO users (username,hash) values (?,?)", name, hash_password)
        except ValueError:
            return apology("User Already Exists!!!", 400)
        session["user_id"] = id

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    id = db.execute("select id from users where id= ?", user_id)[0]["id"]

    symbols = db.execute("select symbol from transactions where user_id= ? group by symbol", id)

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing Symbol")
        Sold_shares = int(request.form.get("shares"))
        if not Sold_shares:
            return apology("Missing Shares")
        ans = db.execute(
            "select sum(shares) as shares from transactions where user_id=? and symbol= ?", id, symbol)
        shares = ans[0]["shares"]

        if (Sold_shares > shares):
            return apology("Insufficient Shares")

        transaction = db.execute(
            "select id,shares from transactions where user_id=? and symbol=?", id, symbol)
        for i in transaction:
            no = i["id"]
            original = i["shares"]
            if Sold_shares <= 0:
                break
            if original > Sold_shares:
                db.execute(
                    "update transactions set shares= shares - ? where user_id=? and id=?", Sold_shares, user_id, no)
                new = Sold_shares
                Sold_shares = 0
            else:
                Sold_shares -= original
                db.execute("delete from transactions where id= ?", no)

        stock = lookup(symbol)
        price = stock["price"]
        sales = new*price
        db.execute("UPDATE users set cash= cash+ ? where id=?", sales, user_id)
        db.execute("Insert into transactions (user_id,symbol,shares,price) values (?,?,?,?)",
                   user_id, symbol, -new, price)
        # db.execute("delete from transactions where shares=0")
        return redirect("/")

    return render_template("sell.html", symbols=symbols)
