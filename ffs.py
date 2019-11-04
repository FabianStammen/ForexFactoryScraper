import csv
import logging
import re
from datetime import datetime, timedelta
from os import path

import requests
from bs4 import BeautifulSoup
from dateutil.tz import gettz


def set_logger():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        filename='logs_file',
                        filemode='w')
    console = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


def get_timezone():
    site = requests.get('https://www.forexfactory.com/timezone.php')
    data = site.text
    soup = BeautifulSoup(data, "lxml")
    tz_infos = soup.find_all('option', selected="selected")
    if tz_infos[0]['value'] == "-5":
        return gettz("America/New_York")
    raise ValueError("The default timezone configuration of forex factory has changed, "
                     "please update.")


def scrap():
    # TODO Refactor to be not monolithic
    timezone = get_timezone()
    start_date = get_start_dt()
    base_url = 'https://www.forexfactory.com/'
    fields = ['date', 'time', 'currency', 'impact', 'event', 'actual', 'forecast', 'previous']
    while True:
        try:
            date_url = dt_to_url(start_date)
        except ValueError:
            logging.info('Successfully retrieved data')
            return
        logging.info('Scraping data for link: %s', date_url)
        site = requests.get(base_url + date_url)
        data = site.text
        soup = BeautifulSoup(data, "lxml")
        table = soup.find("table", class_="calendar__table")
        table_rows = table.select("tr.calendar__row.calendar_row")
        date = None
        for table_row in table_rows:
            try:
                for field in fields:
                    data = table_row.select("td.calendar__cell.calendar__{0}.{0}".format(field))[0]
                    if field == 'date' and data.text.strip() != '':
                        day = data.text.strip().replace('\n', '')
                        if date is None:
                            year = str(start_date.year)
                        else:
                            year = str(get_next_dt(date, mode='day').year)
                        date = datetime.strptime(','.join([year, day]), '%Y,%a%b %d') \
                            .replace(tzinfo=timezone)
                    elif field == 'time' and data.text.strip() != '':
                        time = data.text.strip()
                        if 'Day' in time:
                            hours = 23
                            minutes = 59
                            seconds = 59
                        elif 'Data' in time:
                            hours = 0
                            minutes = 0
                            seconds = 1
                        else:
                            i = 1 if len(time) == 7 else 0
                            hours = int(time[:1 + i]) % 12 + (12 * (time[4 + i:] == 'pm'))
                            minutes = int(time[2 + i:4 + i])
                            seconds = 0
                        date = date.replace(hour=hours, minute=minutes, second=seconds)
                    elif field == 'currency':
                        currency = data.text.strip()
                    elif field == 'impact':
                        impact = data.find("span")["title"]
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
                        [str(date), currency, impact, event, actual, forecast, previous]
                    )
            except TypeError:
                with open('errors.csv', mode='a') as file:
                    file.write(str(date) + ' (No Event Found)\n')
            except ValueError:
                with open('errors.csv', mode='a') as file:
                    file.write(str(date.replace(second=0)) + ' (Data For Past Month)\n')
        start_date = get_next_dt(start_date, mode=get_mode(date_url))


def get_start_dt():
    if path.isfile('forex_factory_catalog.csv'):
        with open('forex_factory_catalog.csv', 'rb+') as file:
            file.seek(0, 2)
            file_size = remaining_size = file.tell() - 2
            if file_size > 0:
                file.seek(-2, 2)
                while remaining_size > 0:
                    if file.read(1) == b'\n':
                        last_day_str = file.readline()[:25].decode()
                        last_day = datetime(year=int(last_day_str[:4]),
                                            month=int(last_day_str[5:7]),
                                            day=int(last_day_str[8:10]),
                                            hour=int(last_day_str[11:13]),
                                            minute=int(last_day_str[14:16]),
                                            tzinfo=gettz('UTC' + last_day_str[19:]))
                        return last_day
                    file.seek(-2, 1)
                    remaining_size -= 1
                file.seek(0)
                file.truncate(0)
    return datetime(year=2007, month=1, day=1, hour=0, minute=0, tzinfo=get_timezone())


def get_next_dt(date, mode):
    if mode == 'month':
        (year, month) = divmod(date.month, 12)
        return date.replace(year=date.year + year, month=month + 1, day=1, hour=0, minute=0)
    if mode == 'week':
        return date.replace(hour=0, minute=0) + timedelta(days=7)
    if mode == 'day':
        return date.replace(hour=0, minute=0) + timedelta(days=1)
    raise ValueError('{} is not a proper mode; please use month, week, or day.'.format(mode))


def dt_to_url(date):
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
    # TODO Timezone changer
    set_logger()
    scrap()
