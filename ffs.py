import csv
import logging
from datetime import date, datetime, timedelta
from os import path

import requests
from bs4 import BeautifulSoup


def set_logger():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        filename='logs_file',
                        filemode='w')
    console = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


def get_economic_calendar(start_link, end_link):
    # write to console current status
    logging.info("Scraping data for link: {}".format(start_link))

    # get the page and make the soup
    base_url = "https://www.forexfactory.com/"
    r = requests.get(base_url + start_link)
    data = r.text
    soup = BeautifulSoup(data, "lxml")

    # get and parse table data, ignoring details and graph
    table = soup.find("table", class_="calendar__table")

    # do not use the ".calendar__row--grey" css selector (reserved for historical data)
    trs = table.select("tr.calendar__row.calendar_row")
    fields = ["date", "time", "currency", "impact", "event", "actual", "forecast", "previous"]

    # some rows do not have a date (cells merged)
    curr_year = start_link[-4:]
    curr_date = ""
    curr_time = ""
    for tr in trs:

        # fields may mess up sometimes, see Tue Sep 25 2:45AM French Consumer Spending
        # in that case we append to errors.csv the date time where the error is
        try:
            for field in fields:
                data = tr.select("td.calendar__cell.calendar__{}.{}".format(field, field))[0]
                # print(data)
                if field == "date" and data.text.strip() != "":
                    curr_date = data.text.strip()
                elif field == "time" and data.text.strip() != "":
                    # time is sometimes "All Day" or "Day X" (eg. WEF Annual Meetings)
                    if data.text.strip().find("Day") != -1:
                        curr_time = "12:00am"
                    else:
                        curr_time = data.text.strip()
                elif field == "currency":
                    currency = data.text.strip()
                elif field == "impact":
                    # when impact says "Non-Economic" on mouseover, the relevant
                    # class name is "Holiday", thus we do not use the classname
                    impact = data.find("span")["title"]
                elif field == "event":
                    event = data.text.strip()
                elif field == "actual":
                    actual = data.text.strip()
                elif field == "forecast":
                    forecast = data.text.strip()
                elif field == "previous":
                    previous = data.text.strip()

            dt = datetime.strptime(",".join([curr_year, curr_date, curr_time]),
                                   "%Y,%a%b %d,%I:%M%p")
            with open('forex_factory_catalog.csv', 'a') as file:
                file.write(",".join([str(dt), currency, impact, event, actual, forecast, previous])
                           + '\n')
        except:
            with open("errors.csv", "a") as f:
                csv.writer(f).writerow([curr_year, curr_date, curr_time])

    # exit recursion when last available link has reached
    if start_link == end_link:
        logging.info("Successfully retrieved data")
        return

    # get the link for the next week and follow
    follow = soup.select("a.calendar__pagination.calendar__pagination--next.next")
    follow = follow[0]["href"]
    get_economic_calendar(follow, end_link)


def date_to_str(day):
    return day.strftime('%b%d.%Y').lower()


def get_end_date_str():
    end_date = date.today() - timedelta(days=((date.today().isoweekday()) % 7) + 7)
    return date_to_str(end_date)


def get_start_date_str():
    if path.exists('forex_factory_catalog.csv'):
        with open('forex_factory_catalog.csv', 'rb') as file:
            file.seek(-2, 2)
            while file.read(1) != b"\n":
                file.seek(-2, 1)
            last_day = file.readline()[:10].decode()
            start_day = date(int(last_day[:4]), int(last_day[5:7]), int(last_day[8:10])) \
                        + timedelta(days=(7 - (date.today().isoweekday()) % 7))
    else:
        start_day = date(2007, 1, 7)
    next_week = start_day + timedelta(days=7)
    if next_week > date(2019, 9, 9):
        raise ValueError('The week of the next start date, '
                         + date_to_str(start_day)
                         + ', if not completed yet. Please wait until'
                         + date_to_str(next_week) + '.')
    return date_to_str(start_day)


if __name__ == "__main__":
    set_logger()
    get_economic_calendar('calendar.php?week=' + get_start_date_str(),
                          'calendar.php?week=' + get_end_date_str())
