import praw
import datetime
import numpy as np
import re
import util
# add logging

class RedditStats(object):

    def __init__(self, hours=12):
        auth = util.get_reddit_auth()
        self.reddit = praw.Reddit(**auth)

        # start yesterday
        self.hours = hours
        self.default_start = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
        # end now
        self.default_end = datetime.datetime.utcnow()

    def get_num_submissions(self,
                            subreddit,
                            hours=None,
                            end=None):

        '''
        Get number of submissions to subreddit in time range.
        '''
        if hours is None:
            start = self.default_start
        else:
            start = self.default_end - datetime.timedelta(hours=hours)
        if end is None:
            end = self.default_end
        return len([s for s in self.reddit.subreddit(subreddit).submissions(start.timestamp(), end.timestamp())])

    def get_num_subscribers(self, subreddit):
        return (self.reddit.subreddit(subreddit).subscribers)

    def get_num_comments_per_hour(self, subreddit, hours=None):
        if hours is None:
            start = self.default_start
        else:
            start = self.default_end - datetime.timedelta(hours=hours)
        comm = self.reddit.subreddit(subreddit).comments(limit=1024)
        cnt = 0
        for c in comm:
            cnt += 1
            if c.created_utc < int(start.timestamp()):
                break
        if cnt <= 1:
            return 0.
        comments_per_sec_in_on_day = float(cnt)/np.abs(int(self.default_end.timestamp()) - int(start.timestamp()))
        return comments_per_sec_in_on_day*3600

    def get_mentions(self, coin_name_array, subreddit_list, hours=None, include_submissions=False):
        """
        counts how often words from coin_name_tuple were mentioned in subreddits from subreddit list
        since start
        """
        if hours is None:
            start = self.default_start
        else:
            start = self.default_end - datetime.timedelta(hours=hours)
        count_list = len(coin_name_array) * [0]
        regex_list = []
        for coin_name_tuple in coin_name_array:
            pattern = r"\b|\b".join(coin_name_tuple)
            pattern = r"\b"+pattern+r"\b"
            regex_list.append(re.compile(pattern, re.I|re.UNICODE))
        for sub in subreddit_list:
            comments = self.reddit.subreddit(sub).comments(limit=1024)
            for comm in comments:
                if int(comm.created) < int(start.timestamp()):
                    break
                for i, regex in enumerate(regex_list):
                    if not re.search(regex, comm.body) is None:
                        count_list[i] += 1
            if include_submissions:
                for submission in self.reddit.subreddit(sub).new():
                    if (int(submission.created) < int(start.timestamp())):
                        break
                    for i, regex in enumerate(regex_list):
                        if not re.search(regex, submission.title) is None:
                            count_list[i] += 1
        return count_list

    def compile_dict(self, subreddit, hours=None):
        if hours is None:
            hours = self.hours
        d = {}
        d["time"] = datetime.datetime.fromtimestamp(int(self.default_end.timestamp()))
        d["hours"] = hours
        d["subreddit"] = subreddit
        d["subscribers"] = self.get_num_subscribers(subreddit)
        d["submissions"] = self.get_num_submissions(subreddit, hours=hours)
        d["comment_rate"] = self.get_num_comments_per_hour(subreddit, hours=hours)
        return d

    def find_subreddits(self, coin_name_list):
        """
        tries to find the corresponding subreddits for a list of crypto coin names
        """
        subreddit_names = []
        keywords = ["crypto", "blockchain", "decentral", "currency", "coin", "trading"]
        # ignore_subs = ["cryptocurrency", "cryptotrading", "cryptotrade", "cryptomarkets", "cryptowallstreet"]
        pattern = "|".join(keywords)
        regex = re.compile(pattern, re.I|re.UNICODE)
        for name in coin_name_list:
            sub_found = True
            try:
                sub = self.reddit.subreddit(name)
                public_description = str(sub.public_description)
                description = str(sub.description)
            except:
                sub_found = False
                # print("Sub {} does not exist".format(name))

            if not sub_found or (re.search(regex, description) == None and re.search(regex, public_description) == None):
                # no keyword appears in subreddit description
                # it's probably not crypto coin related
                print("Sub {} not found or is not crypto related.".format(name))
                # finding alternatives
                # works poorly so its deactivated
                # print("Alternatives:")
                # candidates = self.reddit.subreddits.search(name + " coin")
                # for candidate in candidates:
                #     if candidate.display_name.lower() in ignore_subs:
                #         continue
                #     public_description = str(candidate.public_description)
                #     description = str(candidate.description)
                #     if not (re.search(regex, description) == None and re.search(regex, public_description) == None):
                #         print(candidate.display_name)
                        # subreddit_names.append(name)
            else:
                subreddit_names.append(name)
        return subreddit_names
