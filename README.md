ForexFactoryScraper
A more sophisticated web scraper that downloads forex calendar data from ForexFactory.

The download is managed in packets of days, weeks or month to minimize network traffic.
The chosen timezone is Eastern Standard Time (EST) time-zone WITH Day Light Savings adjustments. This is easily adjustable trough the usage of timezone aware datetime objects.
The program starts at the first possible download date, jan 1 2007, and ends on the current day, up to the current time.
Any later executions of the program checks for the datetime of the last entry and updates the list from that point in time.
If an event has the time signature 'All Day' the time will be saves as the maximum value, 23:59:59, to ensure completion of the event at the point or scraping.
The output file will be located in the working directory and be called forex_factory_catalog.csv

It is required to have Google Chrome installed.
All other requirements are within requirements.txt.
You can easily install them with 'pip install -r requirements.txt'.
