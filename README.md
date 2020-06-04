# instaadownload

Requirements:
- [Python 3](https://www.python.org/downloads/)
- [FFMPEG](https://ffmpeg.org/download.html) (installed and added to the PATH variable)

Setup:
1. Clone the repo
2. Edit the InstagramDownloader.py file. At the bottom should be a username and a password variable
3. search for self.admins and put in the usernames you want to be admins
4. install the requirements (pip install -r requirements.txt) in the correct folder
5. run python InstagramDownloader.py and wait for 3 logins to happen


## Admincommands: (if youre in the self.admins)
### Priority
- !upgrade [user]
- !downgrade [user]

### Antispam:
- !remove [username] (removes queue items from given username)

### Other
- !delay - avg delay by priority level
- !reset - resets the delay log

- !most - user with most items in queue (used to find spammers)

- !day - downloads of the day (bugging and sometimes switches the current day and the next day)
