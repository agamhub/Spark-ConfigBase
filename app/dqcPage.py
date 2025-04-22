import csv
import os
import math

CONFIG_DIR = '/app/config'
CONFIG_FILE = 'DataQuality_Config.csv'
CONFIG_FILEPATH = os.path.join(CONFIG_DIR, CONFIG_FILE)
ROWS_PER_PAGE = 10

def get_headers_from_csv(filepath):
    """Reads the header row from the CSV file."""
    try:
        with open(filepath, 'r', newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter='|')
            headers = next(reader, None)
            return headers if headers else []
    except FileNotFoundError:
        return []
    except Exception:
        return []

def get_dqc_config_data(filepath):
    """Reads all config data from the CSV file."""
    config_data = []
    try:
        with open(filepath, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter='|', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for row in reader:
                config_data.append(row)
        return config_data
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return []

def save_dqc_config_data(filepath, data):
    """Writes config data to the CSV file."""
    if not data:
        return
    fieldnames = data[0].keys()
    try:
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='|', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(data)
    except Exception as e:
        print(f"Error writing CSV: {e}")

def get_config_filepath():
    """Returns the file path for the DQC configuration."""
    return CONFIG_FILEPATH

def get_paginated_dqc_data(page, filter_value, filter_column, sort_column, sort_order):
    """Fetches paginated DQC data with filtering and sorting."""
    config_data = get_dqc_config_data(CONFIG_FILEPATH)
    headers = get_headers_from_csv(CONFIG_FILEPATH)

    # Apply filtering if filter parameters are provided
    if filter_column and filter_value:
        config_data = [row for row in config_data if str(row.get(filter_column, '')).lower() == filter_value.lower()]

    # Apply sorting if sort parameters are provided
    if sort_column:
        config_data.sort(key=lambda x: x.get(sort_column, ''), reverse=(sort_order == 'desc'))

    start_index = (page - 1) * ROWS_PER_PAGE
    end_index = start_index + ROWS_PER_PAGE
    paginated_data = config_data[start_index:end_index]
    total_pages = math.ceil(len(config_data) / ROWS_PER_PAGE)

    return {
        "headers": headers,
        "paginated_data": paginated_data,
        "total_pages": total_pages,
        "error_message": None
    }