# 라이브러리 설정
import streamlit as st
import time
import uuid
from supabase import create_client
import os
from datetime import datetime, timedelta
import pytz
import logging
import requests
from bs4 import BeautifulSoup
import pandas as pd
from googlesearch import search
from g4f.client import Client
from timezonefinder import TimezoneFinder
import re
import json
import urllib.request
import urllib.parse
from langdetect import detect
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor
import threading
import arxiv
from diskcache import Cache
from functools import lru_cache
import xml.etree.ElementTree as ET  
