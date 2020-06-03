import os
from datetime import datetime
import time
import json
import pickle
import threading
import random

import requests
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

from Api import InstagramAPI
from Api import InstagramLogin

from pathlib import Path

import logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

from logging.handlers import TimedRotatingFileHandler
logname = "insta.log"
handler = TimedRotatingFileHandler(logname, when="midnight", interval=1)
handler.suffix = "%Y%m%d"
formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)

import pickle

class Config(object):
    def __init__(self, filename):
        self.filename = filename
        self.lock = threading.Lock()
        self.delaylist = {}

        #self.save_worker = threading.Thread(target=self.save_worker_func)
        #self.save_worker.start()
        if not os.path.exists(filename):
            self.config = {}
            self.config["user_count"] = 0
            self.config["users"] = []
            self.config["stats"] = []
            self.config["request_users"] = []
            self.save_config()
        else:
            self.file = open(filename)
            self.config = json.load(self.file)


        self.language_file = Path("./language.json")
        if not os.path.exists(self.language_file):
            lng = {}
            with open(self.language_file, "w") as language:
                json.dump(lng, language, indent=4)




    def has_key(self, json, key):
        try:
            item = json[key]
            return True
        except Exception:
            return False

    def find_index(self, json_object, key, name):
        index = 0
        for dict in json_object:
            try:
                if dict[key] == name:
                    return index
            except :
                pass
            index+=1
        return -1

    def save_config(self):
        self.lock.acquire()
        with open(self.filename, "w") as config_file:
            json.dump(self.config, config_file)
        self.lock.release()

    def create_list_item(self, json_list, item):
        self.lock.acquire()
        json_list.append(item)
        self.lock.release()

    def clean(self):
        list = []
        new_users = []
        for u in self.config["users"]:
            if not u["userid"] in list:
                new_users.append(u)
                list.append(u["userid"])
        self.config["users"] = new_users
        return len(self.config["users"]) - len(new_users)

# DAY STATS

    def create_day(self, day):
        new_day = {"day": str(day),
                  "date": datetime.now().strftime("%Y-%m-%d"),
                  "downloads": 0}
        self.create_list_item(self.config["stats"], new_day)

        return len(self.config["stats"]) - 1

    def get_day_unsafe(self):
        day = int((time.time() - time.time() % 86400) / 86400)
        index = self.find_index(self.config["stats"], "day", str(day))
        if index == -1:
            index = self.create_day(day)

        return self.config["stats"][index]

    def get_day(self):
        day = self.get_day_unsafe()
        return json.loads(json.dumps(day))

    def day_add_download(self):
        day = self.get_day_unsafe()
        self.lock.acquire()
        day["downloads"] += 1
        self.lock.release()

# USER STATS

    def create_user(self, userid, username):
        i = self.find_index(self.config["users"], "userid", str(userid))
        if i != -1:
            self.config["users"][i]["username"] = username

            return i


        new_user = {"userid": str(userid),
                    "username": username,
                    "downloads": 0,
                    "priority": 1,
                    "latest_item_time": 0,
                    "downloaded_from": []}

        self.lock.acquire()
        self.config["user_count"] += 1
        self.lock.release()
        self.create_list_item(self.config["users"], new_user)


        return len(self.config["users"]) - 1

    def get_user_unsafe(self, userid, create=False, username = ""):
        index = self.find_index(self.config["users"], "userid", str(userid))
        if index == -1:
            if create and username != "":
                self.create_user(userid, username)
            else:
                return None
        return self.config["users"][index]

    def get_user(self, userid):
        user = self.get_user_unsafe(userid)
        if user == None:
            return None
        return json.loads(json.dumps(user))

    def user_add_download(self, userid, username, downloaded_from):
        user = self.get_user_unsafe(userid, create=True, username=username)
        if user == None:
            return False
        self.lock.acquire()
        user["downloads"] += 1
        self.lock.release()

        index = self.find_index(user["downloaded_from"], "username", downloaded_from)
        if index == -1:
            self.create_list_item(user["downloaded_from"], {"username": downloaded_from,
                                            "downloads": 1})
        else:
            self.lock.acquire()
            user["downloaded_from"][index]["downloads"] += 1
            self.lock.release()

        return True

    def user_set_itemtime(self, userid, username, item_time):
        user = self.get_user_unsafe(userid, create=True, username=username)
        self.lock.acquire()
        user["latest_item_time"] = item_time
        self.lock.release()

    def upgrade_priority(self, username):
        index = self.find_index(self.config["users"], "username", username)
        if index == -1:
            return "none"
        user = self.config["users"][index]
        user["priority"] += 1

        return user["priority"]
        

    def downgrade_priority(self, username):
        index = self.find_index(self.config["users"], "username", username)
        if index == -1:
            return "none"
        user = self.config["users"][index]
        user["priority"] -= 1

        return user["priority"]
