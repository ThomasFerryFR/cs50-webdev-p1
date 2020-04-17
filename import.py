from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import requests
import pandas as pd

engine = create_engine("postgres://bwxmflqebqcfgw:2e7c11e773f8777fdbab23f5eb509a9ab175b77c537e2b76b9ce5bf86178769b@ec2-54-247-125-38.eu-west-1.compute.amazonaws.com:5432/df39geldejee7p")
db = scoped_session(sessionmaker(bind=engine))

# Get the Goodread API Key stored in the respective csv file
api_key = pd.read_csv("API-key.csv")['key'][0]

def json_cleaner(text, start, end):

	return text[text.find(start)+len(start):].replace(end,'')


# Print iterations progress
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

def main():

	books_df = pd.read_csv("books.csv")

	i=0
	if db.execute("SELECT * FROM books").fetchall() == []:
		for index, book in books_df.iterrows():
			
			# Get the goodread id and reviews from the API
			g_id = requests.get("https://www.goodreads.com/book/isbn_to_id", params={"key": api_key, "isbn": book['isbn']}).text
			reviews = requests.get("https://www.goodreads.com/book/show.json", params={"key": api_key, "id": g_id, "text_only":"true"}).text

			db.execute("INSERT INTO books (isbn, title, author, pub_year, goodreads_id, goodreads_reviews) VALUES (:isbn, :title, :author, :year, :goodreads_id, :goodreads_reviews)", {"isbn":book['isbn'], "title":book['title'], "author":book['author'], "year":book['year'], "goodreads_id":g_id, "goodreads_reviews":reviews})

			i+=1
			print("{}/{}".format(i, len(books_df.index)))
		db.commit()
		print(db.execute("SELECT * FROM books WHERE pub_year = 2000").fetchall())

	else:
		db_isbns = db.execute("SELECT isbn FROM books").fetchall()
		gr_reviews = []

		i=0

		for isbn in db_isbns:

			review = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": api_key, "isbns": isbn[0]}).text

			average = json_cleaner(review,'average_rating":"','"}]}')
			count = json_cleaner(review[review.find('ratings_count'):review.find(',"reviews_count"')],'ratings_count":',',')


			db.execute("UPDATE books SET goodreads_rating_average = :average, goodreads_rating_count = :count WHERE isbn = :isbn", {"average":average, "count":count, "isbn":isbn[0]})
			db.commit()

			i+=1
			printProgressBar(i, 5000, prefix = 'Progress:', suffix = 'Complete', length = 50)


if __name__ == "__main__":
	main()