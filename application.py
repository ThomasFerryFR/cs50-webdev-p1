import os

from flask import Flask, session, render_template, request, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import json

app = Flask(__name__)

# # Check for environment variable
# if not os.getenv("DATABASE_URL"):
#     raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine("postgres://bwxmflqebqcfgw:2e7c11e773f8777fdbab23f5eb509a9ab175b77c537e2b76b9ce5bf86178769b@ec2-54-247-125-38.eu-west-1.compute.amazonaws.com:5432/df39geldejee7p")
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
	try:
		if session['logged_in']:
			return render_template("index.html", logged_in=session['logged_in'], user_name = session['user_name'])
		else:
			return render_template("index.html", logged_in=session['logged_in'], user_name = "none")
	except:
		session['logged_in'] = False
		return render_template("index.html", logged_in=session['logged_in'], user_name = "none")

@app.route("/register", methods=["GET", "POST"])
def register():

	if request.method == "GET":
		return render_template("register.html", existing=False)

	elif request.method == "POST":
	    # Get Username and password
		username = request.form.get("username")
		password = request.form.get("password")

		# Check if Username is unique
		if db.execute("SELECT * FROM users WHERE username= :username", {"username":username}).rowcount != 0:
			return render_template("register.html", existing=True)

		# Register the new user
		db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username":username, "password":password})
		db.commit()
		return render_template("success.html")

@app.route("/login", methods=["GET", "POST"])
def login():

	if request.method == "GET":
		return render_template("login.html", wrong_uname=False, wrong_pword=False)

	elif request.method == "POST":
		username = request.form.get("username")
		password = request.form.get("password")
		
		# Check if Username exists
		if db.execute("SELECT * FROM users WHERE username= :username", {"username":username}).rowcount != 1:
			return render_template("login.html", wrong_uname=True, wrong_pword=False)
		
		# Check if right password
		if db.execute("SELECT * FROM users WHERE username = :username AND password = :password", {"username":username, "password":password}).rowcount != 1:
			return render_template("login.html", wrong_uname=False, wrong_pword=True)

		# Create session and redirect user
		if db.execute("SELECT * FROM users WHERE username = :username AND password = :password", {"username":username, "password":password}).rowcount == 1:
			session['logged_in'] = True
			session['user_id'] = db.execute("SELECT id FROM users WHERE username = :username AND password = :password", {"username":username, "password":password}).fetchall()[0][0]
			session['user_name'] = db.execute("SELECT username FROM users WHERE id = :user_id", {"user_id": session['user_id']}).fetchall()[0][0] #select username
			return render_template("index.html", logged_in=session['logged_in'], user_name = session['user_name'])

@app.route("/logout", methods=["GET"])
def logout():
	if session['logged_in']:
		session['logged_in'] = False
		session['user_name'] = "none"
		return render_template("index.html", logged_in=session['logged_in'], user_name="none")

@app.route("/search", methods=["POST"])
def search():
	search = request.form.get("search")
	search_type = request.form.get("type").lower()

	if search_type == "year":
		search_type = "pub_year"

	search = "%"+search+"%"

	if search_type == "isbn":
		results = db.execute("SELECT * FROM books WHERE isbn ILIKE :search", {"search":search})
	if search_type == "author":
		results = db.execute("SELECT * FROM books WHERE author ILIKE :search", {"search":search})
	if search_type == "title":
		results = db.execute("SELECT * FROM books WHERE title ILIKE :search", {"search":search})
	if search_type == "pub_year":
		results = db.execute("SELECT * FROM books WHERE pub_year ILIKE :search", {"search":search})
	
	if results.rowcount == 0:
		return render_template("search.html", logged_in = session['logged_in'], results = [], found_none = True, user_name = session['user_name'])
	
	else:
		return render_template("search.html", logged_in=session['logged_in'], results = results.fetchall(), found_none = False, user_name = session['user_name'])


