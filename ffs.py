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
    r = requests.get('https://www.forexfactory.com/timezone.php')
    data = r.text
    soup = BeautifulSoup(data, "lxml")
    tzinfos = soup.find_all('option', selected="selected")
    if tzinfos[0]['value'] == "-5" and tzinfos[1]['value'] == "1":
        return gettz("America/New_York")
    else:
        raise ValueError("The default timezone configuration of forex factory has changed, "
                         "please update.")


def scrap():
    timezone = get_timezone()
    start_dt = get_start_dt()
    base_url = 'https://www.forexfactory.com/'
    fields = ['date', 'time', 'currency', 'impact', 'event', 'actual', 'forecast', 'previous']
    while True:
        try:
            date_url = dt_to_url(start_dt)
        except ValueError:
            logging.info('Successfully retrieved data')
            return
        logging.info('Scraping data for link: {}'.format(date_url))
        r = requests.get(base_url + date_url)
        data = r.text
        soup = BeautifulSoup(data, "lxml")
        table = soup.find("table", class_="calendar__table")
        trs = table.select("tr.calendar__row.calendar_row")
        # some rows do not have a date (cells merged)
        dt = None
        for tr in trs:
            # fields may mess up sometimes, in that case we append to errors.csv
            try:
                for field in fields:
                    data = tr.select("td.calendar__cell.calendar__{}.{}".format(field, field))[0]
                    if field == 'date' and data.text.strip() != '':
                        d = data.text.strip().replace('\n', '')
                        if dt is None:
                            y = str(start_dt.year)
                        else:
                            y = str(get_next_dt(dt, mode='day').year)
                        dt = datetime.strptime(','.join([y, d]), '%Y,%a%b %d') \
                            .replace(tzinfo=timezone)
                    elif field == 'time' and data.text.strip() != '':
                        t = data.text.strip()
                        if 'Day' in t:
                            h = 23
                            m = 59
                            s = 59
                        elif 'Data' in t:
                            h = 0
                            m = 0
                            s = 1
                        else:
                            i = 1 if len(t) == 7 else 0
                            h = int(t[:1 + i]) % 12 + (12 * (t[4 + i:] == 'pm'))
                            m = int(t[2 + i:4 + i])
                            s = 0
                        dt = dt.replace(hour=h, minute=m, second=s)
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
                if dt.second == 1:
                    raise ValueError
                if dt <= start_dt:
                    continue
                if dt >= datetime.now(tz=dt.tzinfo):
                    break
                with open('forex_factory_catalog.csv', mode='a', newline='') as f:
                    writer = csv.writer(f, delimiter=',')
                    writer.writerow([str(dt), currency, impact, event, actual, forecast, previous])
            except TypeError:
                with open('errors.csv', mode='a') as f:
                    f.write(str(dt) + ' (No Event Found)\n')
            except ValueError:
                with open('errors.csv', mode='a') as f:
                    f.write(str(dt.replace(second=0)) + ' (Data For Past Month)\n')
        start_dt = get_next_dt(start_dt, mode=get_mode(date_url))


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


def get_next_dt(dt, mode):
    if mode == 'month':
        (year, month) = divmod(dt.month, 12)
        test = dt.replace(year=dt.year + year, month=month + 1, day=1, hour=0, minute=0)
        return dt.replace(year=dt.year + year, month=month + 1, day=1, hour=0, minute=0)
    elif mode == 'week':
        return dt.replace(hour=0, minute=0) + timedelta(days=7)
    elif mode == 'day':
        return dt.replace(hour=0, minute=0) + timedelta(days=1)
    else:
        raise ValueError('{} is not a proper mode; please use month, week, or day.'.format(mode))


def dt_to_url(dt):
    if dt_is_start_of_month(dt) and dt_is_complete(dt, mode='month'):
        return 'calendar.php?month={}'.format(dt_to_str(dt, mode='month'))
    elif dt_is_start_of_week(dt) and dt_is_complete(dt, mode='week'):
        for weekday in [dt + timedelta(days=x) for x in range(7)]:
            if dt_is_start_of_month(weekday) and dt_is_complete(dt, mode='month'):
                return 'calendar.php?day={}'.format(dt_to_str(dt, mode='day'))
        return 'calendar.php?week={}'.format(dt_to_str(dt, mode='week'))
    elif dt_is_complete(dt, mode='day') or dt_is_today(dt):
        return 'calendar.php?day={}'.format(dt_to_str(dt, mode='day'))
    else:
        raise ValueError('{} is not completed yet.'.format(dt_to_str(dt, mode='day')))


def dt_to_str(dt, mode):
    if mode == 'month':
        return dt.strftime('%b.%Y').lower()
    elif mode == 'week' or mode == 'day':
        return '{d:%b}{d.day}.{d:%Y}'.format(d=dt).lower()
    else:
        raise ValueError('{} is not a proper mode; please use month, week, or day.'.format(mode))


def get_mode(url):
    reg = re.compile('(?<=\\?).*(?=\\=)')
    return reg.search(url).group()


def dt_is_complete(dt, mode):
    return get_next_dt(dt, mode) <= datetime.now(tz=dt.tzinfo)


def dt_is_start_of_week(dt):
    return dt.isoweekday() % 7 == 0


def dt_is_start_of_month(dt):
    return dt.day == 1


def dt_is_today(dt):
    today = datetime.now()
    return today.year == dt.year and today.month == dt.month and today.day == dt.day


if __name__ == '__main__':
    set_logger()
    scrap()
