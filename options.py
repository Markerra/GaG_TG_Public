from sys import maxsize

DEV_CHAT_ID = 931486864 # my chat id 
ADMINS = ["markerra"] # list of admins usernames
AUTOSUBSCRIBE_SEED = "Sugar Apple" # seeds that will be automatically subscribed to on the first interaction
CROP_EXCEPTIONS = {"Carrot", "Apple"} # crops that not require clarification when searching by name
CHECK_INTERVAL = 20 # interval between refreshing all items in seconds
MUT_FILTER = False # a filter that checks for correct mutations

KG_LIMIT = 100000 # maximum allowed mass (kg) for calculations
QUANTITY_LIMIT = 1000 # maximum allowed quantity for calculations
PRICE_LIMIT = maxsize # price limit for calculations (-1 to off)

DB_PATH         =   'db/' # database folder
USERS_PATH      =   DB_PATH + 'users.json' # users database
SUBS_PATH       =   DB_PATH + 'subscriptions.json' # users subscriptions database
SEEDS_PATH      =   DB_PATH + "seeds.json" # seeds database
GEAR_PATH       =   DB_PATH + "gear.json" # gear database
EGGS_PATH       =   DB_PATH + "eggs.json" # eggs database
ESHOPS_PATH     =   DB_PATH + "eshops/prehistoric.json" # event shop items database
EVENTS_PATH     =   DB_PATH + "events.json" # weathers database
MUTATIONS_PATH  =   DB_PATH + "mutations.json" # mutations database
CROPS_PATH      =   DB_PATH + "crops.json" # crops database




















TOKEN = "" # Telegram bot token