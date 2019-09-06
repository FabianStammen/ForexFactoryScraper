import csv
import logging
from datetime import date, datetime, timedelta
from os import path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options


def set_logger():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        filename='logs_file',
                        filemode='w')
    console = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


def setup_driver_with_timezone():
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options)
    driver.get('https://www.forexfactory.com/timezone.php')
    driver.find_element_by_xpath('//select[@name="timezoneoffset"]/option[@value="-5"]').click()
    driver.find_element_by_xpath('//select[@name="dst"]/option[@value="0"]').click()
    driver.find_element_by_xpath('//select[@name="options[timeformat]"]/option[@value="1"]').click()
    driver.find_element_by_xpath('//input[@value="Save Settings"]').click()
    return driver


def scrap(start_link, end_link, driver):
    logging.info('Scraping data for link: {}'.format(start_link))
    base_url = 'https://www.forexfactory.com/'

    driver.get(base_url + start_link)
    driver.find_elements_by_class_name('calendar__table')

    trs = driver.find_elements_by_css_selector('tr.calendar__row.calendar_row')
    # trs = table.select('tr.calendar__row.calendar_row')
    fields = ['date', 'time', 'currency', 'impact', 'event', 'actual', 'forecast', 'previous']

    # some rows do not have a date (cells merged)
    curr_year = start_link[-4:]
    curr_date = ''
    curr_time = ''
    for tr in trs:
        # fields may mess up sometimes, see Tue Sep 25 2:45AM French Consumer Spending
        # in that case we append to errors.csv the date time where the error is
        try:
            for field in fields:
                data = tr.find_elements_by_css_selector('td.calendar__cell.calendar__{}.{}'.format(field, field))[0]
                if field == 'date' and data.text.strip() != '':
                    curr_date = data.text.strip().replace('\n', '')
                elif field == 'time' and data.text.strip() != '':
                    if data.text.strip().find('Day') != -1:
                        curr_time = '00:00'
                    else:
                        curr_time = data.text.strip()
                elif field == 'currency':
                    currency = data.text.strip()
                elif field == 'impact':
                    impact = data.find_element_by_css_selector('span')
                    impact = impact.get_attribute('title')
                elif field == 'event':
                    event = data.text.strip()
                elif field == 'actual':
                    actual = data.text.strip()
                elif field == 'forecast':
                    forecast = data.text.strip()
                elif field == 'previous':
                    previous = data.text.strip()

            dt = datetime.strptime(','.join([curr_year, curr_date, curr_time]),
                                   '%Y,%a%b %d,%H:%M')
            with open('forex_factory_catalog.csv', 'a') as file:
                file.write(','.join([str(dt), currency, impact, event, actual, forecast, previous])
                           + '\n')
        except:
            with open('errors.csv', 'a') as f:
                csv.writer(f).writerow([curr_year, curr_date, curr_time])

    if start_link == end_link:
        logging.info('Successfully retrieved data')
        return

    follow = driver.find_element_by_css_selector(
        'a.calendar__pagination.calendar__pagination--next.next').get_attribute('href')
    follow = follow[follow.rindex('/')+1:]
    scrap(follow, end_link, driver)


def date_to_str(day):
    return day.strftime('%b%d.%Y').lower()


def get_end_date_str():
    end_date = date.today() - timedelta(days=((date.today().isoweekday()) % 7) + 7)
    return date_to_str(end_date)


def get_start_date_str():
    if path.exists('forex_factory_catalog.csv'):
        with open('forex_factory_catalog.csv', 'rb') as file:
            file.seek(-2, 2)
            while file.read(1) != b'\n':
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


if __name__ == '__main__':
    set_logger()
    scrap('calendar.php?week=' + get_start_date_str(),
          'calendar.php?week=' + get_end_date_str(),
          setup_driver_with_timezone())
