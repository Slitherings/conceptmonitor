import requests
import os
import json
from bs4 import BeautifulSoup as soup
from log import log as log
import time
from datetime import datetime
import random
import sqlite3
from discord_hooks import Webhook
import discord
import slackweb
from threading import Thread
import urllib.request

user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3107.4 Safari/537.36'
headers = {}
headers['User-Agent'] = user_agent
headers['Content-Type'] = 'application/json'

class Product():
    def __init__(self, title, link, stock, keyword, image_url, stock_options):

        self.title = title
        self.stock = stock
        self.link = link
        self.keyword = keyword
        self.image_url = image_url
        self.stock_options = stock_options


def read_from_txt(path):

    # Initialize variables
    raw_lines = []
    lines = []

    # Load data from the txt file
    try:
        f = open(path, "r")
        raw_lines = f.readlines()
        f.close()

    # Raise an error if the file couldn't be found
    except:
        log('e', "Couldn't locate: " + path)

    if(len(raw_lines) == 0):
        log('w', "No data found in: " + path)

    # Parse the data
    for line in raw_lines:
        lines.append(line.strip("\n"))

    # Return the data
    return lines


def add_to_db(product):

    # Initialize variables
    title = product.title
    stock = str(product.stock)
    link = product.link
    keyword = product.keyword
    alert = False

    # log('i', stock)

    # Create database
    conn = sqlite3.connect('products.db')
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS products(title TEXT, link TEXT UNIQUE, stock TEXT, keywords TEXT)""")

    # Add product to database if it's unique
    try:
        c.execute("""INSERT INTO products (title, link, stock, keywords) VALUES (?, ?, ?, ?)""", (title, link, stock, keyword))
        log('s', "Found new product with keyword " + keyword + ". Link = " + link)        
        alert = True
    except:
        # Product already exists, let's check for stock updates
        try:
            # this is messy as fuck and I'm sorry.. :(
            d = (link,)
            c.execute('SELECT (stock) FROM products WHERE link=?', d)
            old_stock = c.fetchone()
            stock_str = str(old_stock)[2:-3]
            if str(stock_str).strip() == str(product.stock).strip():
                log('w', "Product at URL: " + link + " already exists in the database.")
                pass
            else:
                # update table for that product with new stock
                log('s', "Product at URL: " + link + " changed stock.")
                c.execute("""UPDATE products SET stock = ? WHERE link= ?""", (stock_str, link))
                alert = True
        except sqlite3.Error as e:
            log('e', "database error: " + str(e))

    # Close connection to the database
    conn.commit()
    c.close()
    conn.close()

    # Return whether or not it's a new product
    return alert

def notify(product, discord):

    times = []
    today = datetime.now()
    times.append(today)
    sizes = ""

    for size in product.stock_options:
        sizes+= (size + " ")

    if discord:
        embed = Webhook(discord, color=0xEAF4EC)
        embed.set_title(title=product.title, url=product.link)
        embed.set_thumbnail(url=product.image_url)
        embed.add_field(name="Sizes", value=sizes)
        embed.set_footer(text='BBGR', icon='https://imgur.com/8PRphpS', ts=True)
        embed.post()

def monitor(link, keywords, discord):

    log('i', "Checking site: " + link + "...")
    isEarlyLink = False
    links = []
    pages = []
    # Parse the site from the link
    pos_https = link.find("https://")
    pos_http = link.find("http://")
    pos_omia = link.find('omia')

    if(pos_https == 0):
        site = link[8:]
        end = site.find("/")
        if(end != -1):
            site = site[:end]
        site = "https://" + site
    else:
        site = link[7:]
        end = site.find("/")
        if(end != -1):
            site = site[:end]
        site = "http://" + site

    if pos_omia > 0:
        isEarlyLink = True

    # build search links
    if (link.endswith('=')):
        for word in keywords:
            links.append(link + word)
    else:
        links.append(link)

    for l in links:
        # go ahead and make the request
        if isEarlyLink:
            # parse the page to collect data
            stock_data = []

            try:
                r = requests.get(l+"?admin=True", timeout=5, verify=False)
            except:
                log('e', 'Connection to URL: ' + l + " failed. Retrying...")
                time.sleep(5)
                try:
                    r.requests.get(l+"?admin=True", timeout=8, verify=False)
                except:      
                    log('e', 'Connection to URL: ' + l + " failed.")
                    return
            if r.status_code == 404:
                log('e', "Unable to parse that link..")

            page = soup(r.text, "html.parser")

            product = page.findAll('div', class_= 'bc-sf-filter-product-item')
            title = page.findAll('div', class_= 'bc-sf-filter-product-bottom')
            image = page.findAll('img', class_='bc-sf-filter-product-item-image-link img.bc-sf-filter-product-item-main-image')

            # paddings
            if not image:
                image = "N/A"

            if not title:
                title: "N/A"

            # get the data
            url = (l+".json"+"?admin=True")
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req).read()

            size_opts = json.loads(resp.decode('utf-8'))['available_sizes']
            # parse through the list
            
            if not size_opts:
                stock_data.append('Unavailable')
            else:
                for size in size_opts:
                    stock_data.append(size['name'])
            product = Product(title, l, stock_data, "N/A", str(image), stock_data)
            alert = add_to_db(product)

            if alert:
                notify(product, discord)
        # let's do some magic to see if it's a valid link
        else: 
            try:
                r = requests.get(l, timeout=5, verify=False)
                pages.append(r)
            except:
                log('e', 'Connection to URL: ' + l + " failed. Retrying...")
                time.sleep(5)
                try:
                    r.requests.get(l, timeout=8, verify=False)
                    pages.append(r)
                except:      
                    log('e', 'Connection to URL: ' + l + " failed.")
                    return

    for p in pages:
        page = soup(p.text, "html.parser")
        hrefs = []
        raw_links = page.findAll('div', class_= 'bc-sf-filter-product-item')
        captions = page.findAll('div', class_= 'bc-sf-filter-product-bottom')
        images = page.findAll('img', class_='bc-sf-filter-product-item-image-link img.bc-sf-filter-product-item-main-image')

        for raw_link in raw_links:
            link = raw_link.find('a', attrs={"itemprop": "url"})
            try:
                hrefs.append(link["href"])
            except:
                pass

        index = 0
        for href in hrefs:
            found = False
            if len(keywords) > 0:
                for keyword in keywords:
                    if keyword.upper() in captions[index].text.upper():
                        found = True
                        stock_data = []
                        
                        url = (site+hrefs[index]+'.json')

                        req = urllib.request.Request(url, headers=headers)
                        resp = urllib.request.urlopen(req).read()

                        size_opts = json.loads(resp.decode('utf-8'))['available_sizes']
                        # parse through the list
                        if not size_opts:
                            stock_data.append('Unavailable')
                        else:
                            for size in size_opts:
                                stock_data.append(size['name'])

                        product = Product(captions[index].text, (site + hrefs[index]), stock_data, keyword, str(images[index]['src']), stock_data)
                        alert = add_to_db(product)

                        if alert:
                            notify(product, discord)
            index = index + 1


def __main__():
    # Ignore insecure messages (for now)
    import urllib3
    urllib3.disable_warnings()

    with open('config.sample.json') as config:
        j = json.load(config)

    ######### CHANGE THESE #########
    #  KEYWORDS: (seperated by -)  #
    keywords = [                   #
       "700",
       "350",
       "Jordan",
       "Yeezy",
       "Zoom-Fly",
       "Nike", 
       "Travis"                  
    ]                             
    discord = j['discord']

    # Load sites from file
    sites = read_from_txt("cnceptlinks.txt")

    # Start monitoring sites
    while(True):
        threads = []
        for site in sites:
            # skip over blank lines and shit
            if not site.strip():
                pass
            else :
                t = Thread(target=monitor, args=(site, keywords, discord))
                threads.append(t)
                t.start()
                time.sleep(2)



            