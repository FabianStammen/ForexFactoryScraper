"""ForexFactoryScraper
A more sophisticated web scraper that downloads forex calendar data from ForexFactory.

The download is managed in packets of days, weeks or month to minimize network traffic.
The chosen timezone is Eastern Standard Time (EST) time-zone WITH Day Light Savings adjustments.
This is easily adjustable trough the usage of timezone aware datetime objects.
The program starts at the first possible download date, jan 1 2007, and ends on the current day,
up to the current time.
Any later executions of the program checks for the datetime of the last entry and updates the list
from that point in time.
If an event has the time signature 'All Day' the time will be saves as the maximum value, 23:59:59,
to ensure completion of the event at the point or scraping.
The output file will be located in the working directory and be called forex_factory_catalog.csv

It is required to have Google Chrome installed.
Headless mode is not possible anymore, since Forex Factory uses Cloudflare DDoS protection.
"""
import csv
import re
from datetime import datetime, timedelta
from os import path

import undetected_chromedriver.v2 as uc
from dateutil.tz import gettz
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait


def setup_driver():
    """Setup the firefox geckodriver to be headless.

    Returns:
        selenium.webdriver.Firefox: The setup geckodriver.
    """
    options = uc.ChromeOptions()
    # options.headless = True
    options.add_argument('--no-first-run --no-service-autorun --password-store=basic')
    return uc.Chrome(options=options)


def get_timezone(driver):
    """Extracts the current default timezone from the website.

    Returns:
        timezone: the timezone
    """
    driver.get('https://www.forexfactory.com/timezone.php')
    select = Select(WebDriverWait(driver, 10).until(
        ec.presence_of_element_located((By.ID, 'timezone'))))
    tz_name = select.first_selected_option.text[1:10]
    return gettz(tz_name)


def scrap(timezone):
    """Scrap the event data from the web.

    Args:
        timezone : The output time zone.
    """
    driver = setup_driver()
    try:
        ff_timezone = get_timezone(driver)
        start_date = get_start_dt(ff_timezone)
        fields = ['date', 'time', 'currency', 'impact', 'event', 'actual', 'forecast', 'previous']
        while True:
            try:
                date_url = dt_to_url(start_date)
            except ValueError:
                print('Successfully retrieved data')
                return
            print('\r' + 'Scraping data for link: ' + date_url, end='', flush=True)

            driver.get('https://www.forexfactory.com/' + date_url)
            soup = BeautifulSoup(driver.page_source, 'lxml')
            table = soup.find('table', class_='calendar__table')
            table_rows = table.select('tr.calendar__row.calendar_row')
            date = None
            for table_row in table_rows:
                try:
                    currency, impact, event, actual, forecast, previous = '', '', '', '', '', ''
                    for field in fields:
                        data = table_row.select('td.calendar__cell.calendar__{0}.{0}'.format(field))[0]
                        if field == 'date' and data.text.strip() != '':
                            day = data.text.strip().replace('\n', '')
                            if date is None:
                                year = str(start_date.year)
                            else:
                                year = str(get_next_dt(date, mode='day').year)
                            date = datetime.strptime(','.join([year, day]), '%Y,%a%b %d') \
                                .replace(tzinfo=ff_timezone)
                        elif field == 'time' and data.text.strip() != '':
                            time = data.text.strip()
                            if 'Day' in time:
                                date = date.replace(hour=23, minute=59, second=59)
                            elif 'Data' in time:
                                date = date.replace(hour=0, minute=0, second=1)
                            else:
                                i = 1 if len(time) == 7 else 0
                                date = date.replace(
                                    hour=int(time[:1 + i]) % 12 + (12 * (time[4 + i:] == 'pm')),
                                    minute=int(time[2 + i:4 + i]), second=0)
                        elif field == 'currency':
                            currency = data.text.strip()
                        elif field == 'impact':
                            impact = data.find('span')['title']
                        elif field == 'event':
                            event = data.text.strip()
                        elif field == 'actual':
                            actual = data.text.strip()
                        elif field == 'forecast':
                            forecast = data.text.strip()
                        elif field == 'previous':
                            previous = data.text.strip()
                    if date.second == 1:
                        raise ValueError
                    if date <= start_date:
                        continue
                    if date >= datetime.now(tz=date.tzinfo):
                        break
                    with open('forex_factory_catalog.csv', mode='a', newline='') as file:
                        writer = csv.writer(file, delimiter=',')
                        writer.writerow(
                            [str(date.astimezone(timezone)), currency, impact, event, actual, forecast, previous]
                        )
                except TypeError:
                    with open('errors.csv', mode='a') as file:
                        file.write(str(date) + ' (No Event Found)\n')
                except ValueError:
                    with open('errors.csv', mode='a') as file:
                        file.write(str(date.replace(second=0)) + ' (Data For Past Month)\n')
            start_date = get_next_dt(start_date, mode=get_mode(date_url))
    finally:
        driver.quit()