# REQUESTED STATS

    def create_requested(self, username):
        new_requested = {"username": username,
                        "requested": 0,
                        "requestors": []}
        self.create_list_item(self.config["request_users"], new_requested)
  
    def get_requested_unsafe(self, username):
        index = self.find_index(self.config["request_users"], "username", username)
        if index == -1:
            self.create_requested(username)
            index == len(self.config["request_users"]) - 1
        return self.config["request_users"][index]

    def get_requested(self, username):
        requested = self.get_requested_unsafe(username)
        if requested == None:
            return None
        return json.loads(json.dumps(requested))

    def add_get_requestor(self, requestor_json, userid):
        index = self.find_index(requestor_json["requestors"], "userid", userid)
        if index == -1:
            requestor = {"userid": userid,
                         "requested": 0}
            self.create_list_item(requestor_json["requestors"], requestor)
            self.lock.acquire()
            requestor_json["requested"] +=1
            self.lock.release()
            index == len(requestor_json["requestors"]) - 1
        return requestor_json["requestors"][index]

    def remove_requestor(self, username):
        for thing in self.config["request_users"]:
            if thing["username"] == username:
                self.lock.acquire()
                self.config["request_users"].remove(thing)
                self.lock.release()

    def requested_add_request(self, username, requested_by_userid):
        requested = self.get_requested_unsafe(username)
        requestor = self.add_get_requestor(requested, str(requested_by_userid))
        self.lock.acquire()
        requestor["requested"] += 1
        self.lock.release()

# Language
    def get_text(self, text_key):
        file = open(self.language_file)
        lng = json.load(file)
        if self.has_key(lng, text_key):
            return lng[text_key]
        else:
            return "unknown, dm the dev or sth pls"

    def add_text(self, text_key, text):
        file = open(self.language_file)
        lng = json.load(file)
        with open(self.language_file, "w+") as language:
            lng[text_key] = text
            json.dump(lng, language, indent=4)

#DELAY
    def reset_delay(self):
        self.delaylist = {}

    def capture_delay(self, delay, priority):
        if not self.has_key(self.delaylist, priority):
            self.delaylist[priority] = []
        
        if len(self.delaylist[priority]) >= 20:
            self.delaylist[priority].remove(self.delaylist[priority][0])

        self.delaylist[priority].append(delay)

    def get_delay(self, priority):
        if not self.has_key(self.delaylist, priority):
            self.delaylist[priority] = []
        
        delay = 0
        i = 0
        for d in self.delaylist[priority]:
            delay += d
            i += 1
        if i > 0:
            delay = delay / i
        else:
            delay = 0
        return int(delay * 10) // 10

