
# TODO: implement some kind of dev / prod environment detection to dynamically set this.
# This has time and might be of interest once we decide to ship the application in a 
# docker container or so
DEBUG = True

if DEBUG:
    from .dev import *
else:
    from .prod import *