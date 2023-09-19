from flask import Flask, request, send_from_directory, Response
from werkzeug.exceptions import abort
from werkzeug.middleware.proxy_fix import ProxyFix
from typing import List

__author__ = "Michael Pogrebinsky - www.topdeveloperacademy.com"


from data.book import Book
from data.database import Database
from data.request_validator import RequestValidator, CreditCardValidationException, InvalidBillingInfo

app = Flask(__name__, static_url_path='')

# The lab is behind a http proxy, so it's not aware of the fact that it should use https.
# We use ProxyFix to enable it: https://flask.palletsprojects.com/en/2.0.x/deploying/wsgi-standalone/#proxy-setups
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Used for any other security related needs by extensions or application, i.e. csrf token
app.config['SECRET_KEY'] = 'mysecretkey'

# Required for cookies set by Flask to work in the preview window that's integrated in the lab IDE
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True

# Required to render urls with https when not in a request context. Urls within Udemy labs must use https
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Creating application databases and business logic
BOOKS_DIRECTORY = "resources/books"
checkout_request_validator = RequestValidator()
database = Database()

@app.route("/")
def index():
    return app.send_static_file("index.html")
    
@app.route("/categories/", methods=["GET"])
def categories():
    return database.get_all_supported_categories()
    
@app.route("/books/", methods=["GET"])
def get_books():
    category = request.args.get('category')
    if category is not None:
        books = aggregate_books(database.get_books_by_category(category))
    else:
        books = aggregate_books(database.get_all_books())
    return books
    
@app.route("/trending/<int:max_no_of_books>", methods=["GET"])
def trending_books(max_no_of_books: int):
    books = aggregate_books(database.get_trending_books(max_no_of_books))
    return books
    
@app.route("/checkout/", methods=["POST"])
def checkout():
    payload = request.get_json()
    checkout_request_validator.validate_billing_info(
        payload['first_name'], payload['last_name'], payload['billing_address']
    )
    checkout_request_validator.validate_credit_card(payload['credit_card'])
    database.purchase_books(first_name=payload['first_name'],
                            last_name=payload['last_name'],
                            billing_address=payload['billing_address'],
                            email=payload['email'],
                            credit_card=payload['credit_card'],
                            book_ids=payload["book_ids"])
    cookie_value = ",".join([str(book_id) for book_id in payload["book_ids"]])
    response.set_cookie('purchased_books',cookie_value, max_age=30)
    return "success"
    
@app.errorhandler(InvalidBillingInfo)
def handle_invalid_billing_info_exception(e):
    return Response(str(e), status=400, mimetype="text/plain")
    
@app.errorhandler(CreditCardValidationException)
def handle_credit_card_validation_exception(e):
    app.logger.warning(e)
    return Response(str(e), status=402, mimetype="text/plain")
    
@app.route("/book_download/", methods=["GET"])
def book_download():
    book_id = request.args.get('book_id')
    purchase_book_ids = request.cookies.get('purchased_books')
    if not purchase_book_ids or not purchase_book_ids.strip():
        abort(401)
    if not str(book_id) in set(purchase_book_ids.strip(",")):
        abort(401)
    filename = database.get_book_file_name(book_id)
    return send_from_directory(directory=BOOKS_DIRECTORY, path=filename, as_attachment=True)


def aggregate_books(books: List[Book]) -> dict:
    """
    Creates a dictionary object that maps from 'books' to a list of book objects
    Example:
        {"books: [{"id": 123,
                    "name": "Course Name",
                    "description": "Course Description",
                    "image_file_name": "image.png",
                    "price_usd": 19.9,
                    "topic": "education",
                    "average_rating" : 4.5}]
        }
    """

    return {"books": [book.__dict__ for book in books]}
