import psycopg2
import datetime
import numpy as np
from util import setup_logger

log = setup_logger(__name__)

class DatabaseConnection(object):
    """
    Class for PostgreSQL connections using psycopg2
    http://initd.org/psycopg/docs/usage.html
    """

    def __init__(self, dbname, user, password, host="localhost"):
        try:
            self.conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host)
            self.cur = self.conn.cursor()
        except:
            log.error("Could not connect to databse!")
            return
        if (not self.data_table_exists()):
            self.create_data_table()
        if (not self.price_table_exists()):
            self.create_price_table()

    def close(self):
        """
        close the database connection
        """
        self.conn.commit()
        self.cur.close()
        self.conn.close()

    # ------------ price table ------------

    def price_table_exists(self):
        self.cur.execute("SELECT * FROM information_schema.tables where table_name=%s ;", ("price",))
        return self.cur.rowcount > 0

    def create_price_table(self):
        """
        create the price data table
        format: |id|time|coin_id|coin_name|symbol|subreddit|price|percent_change_1h|percent_change_24h|
        """
        self.cur.execute("CREATE TABLE price (id serial PRIMARY KEY, time timestamp,"
                         "coin_id varchar, coin_name varchar, symbol varchar, subreddit varchar,"
                         "price real, percent_change_1h real, percent_change_24h real);")
        self.conn.commit()
        log.info("Created price table.")

    def delete_price_table(self):
        """
        drop the data table
        """
        self.cur.execute("DROP TABLE data;")
        self.conn.commit()
        log.info("Dropped data table.")

    def insert_price(self, price_data_dict):
        """
        insert a price item into the table
        """
        self.cur.execute("INSERT INTO price (time, coin_id, coin_name, symbol, subreddit, price, percent_change_1h,  percent_change_24h)"
                         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s);",
                         (price_data_dict["time"], price_data_dict["coin_id"], price_data_dict["coin_name"],
                          price_data_dict["symbol"], price_data_dict["subreddit"], price_data_dict["price"],
                          price_data_dict["percent_change_1h"], price_data_dict["percent_change_24h"])
        )
        self.conn.commit()

    # ------------ data table ------------

    def data_table_exists(self):
        self.cur.execute("SELECT * FROM information_schema.tables where table_name=%s ;", ("data",))
        return self.cur.rowcount > 0

    def create_data_table(self):
        """
        create the main data table
        format: |id|start_time|end_time|subreddit|subscribers|submissions|comment_rate|mentions|
        """
        self.cur.execute("CREATE TABLE data (id serial PRIMARY KEY, start_time timestamp,"
                         "end_time timestamp, subreddit varchar, subscribers int,"
                         "submissions int, comment_rate real, mentions int);")
        self.conn.commit()
        log.info("Created data table.")

    def delete_data_table(self):
        """
        drop the data table
        """
        self.cur.execute("DROP TABLE data;")
        self.conn.commit()
        log.info("Dropped data table.")

    def insert_data(self, data_dict):
        """
        insert a data item into the table
        """
        self.cur.execute("INSERT INTO data (start_time, end_time, subreddit, subscribers, submissions, comment_rate, mentions)"
                         "VALUES (%s, %s, %s, %s, %s, %s, %s);",
                         (data_dict["start_time"], data_dict["end_time"], data_dict["subreddit"],
                          data_dict["subscribers"], data_dict["submissions"], data_dict["comment_rate"], data_dict["mentions"]))
        self.conn.commit()

    # ------------ data table queries------------

    def get_all_subreddits(self):
        # TODO: method that returns only subreddits that have data in the last day
        """
        returns a list of all subreddits in the database
        """
        self.cur.execute("SELECT DISTINCT subreddit FROM data;")
        return [x[0] for x in self.cur.fetchall()]

    def get_rows_for_subreddit(self, subreddit, start=None, end=None):
        if start is None: start = datetime.datetime.fromtimestamp(0)
        if end is None: end = datetime.datetime.now()
        querystr = "SELECT start_time, end_time, subscribers, submissions, comment_rate, mentions FROM data WHERE subreddit=%s \
            AND end_time < %s AND start_time > %s ORDER BY end_time DESC"
        self.cur.execute(querystr, (subreddit, end, start))
        return self.cur.fetchall()

    def get_metrics_for_subreddit(self, subreddit, start=None, end=None):
        # TODO custom timeinterval, minimum time distance
        """
        gets all tuples of subscribers, submissions and comment_rate in the given time interval

        Args:
            subreddit: string
            start: start-timestamp
            end: end-timestamp

        Returns:
            List of Tuples containing metrics from subreddit, time is decreasing
            If only one of start and end is given the other one is not constrained.
            If neither is given returns the metrics for the last two rows in the table.
        """
        if start is None and end is None:
            querystr = "SELECT subscribers, submissions, comment_rate, mentions FROM data WHERE subreddit=%s \
                    AND end_time in (SELECT DISTINCT end_time FROM data ORDER BY end_time DESC LIMIT 2) \
                    ORDER BY end_time DESC LIMIT 2"
            self.cur.execute(querystr, (subreddit,))
        else:
            if start is None: start = datetime.datetime.fromtimestamp(0)
            if end is None: end = datetime.datetime.now()
            querystr = "SELECT subscribers, submissions, comment_rate, mentions FROM data WHERE subreddit=%s \
                    AND end_time < %s AND start_time > %s ORDER BY end_time DESC"
            self.cur.execute(querystr, (subreddit, end, start))
        return self.cur.fetchall()

    def get_interpolated_data(self, subreddit, timestamp):
        """
        Returns a metrics tuple for the subreddit for the given timestamp.
        Created by linear intrpolation using the two nearest datapoints.
        """
        querystr = "SELECT end_time, subscribers, submissions, comment_rate, mentions FROM data WHERE subreddit=%s \
                AND end_time > %s ORDER BY end_time ASC LIMIT 1"
        self.cur.execute(querystr, (subreddit, timestamp))
        next_newer = self.cur.fetchone()
        querystr = "SELECT end_time, subscribers, submissions, comment_rate, mentions FROM data WHERE subreddit=%s \
                AND end_time < %s ORDER BY end_time DESC LIMIT 1"
        self.cur.execute(querystr, (subreddit, timestamp))
        next_older = self.cur.fetchone()
        if next_newer == None:  # if no newer data exists return the latest data
            return next_older[1:]
        elif next_older == None:  # if no older data exists raise error
            raise ValueError("Cannot interpolate for given timestamp")
        # weighted interpolation
        interval = next_newer[0] - next_older[0]
        weight_newer = (next_newer[0] - timestamp) / interval
        weight_older = (timestamp - next_older[0]) / interval
        return weight_newer*np.array(next_newer[1:]) + weight_older*np.array(next_older[1:])