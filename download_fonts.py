#!/usr/bin/env python3
import urllib.request
import os

os.makedirs("fonts", exist_ok=True)

fonts = {
    "Niconne-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/niconne/Niconne-Regular.ttf",
    "Montserrat-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Regular.ttf",
    "Montserrat-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Bold.ttf"
}

for filename, url in fonts.items():
    path = os.path.join("fonts", filename)
    if not os.path.exists(path):
        print(f"Downloading {filename}...")
        try:
            urllib.request.urlretrieve(url, path)
            print(f"Successfully downloaded {filename}")
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
    else:
        print(f"{filename} already exists.")
