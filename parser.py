from datetime import datetime
import psycopg2
import requests
from bs4 import BeautifulSoup
import time
import telegram
from telegram.ext import Updater
import json
import os
from dotenv import load_dotenv
import cowsay

load_dotenv()

print(cowsay.get_output_string('trex', 'Мощный парсер'))
print(cowsay.get_output_string('stegosaurus', 'Истину глаголите'))


# Connect to Postgres database
conn = psycopg2.connect(database=os.getenv('DB_NAME'),
                        user=os.getenv('DB_USER'),
                        password=os.getenv('DB_PASSWORD'),
                        host=os.getenv('DB_HOST'),
                        port=os.getenv('DB_PORT'))
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id SERIAL PRIMARY KEY,
        title TEXT,
        link TEXT,
        price TEXT,
        date_posted TEXT,
        seller TEXT,
        description TEXT
    );
""")
conn.commit()


# Telegram bot setup
updater = Updater(token=os.getenv('TELEGRAM_BOT_TOKEN'), use_context=True)
dispatcher = updater.dispatcher
bot = telegram.Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
chat_id = os.getenv('TELEGRAM_USER_ID')

# Keywords to search
keywords = json.loads(os.getenv('KEYWORDS'))


def scrape_listing(listing_url):
    response = requests.get(listing_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract the title of the listing
    title = soup.find('h1', {'data-cy': 'ad_title'})
    if title != None:
        title = title.text.strip()

    date_posted = soup.find('span', {'data-cy': 'ad-posted-at'})
    if date_posted != None:
        date_posted = date_posted.text.strip()

    price = soup.find('div', {'data-testid': 'ad-price-container'})
    if price != None:
        price = price.text.strip()

    description = soup.find('div', {'data-cy': 'ad_description'})
    if description != None:
        description = description.text.strip()
        description = description[0:8] + '\n' + description[8::]

    seller = soup.find('a', {'data-testid': 'user-profile-link'})
    if seller != None:
        seller_link = 'https://olx.uz' + seller['href']
        seller = seller_link + ' ' + seller.text.strip()

    # Extract the link to the listing
    link = listing_url

    # Check if any of the keywords are in the title or description
    if any(title != None and keyword in title.lower() or description != None and keyword in description.lower() for keyword in keywords):
        # Check if the listing is already in the database
        cur.execute("SELECT * FROM listings WHERE title=%s", (title,))
        result = cur.fetchone()

        if result is None:
            # Add the listing to the database
            cur.execute("INSERT INTO listings (title, link, price, date_posted, seller, description) VALUES (%s, %s, %s, %s, %s, %s)", (title, link, price, date_posted, seller, description))
            conn.commit()

            # Send a message to the Telegram user
            message = f"Заголовок: {title}\nСсылка: {link}\nЦена: {price}\nВремя Опубликованования: {date_posted}\nПродавец: {seller}\nОписание: {description}"
            if len(message) > 4096:
                for x in range(0, len(message), 4096):
                    bot.send_message(message.chat.id, message[x:x+4096])
            else:
                bot.send_message(chat_id=chat_id, text=message)


def scrape_olx():
    page_number = 1
    while True:
        if page_number > int(os.getenv('PAGE_LIMIT')):
            break
        # URL of the page to scrape
        # url = f'https://www.olx.uz/d/list/?page=2'
        url = f'https://www.olx.uz/list/?page={page_number}&q=&search[order]=created_at:desc'
        # url = f'https://www.olx.uz/d/list/?page=1&q=&search[order]=price:asc'

        # Send a GET request to the URL and get the page content
        response = requests.get(url)

        # Parse the page content with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all the listings on the page
        listings = soup.find_all('div', class_='offer-wrapper')
        
        # Scrape each listing on the page
        for listing in listings:
            listing_url = None
            listing_href = listing.find('a', class_='marginright5 link linkWithHash detailsLink', href=True)
            if listing_href != None:
                listing_url = listing_href['href']
                scrape_listing(listing_url)

        # Wait for 3 seconds before scraping the next page
        time.sleep(3)
        page_number += 1
        continue
        



def main():
    while True:
        conn = psycopg2.connect(database=os.getenv('DB_NAME'),
                                user=os.getenv('DB_USER'),
                                password=os.getenv('DB_PASSWORD'),
                                host=os.getenv('DB_HOST'),
                                port=os.getenv('DB_PORT'))
        cur = conn.cursor()
        # Scrape OLX and send messages every timeout
        scrape_olx()
        time.sleep(int(os.getenv('INTERVAL_FOR_NEW_SCRAP')))
        # Close the database connection
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()