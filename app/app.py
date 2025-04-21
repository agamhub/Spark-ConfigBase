from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import math

app = Flask(__name__)
CONFIG_DIR = '/app/config'
CONFIG_FILE = 'master_job.csv'
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

def get_config_data(filepath):
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

def save_config_data(filepath, data):
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

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/config', methods=['GET', 'POST'])
def display_config():
    config_data = get_config_data(CONFIG_FILEPATH)
    headers = get_headers_from_csv(CONFIG_FILEPATH)
    page = request.args.get('page', 1, type=int)
    start_index = (page - 1) * ROWS_PER_PAGE
    end_index = start_index + ROWS_PER_PAGE
    paginated_data = config_data[start_index:end_index]
    total_pages = math.ceil(len(config_data) / ROWS_PER_PAGE)
    error_message = None

    if request.method == 'POST':
        if request.form.get('action') == 'add':
            new_row = {header: request.form.get(header, '').strip() for header in headers}
            if 'FileName' in new_row and any(row.get('FileName') == new_row['FileName'] for row in config_data):
                error_message = f"File Name '{new_row['FileName']}' already exists."
            else:
                config_data.append(new_row)
                save_config_data(CONFIG_FILEPATH, config_data)
                return redirect(url_for('display_config'))
        elif request.form.get('action') == 'update':
            filename_to_update = request.form.get('update_filename')
            if filename_to_update:
                updated_row = {}
                for header in headers:
                    updated_row[header] = request.form.get(f'update_{header}')

                updated = False
                for i, row in enumerate(config_data):
                    if row.get('FileName') == filename_to_update:
                        config_data[i].update(updated_row)
                        updated = True
                        break
                if updated:
                    save_config_data(CONFIG_FILEPATH, config_data)
                return redirect(url_for('display_config', page=page))
        elif request.form.get('action') == 'delete':
            filename_to_delete = request.form.get('delete_filename')
            config_data = [row for row in config_data if row.get('FileName') != filename_to_delete]
            save_config_data(CONFIG_FILEPATH, config_data)
            return redirect(url_for('display_config', page=page))

    return render_template('config_form.html', config_data=paginated_data, headers=headers, page=page, total_pages=total_pages, error_message=error_message)

@app.route('/database-config')
def database_config():
    return render_template('database_config.html')

if __name__ == '__main__':
    app.run(debug=True)