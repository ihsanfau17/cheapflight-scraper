# Project Overview

The goal of this project is to automate collecting Google Flights search results and turn them into structured data for downstream analysis. Instead of copying values manually from the browser, the script uses Selenium to drive Chrome, load the configured Google Flights query, and extract flight cards one by one. For each flight it captures airline, departure and arrival details (including overnight arrivals), duration, stopover descriptions, and ticket price.

The scraper mimics user behaviour by opening the configured search URL, waiting for the results grid to render, scrolling through the list, and pressing any relevant "View more" buttons to reveal additional cards. It normalises the raw text, removes non-breaking spaces, and writes a clean data set either to the console or to CSV.

The workflow is intended for users who already know the route they want to monitor. You provide the seed Google Flights URL (which includes origin, destination, cabin class, etc.), specify the dates to collect, and the script follows the necessary UI interactions to gather the data automatically.