@app.route("/book", methods=["GET", "POST"])
def book():
	
	def widget_cleaner(dirty_code):

		sub_strings = [("\\u003c","<"), ("\\u003e", ">"), ("\\n", ""), ("=\\","="), ('\\"', '"'), ('\\u0026', '&'), ('{"reviews_widget":"',''),('"}',"")]
		
		clean_code = dirty_code

		for sub in sub_strings:
			clean_code = clean_code.replace(sub[0], sub[1])

		return clean_code

	isbn = request.args.get('isbn', None)
	if isbn == None:
		isbn = session["isbn"]
	session["isbn"] = None
	results = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn":isbn})

	reviews = []

	book = []
	for info in results.fetchall()[0]:
		book.append(info)

	book[5] = widget_cleaner(book[5])

	for proxy in db.execute("SELECT * FROM bookli_reviews WHERE isbn = :isbn", {"isbn":book[0]}).fetchall():
		review = [item for item in proxy]
		review[1] = db.execute("SELECT username FROM users WHERE id=:id",{"id": review[1]}).fetchall()[0][0]
		reviews.append(review)

	try:
		bookli_ratings = round(float(db.execute("SELECT AVG(rating) FROM bookli_reviews WHERE isbn=:isbn", {"isbn":book[0]}).fetchall()[0][0]),2)
	except:
		bookli_ratings = 'n.a.'
	bookli_count = db.execute("SELECT COUNT(rating) FROM bookli_reviews WHERE isbn=:isbn", {"isbn":book[0]}).fetchall()[0][0]

	user_reviews = db.execute("SELECT ratings FROM users WHERE username = :username", {"username":session['user_name']}).fetchall()[0][0]

	if user_reviews == None:
		return render_template("book.html", logged_in=session['logged_in'], book = book, reviewed = False, user_name = session['user_name'], reviews = reviews, bookli_rating= bookli_ratings, bookli_count = bookli_count)
	else:
		user_reviews = [int(rev) for rev in user_reviews]
		reviewed_isbns = [isbn[0] for isbn in db.execute("SELECT isbn FROM bookli_reviews WHERE id = ANY(:ids)", {"ids": user_reviews}).fetchall()]
		if book[0] in reviewed_isbns:
			u_review = db.execute("SELECT review FROM bookli_reviews WHERE isbn = :isbn AND id = ANY(:id)", {"isbn":book[0], "id": user_reviews}).fetchall()[0][0]
			u_rating = db.execute("SELECT rating FROM bookli_reviews WHERE isbn = :isbn AND id = ANY(:id)", {"isbn":book[0], "id": user_reviews}).fetchall()[0][0]

			return render_template("book.html", logged_in=session['logged_in'], book = book, reviewed = True, user_name = session['user_name'], user_review = u_review, user_rating = u_rating, reviews = reviews, bookli_rating= bookli_ratings, bookli_count = bookli_count)
		else:
			return render_template("book.html", logged_in=session['logged_in'], book = book, reviewed = False, user_name = session['user_name'], reviews = reviews, bookli_rating= bookli_ratings, bookli_count = bookli_count)


@app.route("/user_page", methods=["GET"])
def user_page():

	user_reviews = db.execute("SELECT ratings FROM users WHERE username = :username", {"username":session['user_name']}).fetchall()[0][0]

	if user_reviews== None:
		return render_template("user_page.html", logged_in = session['logged_in'], reviewed_books = [], written_reviews = False, user_name = session['user_name'])
	else:
		user_reviews = [int(rev) for rev in user_reviews]
		reviewed_isbns = [isbn[0] for isbn in db.execute("SELECT isbn FROM bookli_reviews WHERE id = ANY(:ids)", {"ids": user_reviews}).fetchall()]
		reviewed_books = db.execute("SELECT * FROM books WHERE isbn = ANY(:isbn)", {"isbn":reviewed_isbns}).fetchall()

		return render_template("user_page.html", logged_in=session['logged_in'], reviewed_books = reviewed_books, written_reviews = True, user_name = session['user_name'])

@app.route("/review", methods=["POST"])
def review():

	review = request.form.get("review")
	rating = request.form.get("rating")
	isbn = request.form.get("isbn")

	db.execute("INSERT INTO bookli_reviews (user_id, isbn, rating, review) VALUES (:user, :isbn, :rating, :review)", {"user":session["user_id"], "isbn":isbn, "rating": rating, "review": review})
	db.commit()

	review_id = db.execute("SELECT id FROM bookli_reviews WHERE user_id = :user AND isbn = :isbn", {"user":session["user_id"],"isbn":isbn}).fetchall()[0][0]
	db.execute("UPDATE users SET ratings = ratings || :review_id WHERE id = :user", {"review_id": review_id, "user": session["user_id"]})
	db.commit()

	results = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn":isbn})

	book = []
	for info in results.fetchall()[0]:
		book.append(info)	

	session["isbn"] = book[0]
	return redirect(url_for('book'))

@app.route("/api/<string:isbn>", methods=["GET"])
def api(isbn):

	book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn":isbn}).fetchall()[0]

	if book == None:
		return "Error 404: The isbn requested is not stored in our database"

	try:
		bookli_ratings = round(float(db.execute("SELECT AVG(rating) FROM bookli_reviews WHERE isbn=:isbn", {"isbn":book[0]}).fetchall()[0][0]),2)
	except:
		bookli_ratings = 'n.a.'
	bookli_count = db.execute("SELECT COUNT(rating) FROM bookli_reviews WHERE isbn=:isbn", {"isbn":book[0]}).fetchall()[0][0]

	result = {"title": book[1], "author": book[2], "year": book[3], "review_count": bookli_count, "average_score": bookli_ratings}

	return json.dumps(result)