def get_start_dt(timezone):
    """Get the start datetime for the scraping. Function incremental.

    Returns:
        datetime: The start datetime.
    """
    if path.isfile('forex_factory_catalog.csv'):
        with open('forex_factory_catalog.csv', 'rb+') as file:
            file.seek(0, 2)
            file_size = remaining_size = file.tell() - 2
            if file_size > 0:
                file.seek(-2, 2)
                while remaining_size > 0:
                    if file.read(1) == b'\n':
                        return datetime.fromisoformat(file.readline()[:25].decode())
                    file.seek(-2, 1)
                    remaining_size -= 1
                file.seek(0)
                file.truncate(0)
    return datetime(year=2007, month=1, day=1, hour=0, minute=0, tzinfo=timezone)


def get_next_dt(date, mode):
    """Calculate the next datetime to scrape from. Based on efficiency either a day, week start or
    month start.

    Args:
        date (datetime): The current datetime.
        mode (str): The operating mode; can be 'day', 'week' or 'month'.

    Returns:
        datetime: The new datetime.
    """
    if mode == 'month':
        (year, month) = divmod(date.month, 12)
        return date.replace(year=date.year + year, month=month + 1, day=1, hour=0, minute=0)
    if mode == 'week':
        return date.replace(hour=0, minute=0) + timedelta(days=7)
    if mode == 'day':
        return date.replace(hour=0, minute=0) + timedelta(days=1)
    raise ValueError('{} is not a proper mode; please use month, week, or day.'.format(mode))


def dt_to_url(date):
    """Creates an url from a datetime

    Args:
        date (datetime): The datetime.

    Returns:
        str: The url.
    """
    if dt_is_start_of_month(date) and dt_is_complete(date, mode='month'):
        return 'calendar.php?month={}'.format(dt_to_str(date, mode='month'))
    if dt_is_start_of_week(date) and dt_is_complete(date, mode='week'):
        for weekday in [date + timedelta(days=x) for x in range(7)]:
            if dt_is_start_of_month(weekday) and dt_is_complete(date, mode='month'):
                return 'calendar.php?day={}'.format(dt_to_str(date, mode='day'))
        return 'calendar.php?week={}'.format(dt_to_str(date, mode='week'))
    if dt_is_complete(date, mode='day') or dt_is_today(date):
        return 'calendar.php?day={}'.format(dt_to_str(date, mode='day'))
    raise ValueError('{} is not completed yet.'.format(dt_to_str(date, mode='day')))


def dt_to_str(date, mode):
    if mode == 'month':
        return date.strftime('%b.%Y').lower()
    if mode in ('week', 'day'):
        return '{d:%b}{d.day}.{d:%Y}'.format(d=date).lower()
    raise ValueError('{} is not a proper mode; please use month, week, or day.'.format(mode))


def get_mode(url):
    reg = re.compile('(?<=\\?).*(?=\\=)')
    return reg.search(url).group()


def dt_is_complete(date, mode):
    return get_next_dt(date, mode) <= datetime.now(tz=date.tzinfo)


def dt_is_start_of_week(date):
    return date.isoweekday() % 7 == 0


def dt_is_start_of_month(date):
    return date.day == 1


def dt_is_today(date):
    today = datetime.now()
    return today.year == date.year and today.month == date.month and today.day == date.day


if __name__ == '__main__':
    """Main function

    Initializes the module.
    """
    scrap(gettz('UTC-5'))  # HistData saves its Forex data with UTC-5
