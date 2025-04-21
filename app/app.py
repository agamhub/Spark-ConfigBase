from flask import Flask, render_template, request, redirect, url_for, jsonify
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
    filter_value = request.args.get('filter', '').strip()
    filter_column = request.args.get('column', '').strip()
    sort_column = request.args.get('column', '').strip()
    sort_order = request.args.get('order', 'asc')

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
                return redirect(url_for('display_config', page=page, filter=filter_value, column=filter_column))
        elif request.form.get('action') == 'delete':
            filename_to_delete = request.form.get('delete_filename')
            config_data = [row for row in config_data if row.get('FileName') != filename_to_delete]
            save_config_data(CONFIG_FILEPATH, config_data)
            return redirect(url_for('display_config', page=page, filter=filter_value, column=filter_column))

    return render_template(
            'config_form.html',
            config_data=paginated_data,
            headers=headers,
            page=page,
            total_pages=total_pages,
            error_message=error_message,
            filter_criteria=filter_value,
            filter_column=filter_column,
            sort_column=sort_column,
            sort_order=sort_order
        )

@app.route('/database-config')
def database_config():
    return render_template('database_config.html')

@app.route('/chart-data')
def chart_data():
    """Provide paginated data for the dashboard chart."""
    config_data = get_config_data(CONFIG_FILEPATH)
    # Example: Count occurrences of each FileType
    file_type_counts = {}
    flag_counts = {}  # Count occurrences of Flag = 1 for each BatchName
    for row in config_data:
        batch_name = row.get('BatchName', 'Unknown')
        file_type_counts[batch_name] = file_type_counts.get(batch_name, 0) + 1
        if row.get('Flag') == '1':
            flag_counts[batch_name] = flag_counts.get(batch_name, 0) + 1
            
    # Sort and paginate the data
    sorted_file_types = sorted(file_type_counts.items(), key=lambda x: x[1], reverse=True)
    page = int(request.args.get('page', 1))  # Get the page number from the query string
    items_per_page = 10
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    paginated_file_types = sorted_file_types[start_index:end_index]

    # Prepare data for the chart
    chart_data = {
        "labels": [item[0] for item in paginated_file_types],
        "data": [item[1] for item in paginated_file_types],
        "flag_data": [flag_counts.get(item[0], 0) for item in paginated_file_types],  # Add Flag = 1 counts
        "total_pages": math.ceil(len(file_type_counts) / items_per_page)
    }
    return jsonify(chart_data)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True)