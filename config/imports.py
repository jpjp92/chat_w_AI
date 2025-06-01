# config/imports.py
# Standard library imports
import asyncio
import atexit
import json
import random
import logging
import multiprocessing
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import queue
import re
import threading
import time
import types
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import lru_cache

# Third-party imports
import aiohttp
import arxiv
import nest_asyncio
import pandas as pd
import pytz
import requests
import streamlit as st
from bs4 import BeautifulSoup
from diskcache import Cache
from g4f.client import Client
from googlesearch import search
from langdetect import detect
from requests.adapters import HTTPAdapter
from supabase import create_client
from timezonefinder import TimezoneFinder
from urllib3.util.retry import Retry

### original import
# import aiohttp
# import nest_asyncio
# import atexit
# import types
# import streamlit as st
# import time
# import uuid
# from supabase import create_client
# import os
# from datetime import datetime, timedelta
# import pytz
# import logging
# import requests
# from bs4 import BeautifulSoup
# import pandas as pd
# from googlesearch import search
# from g4f.client import Client
# from timezonefinder import TimezoneFinder
# import re
# import json
# import urllib.request
# import urllib.parse
# from urllib3.util.retry import Retry
# from langdetect import detect
# from requests.adapters import HTTPAdapter
# # from requests.packages.urllib3.util.retry import Retry
# from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
# import threading
# import queue
# import multiprocessing
# import arxiv
# from diskcache import Cache
# from functools import lru_cache
# import xml.etree.ElementTree as ET
# import asyncio
# # from soynlp.word import WordExtractor
# # from soynlp.tokenizer import LTokenizer
# # from soynlp.normalizer import repeat_normalize