class Uploader(object):
    def __init__(self, API, config, number, sessionpath):
        self.api = API
        self.cfg = config
        self.number = number
        self.sessionpath = sessionpath
        self.upload_worker = threading.Thread(target=self.upload_worker_func)
        self.running = False
        self.queue = []

        self.sleep = [0,60]

        self.counter = 0
        self.errors = 0

    def start(self):
        self.running = True
        self.upload_worker.start()

    def stop(self):
        self.running = False


    def extract_priority(self, json):
        try:
            return int(json["priority"])
        except KeyError:
            return 0

    def queue_contains(self, itemid):
        for item in self.queue:
            if item["item_id"] == itemid:
                return True
        return False

    def queue_contains_post(self, media_id, username):
        for item in self.queue:
            if item["username"] == username:
                try:
                    if item["media_id"] == media_id:
                        return True
                except Exception as e:
                    pass
        return False


    def reload_api(self):
        uploaderpath = self.sessionpath

        if os.path.exists(uploaderpath):
            self.api = pickle.load(open(uploaderpath, "rb"))
            logging.info("Reloaded uploader {0}".format(self.sessionpath))
        else:
            logging.warning("Failed to reload uploader")


    def send_media(self, url, itemid, mediatype, media_id, userid, username, download_from, sent, cut=False):
        user = self.cfg.get_user(userid)
        

        item = {"priority": user["priority"],
                "url": url,
                "item_id": itemid,
                "media_type": mediatype,
                "media_id": media_id,
                "cut": cut,
                "sent": sent,
                "userid": userid,
                "username": username,
                "download_from": download_from}

        self.queue.append(item)

    def upload_video(self, item, filename):
        full_path = str(Path("./videos/{f}.mp4".format(f=filename)))
        video = requests.get(item["url"])
        open(full_path, "wb").write(video.content)
        if item["cut"] == True:
            new_path = str(Path("./videos/{f}_cut.mp4".format(f=filename)))
            ffmpeg_extract_subclip(full_path, 0, 59, targetname=new_path)
            os.remove(full_path)
            full_path = new_path
        xd = self.api.prepare_direct_video(item["userid"], full_path)
        try:
            self.api.send_direct_video(xd)
        except Exception as e:
            rnd = random.randint(1, 5) 
            time.sleep(rnd)
            self.api.send_direct_video(xd)
        
        user = self.cfg.get_user(item["userid"])
        if user["downloads"] == 0:
            self.api.sendMessage(str(item["userid"]), "This bot was developed by @instaagroup.\n Check us out or modify the code on GitHub!")
            self.counter += 1
            logging.info("Welcomed {u}!".format(u=item["username"]))
        cfg.user_add_download(item["userid"], item["username"], item["download_from"])
        cfg.day_add_download()
        logging.info("{d} successfully downloaded a video from {u}".format(d=item["username"], u=item["download_from"]))

        logging.info("Timespan since sent video: {0}ms".format(str((time.time() * 1000 // 1) - item["sent"] // 1000)))
        self.cfg.capture_delay(int(time.time() - item["sent"] // 1000000), item["priority"])
        if os.path.exists(full_path):
            os.remove(full_path)
    def upload_photo(self, item, filename):
        full_path = str(Path("./images/{f}.jpg".format(f=filename)))
        video = requests.get(item["url"])
        open(full_path, "wb").write(video.content)
        xd = self.api.prepare_direct_image(item["userid"], full_path)
        try:
            self.api.send_direct_image(xd)
        except Exception as e:
            rnd = random.randint(1, 20) 
            time.sleep(rnd)
            self.api.send_direct_image(xd)
        user = self.cfg.get_user(item["userid"])
        if user["downloads"] == 0:
            self.api.sendMessage(str(item["userid"]), "This bot was developed by @instaagroup.\n Check us out or modify the code on GitHub!")
            self.counter += 1
            logging.info("Welcomed {u}!".format(u=item["username"]))
        cfg.user_add_download(item["userid"], item["username"], item["download_from"])
        cfg.day_add_download()
        logging.info("{d} successfully downloaded a photo from {u}".format(d=item["username"], u=item["download_from"]))

        logging.info("Timespan since sent video: {0}ms".format(str((time.time() * 1000 // 1) - item["sent"] // 1000)))
        self.cfg.capture_delay(int(time.time() - item["sent"] // 1000000), item["priority"])
        if os.path.exists(full_path):
            os.remove(full_path)

    def upload_worker_func(self):
        while self.running:
            if len(self.queue) == 0:
                time.sleep(1)
                continue

            self.queue.sort(key=self.extract_priority, reverse=True)

            item = None
            filename = None
            full_path = ""
            try:
                item = self.queue[0]
                if item["priority"] > 1:
                    self.sleep = [5, 15]
                rnd = random.randint(self.sleep[0], self.sleep[1]) 
                time.sleep(rnd)
                filename = str(int(round(time.time() * 10000)))
                if item["media_type"] == 2:
                    self.upload_video(item, filename)
                elif item["media_type"] == 1:
                    self.upload_photo(item, filename)

                self.sleep = [10, 30]
                self.queue.remove(item)
            except Exception as e:
                if os.path.exists(full_path):
                    os.remove(full_path)
                logging.error("Error with {u} {er}".format(er=str(e), u=item["username"]))
                if not "few minutes" in str(e):
                    self.queue.remove(item)
                self.reload_api()
                self.sleep = [30, 120]
            time.sleep(1)


class InboxItem(object):
    def __init__(self, json):
        self.json = json
        self.item = json["items"][0]
        self.users = json["users"]
        self.is_group = json["is_group"]
        self.item_type = self.item["item_type"]
        self.author_id = self.item["user_id"]
        self.timestamp = self.item["timestamp"]


    def get_media(self):
        location = self.item[self.item_type]
        if self.item_type == "story_share":
            location = location["media"]
        elif self.item_type == "felix_share":
            location = location["video"]

        return location

    def get_media_type(self):
        if self.item_type != "media_share" and self.item_type != "story_share" and self.item_type != "felix_share" :
            return 0

        return self.get_media()["media_type"]

    def get_item_poster(self):
        type = self.get_media_type()
        if type == 0:
            return self.author_id
        name = "~unkown"
        if 0 < type < 3:
            name = self.get_media()["user"]["username"]
        if type == 8:
            name = self.item["media_share"]["user"]["username"]
        return name

    def get_video_url(self):
        url = self.get_media()["video_versions"][0]["url"]
        return url

    def get_image_url(self):
        url = self.get_media()["image_versions2"]["candidates"][0]["url"]
        return url

    def get_multipost_url(self, items, num):
        item = items[num - 1]
        if(item["type"] == 2):
            return item["url"]
        else:
            return "error"
    
    def get_multipost_length(self):
        return len(self.item["media_share"]["carousel_media"])

    def get_multipost_json(self):
        jf = {}
        jf["author_id"] = self.author_id
        jf["download_from"] = self.get_item_poster()
        jf["items"] = []
        for x in self.item["media_share"]["carousel_media"]:
            if(x["media_type"] == 2):
                jf["items"].append({"type": x["media_type"],
                                    "url": x["video_versions"][0],
                                    "duration": x["video_duration"]})
            else:
                jf["items"].append({"type": x["media_type"],
                                    "url": x["image_versions2"][0]})
        return jf


class InboxHandler(object):
    def __init__(self, API, config, uploader, d_uploader):
        self.api = API
        self.cfg = config
        self.count = 0
        self.uploader_list = uploader
        self.uploader = self.uploader_list[0]

        self.admins = ["instaagroup", "rxc0.i", "dome271"]

        self.first = True

    def is_inbox_valid(self, json_inbox):
        millis = time.time() // 1000
        try:
            snapshot = json_inbox["snapshot_at_ms"] // 1000000
        except Exception:
            snapshot = 0
    
        return millis == snapshot

    def is_multipost_expected(self, userid):
        return os.path.exists(Path("./multi/{u}.json".format(u=str(userid))))

    def run(self):
        while True:
            try:
                try:
                    self.handle_inbox()
                    time.sleep(15)
                except Exception as e:
                    logging.error("Handle Inbox crashed:  {0}".format(str(e)))
                    time.sleep(10)
            except:
                self.cfg.save_config()
                time.sleep(10)
        for u in self.uploader_list:
            u.running = False
        logging.error("dead, oof")

    def get_uploader(self):
        upl = self.uploader_list[0]
        for u in self.uploader_list:
            if len(upl.queue) > len(u.queue):
                upl = u

        return upl

    def is_post_queued(self, media_id, username):
        total = 0
        for upl in self.uploader_list:
            if upl.queue_contains_post(media_id, username):
                return True
        return False

    def queue_count(self):
        total = 0
        for upl in self.uploader_list:
            q = len(upl.queue)
            print(str(q), end=" ")
            total += q
        print("Total {0}".format(total))
        total = 0

    def queue_total(self):
        total = 0
        for upl in self.uploader_list:
            q = len(upl.queue)
            total += q
        return total
            
#item handler
    def handle_video(self, username, item, same_queue=False, videojson = None, bypass = False):
        user = self.cfg.get_user(item.author_id)
        if bypass != True and user["latest_item_time"] == item.timestamp:
            return
        self.cfg.user_set_itemtime(item.author_id, username, item.timestamp)

        if not bypass and self.is_post_queued(item.get_media()["pk"], username):
            self.api.sendMessage(str(item.author_id), "That post is already in the queue.")
            return

        if bypass == False:
            self.do_delay_ad(username, item)

        if videojson == None:
            url = item.get_video_url()
            duration = item.get_media()["video_duration"]
        else:
            url = videojson["video_versions"][0]["url"]
            duration = videojson["video_duration"]

        if duration >= 70:
            self.api.sendMessage(str(item.author_id), self.cfg.get_text("video_to_long"))
            return

        uploader = self.uploader
        
        if not same_queue:
            uploader = self.get_uploader()
            self.uploader = uploader
            
        uploader.send_media(url, item.item["item_id"], 2, item.get_media()["pk"], str(item.author_id),  username, item.get_item_poster(), item.timestamp, cut = duration >= 60)
        logging.info("Added {u} to queue".format(u=username))

    def handle_text(self, username, item, text = ""):
        if self.cfg.get_user(item.author_id)["latest_item_time"] == item.timestamp:
            return
        self.cfg.user_set_itemtime(item.author_id, username, item.timestamp)

        if text == "":
            try:
                text = item.item["text"]
            except:
                pass
        #ADMINCOMMANDS
        if username in self.admins:  
            if text.startswith("!upgrade"):
                pusername = text.replace("!upgrade ", "")
                now = self.cfg.upgrade_priority(pusername)
                self.api.sendMessage(str(item.author_id), "{u} now has priority lvl {lv}".format(u=pusername, lv = now))
            elif text.startswith("!downgrade"):
                pusername = text.replace("!downgrade ", "")
                now = self.cfg.downgrade_priority(pusername)
                self.api.sendMessage(str(item.author_id), "{u} now has priority lvl {lv}".format(u=pusername, lv = now))
            elif text.startswith("!remove"):
                pusername = text.replace("!remove ", "")
                total = 0
                for upl in self.uploader_list:
                    for i in upl.queue:
                        if i["username"] == pusername:
                            total += 1
                            upl.queue.remove(i)
                self.api.sendMessage(str(item.author_id), "Removed {} queue items from that user!".format(total))
            elif text.startswith("!reset"):
                self.cfg.reset_delay()
                self.api.sendMessage(str(item.author_id), "Resetted!")
            elif text.startswith("!most"):
                result = {}
                for u in self.uploader_list:
                    for q in u.queue:
                        if q["username"] not in result.keys():
                            result[q["username"]] = 1
                        else:
                            result[q["username"]] += 1
                xd = sorted(result.items(), key=lambda x: x[1], reverse=True)
                new = []
                for i in range(0,10):
                    new.append(xd[i])
                self.api.sendMessage(str(item.author_id), json.dumps(new, indent=4))
            if text == "!day":
                downloads = self.cfg.get_day()["downloads"]
                self.api.sendMessage(str(item.author_id), "{dl} downloads today!".format(dl = downloads))
            elif text == "!delay":
                msg = ""
                for i in range(0, 100):
                    d = self.cfg.get_delay(i)
                    if d != 0:
                        msg += "Priority Lv {lvl} - {delay}s \r\n".format(lvl=i, delay=d)
                self.api.sendMessage(str(item.author_id), msg)
        return

    def handle_link(self, username, item):
        if username in self.admins: 
            self.handle_text(username, item, item.item["link"]["text"]) 
        if self.cfg.get_user(item.author_id)["latest_item_time"] == item.timestamp:
            return
        self.cfg.user_set_itemtime(item.author_id, username, item.timestamp)


        self.api.sendMessage(str(item.author_id), self.cfg.get_text("links_not_supported"))
        return

    def handle_image(self, username, item, same_queue=False, imagejson = None, bypass = False):
        user = self.cfg.get_user(item.author_id)
        if bypass != True and user["latest_item_time"] == item.timestamp:
            return
            
        self.cfg.user_set_itemtime(item.author_id, username, item.timestamp)


        if not bypass and self.is_post_queued(item.get_media()["pk"], username):
            self.api.sendMessage(str(item.author_id), "That post is already in the queue.")
            return

        if bypass == False:
            self.do_delay_ad(username, item) 

        if imagejson == None:
            url = item.get_image_url()
        else:
            url = imagejson["image_versions2"]["candidates"][0]["url"]

        uploader = self.uploader

        if not same_queue:
            uploader = self.get_uploader()
            self.uploader = uploader

        uploader.send_media(url, item.item["item_id"], 1, item.get_media()["pk"], str(item.author_id),  username, item.get_item_poster(), item.timestamp, cut = False)
        logging.info("Added {u} to queue".format(u=username))

    def handle_placeholder(self, username, item):
        if self.cfg.get_user(item.author_id)["latest_item_time"] == item.timestamp:
            return
        self.cfg.user_set_itemtime(item.author_id, username, item.timestamp)
        if "Unavailable" in item.get_media()["title"]:
            msg = item.get_media()["message"]
            if "@" in msg:
                username_requested = "".join([i for i in msg.split() if i.startswith("@")][0])[1:]
                self.cfg.requested_add_request(username_requested, item.author_id)
            
                self.api.sendMessage(str(item.author_id), self.cfg.get_text("requested"))
                return
            elif "deleted" in msg:
                self.api.sendMessage(str(item.author_id), self.cfg.get_text("deleted"))
            else:
                self.api.sendMessage(str(item.author_id), self.cfg.get_text("blocked"))
        return

    def handle_story(self, username, item):
        try:
            title = item.item["story_share"]["title"]
            msg = item.item["story_share"]["message"]
            reason = item.item["story_share"]["reason"]
        except :
            title = "nope"
            message = None

        if title != "nope":
            if reason != 4:
                return
            #Not following
            if self.cfg.get_user(item.author_id)["latest_item_time"] == item.timestamp:
                return
            self.cfg.user_set_itemtime(item.author_id, username, item.timestamp)
            username_requested = "".join([i for i in msg.split() if i.startswith("@")][0])[1:]
            self.cfg.requested_add_request(username_requested, item.author_id)
            self.api.sendMessage(str(item.author_id), self.cfg.get_text("requested"))
            return

        if item.get_media_type() == 2:
            self.handle_video(username, item)
        elif item.get_media_type() == 1:
            self.handle_image(username, item)

    def handle_media_share(self, username, item):
        if self.cfg.get_user(item.author_id)["latest_item_time"] == item.timestamp:
            return

        if item.get_media_type() == 2:
            self.handle_video(username, item)

        elif item.get_media_type() == 1:
            self.handle_image(username, item)

        elif item.get_media_type() == 8:
            if self.cfg.get_user(item.author_id)["latest_item_time"] == item.timestamp:
                return
            if self.queue_total() > 2000:
                self.api.sendMessage(str(item.author_id), "Slideposts are currently disabled due to heavy server load. Please come back later.")
                self.cfg.user_set_itemtime(item.author_id, username, item.timestamp)
                return
            for i in item.get_media()["carousel_media"]:
                if i["media_type"] == 2:
                    self.handle_video(username, item, True, i, True)
                elif i["media_type"] == 1:
                    try:
                        self.handle_image(username, item, True, i, True)
                    except Exception as e:
                        print("skip")
                    

    def handle_profilepic(self, username, item):
        if self.cfg.get_user(item.author_id)["latest_item_time"] == item.timestamp:
            return
        self.cfg.user_set_itemtime(item.author_id, username, item.timestamp)
        if item.item["profile"]["has_anonymous_profile_picture"]:
            self.api.sendMessage(str(item.author_id), "That profile picture is anonymous")
        url = item.item["profile"]["profile_pic_url"]
        self.uploader.send_media(url, item.item["item_id"], 1, str(item.author_id),  username, item.item["profile"]["username"], item.timestamp, cut = False)
        logging.info("Added {u} to queue".format(u=username))


    def do_delay_ad(self, username, item):
        user = self.cfg.get_user(item.author_id)
        priority = user["priority"]
        delay = self.cfg.get_delay(priority)
        print("user " + username + " " + str(delay))
        if delay > 300:
            uprankdelay = self.cfg.get_delay(priority+1)
            if uprankdelay > 150:
                return
            self.api.sendMessage(str(item.author_id), "There are {q} people in the queue. Let an admin upgrade your priority".format(q=self.queue_total()))

    def handle_inbox(self):
        print("handle inbox")
        self.cfg.save_config()
        num = 20
        if self.first == True:
            num = 50
            self.first = False
        self.api.getv2Inbox(num)
        with  open(Path("last.json"), "w+") as fp:
            json.dump(self.api.LastJson, fp)
        inbox = self.api.LastJson
        if not self.is_inbox_valid(inbox):
            logging.warning("Invalid inbox.. sleeping 10s")
            time.sleep(10)
            return

        for i in inbox["inbox"]["threads"]:
            try:
                username = i["users"][0]["username"]
            except :
                username = "@UNKNOWN@"

            item = InboxItem(i)
            if item.is_group:
                continue
            self.cfg.create_user(item.author_id, username)

            if item.item_type == "text":
                self.handle_text(username, item)

            elif item.item_type == "link":
                self.handle_link(username, item)

            elif item.item_type == "profile":
                self.handle_profilepic(username, item)

            elif item.item_type == "placeholder":
                self.handle_placeholder(username, item)

            elif item.item_type == "story_share":
                self.handle_story(username, item)

            elif item.item_type == "media_share":
                self.handle_media_share(username, item)

        if inbox["pending_requests_total"] == 0:
            time.sleep(1)
            self.queue_count()
            x = 0
            for upl in self.uploader_list:
                path = "uploader{0}_queue".format(str(x))
                with  open(path, "w+") as fp:
                    json.dump(upl.queue, fp)
                x+=1
            return

        print("Now pending..")
        self.api.get_pending_inbox()
        inbox = self.api.LastJson
        for i in inbox["inbox"]["threads"]:
            try:
                username = i["users"][0]["username"]
            except :
                username = "@UNKNOWN@"

            item = InboxItem(i)
            self.api.approve_pending_thread(i["thread_id"])
            self.cfg.create_user(item.author_id, username)

            if item.item_type == "text":
                self.handle_text(username, item)

            elif item.item_type == "link":
                self.handle_link(username, item)

            elif item.item_type == "placeholder":
                self.handle_placeholder(username, item)

            elif item.item_type == "story_share":
                self.handle_story(username, item)

            elif item.item_type == "media_share":
                self.handle_media_share(username, item)

username = "USERNAME"
password = "PASSWORD"

cfg = Config(Path("config.json"))
sessionpath = Path("sessions/{u}.session".format(u = username))

mainlogin = InstagramLogin(username, password, Path("./sessions"))
api = mainlogin.api

if not api.isLoggedIn:
    logging.error("Failed to login")
    exit()

uploaders = []
for x in range(0, 2):
    uploaderpath = Path("sessions/" + username +"uploader_{0}.session".format(x))
    queuepath = Path("uploader{0}_queue".format(x))

    if os.path.exists(uploaderpath):
        uapi = pickle.load(open(uploaderpath, "rb"))
        if not uapi.isLoggedIn:
            uapi.login()
    else:
        uapi = InstagramAPI(username, password)
        uapi.login()
        pickle.dump(uapi, open(uploaderpath, "wb"))
    test_upl = Uploader(uapi, cfg, x, uploaderpath)

    if os.path.exists(queuepath):
        test_upl.queue = json.load(open(queuepath))

    test_upl.start()
    uploaders.append(test_upl)


inbox = InboxHandler(api, cfg, uploaders, [])
inbox.run()


