from flask import Flask, render_template, request, redirect, url_for, jsonify
from dqcPage import get_paginated_dqc_data, save_dqc_config_data, get_dqc_config_data, get_config_filepath
import csv
import os
import math

app = Flask(__name__)
CONFIG_DIR = '/app/config'
CONFIG_FILE = 'master_job.csv'
CONFIG_FILEPATH = os.path.join(CONFIG_DIR, CONFIG_FILE)
ROWS_PER_PAGE = 10
SCHEMA_DIR = '/app/schema'

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
            sort_order=sort_order,
            max=max,
            min=min
        )

@app.route('/dqc', methods=['GET', 'POST'])
def display_dqc():
    page = request.args.get('page', 1, type=int)
    filter_value = request.args.get('filter', '').strip()
    filter_column = request.args.get('column', '').strip()
    sort_column = request.args.get('column', '').strip()
    sort_order = request.args.get('order', 'asc')

    # Fetch paginated data
    dqc_data = get_paginated_dqc_data(page, filter_value, filter_column, sort_column, sort_order)
    CONFIG_FILEPATH_DQC = get_config_filepath()

    if request.method == 'POST':
        # Fetch the full dataset for modifications
        full_data = get_dqc_config_data(CONFIG_FILEPATH_DQC)

        if request.form.get('action') == 'add':
            # Add a new row to the full dataset
            new_row = {header: request.form.get(header, '').strip() for header in dqc_data["headers"]}
            if ('DqcId' in new_row and 'BatchName' in new_row and
                any(row.get('DqcId') == new_row['DqcId'] and row.get('BatchName') == new_row['BatchName'] for row in full_data)):
                dqc_data["error_message"] = f"DqcId '{new_row['DqcId']}' with BatchName '{new_row['BatchName']}' already exists."
            else:
                full_data.append(new_row)
                save_dqc_config_data(CONFIG_FILEPATH_DQC, full_data)  # Save the full dataset
                return redirect(url_for('display_dqc'))

        elif request.form.get('action') == 'update':
            # Update an existing row in the full dataset
            dqc_id_to_update = request.form.get('update_DqcId')
            batch_name_to_update = request.form.get('update_BatchName')
            if dqc_id_to_update and batch_name_to_update:
                updated_row = {}
                for header in dqc_data["headers"]:
                    updated_row[header] = request.form.get(f'update_{header}')

                updated = False
                for i, row in enumerate(full_data):
                    if row.get('DqcId') == dqc_id_to_update and row.get('BatchName') == batch_name_to_update:
                        full_data[i].update(updated_row)
                        updated = True
                        break
                if updated:
                    save_dqc_config_data(CONFIG_FILEPATH_DQC, full_data)  # Save the full dataset
                return redirect(url_for('display_dqc', page=page, filter=filter_value, column=filter_column))

        elif request.form.get('action') == 'delete':
            # Delete a row from the full dataset
            dqc_id_to_delete = request.form.get('delete_DqcId')
            batch_name_to_delete = request.form.get('delete_BatchName')
            if dqc_id_to_delete and batch_name_to_delete:
                full_data = [
                    row for row in full_data
                    if not (row.get('DqcId') == dqc_id_to_delete and row.get('BatchName') == batch_name_to_delete)
                ]
                save_dqc_config_data(CONFIG_FILEPATH_DQC, full_data)  # Save the full dataset
                return redirect(url_for('display_dqc'))

    return render_template(
        'dqc_config.html',
        config_data=dqc_data["paginated_data"],
        headers=dqc_data["headers"],
        page=page,
        total_pages=dqc_data["total_pages"],
        error_message=dqc_data["error_message"],
        filter_criteria=filter_value,
        filter_column=filter_column,
        sort_column=sort_column,
        sort_order=sort_order,
        max=max,
        min=min
    )

@app.route('/chart-data')
def chart_data():
    """Provide paginated data for the dashboard chart."""
    config_data = get_config_data(CONFIG_FILEPATH)

    # Load data from DataQuality_Config.csv
    CONFIG_FILEPATH_DQC = get_config_filepath()  # Get the file path for DataQuality_Config.csv
    dqc_data = get_dqc_config_data(CONFIG_FILEPATH_DQC)

    # Example: Count occurrences of each FileType
    file_type_counts = {}
    flag_counts = {}  # Count occurrences of Flag = 1 for each BatchName
    for row in config_data:
        batch_name = row.get('BatchName', 'Unknown')
        file_type_counts[batch_name] = file_type_counts.get(batch_name, 0) + 1
        if row.get('Flag') == '1':
            flag_counts[batch_name] = flag_counts.get(batch_name, 0) + 1
            
    # Count total BatchName occurrences in DataQuality_Config.csv
    dqc_batch_counts = {}
    for row in dqc_data:
        batch_name = row.get('BatchName', 'Unknown')
        dqc_batch_counts[batch_name] = dqc_batch_counts.get(batch_name, 0) + 1

    # Combine data for the stacked bar chart
    combined_batch_names = set(file_type_counts.keys()).union(dqc_batch_counts.keys())
    combined_data = []
    for batch_name in combined_batch_names:
        combined_data.append({
            "batch_name": batch_name,
            "master_job_count": file_type_counts.get(batch_name, 0),
            "dqc_count": dqc_batch_counts.get(batch_name, 0),
            "flag_count": flag_counts.get(batch_name, 0)
        })

    # Sort and paginate the data
    sorted_combined_data = sorted(combined_data, key=lambda x: x["master_job_count"], reverse=True)
    page = int(request.args.get('page', 1))  # Get the page number from the query string
    items_per_page = 10
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    paginated_combined_data = sorted_combined_data[start_index:end_index]

    # Prepare data for the chart
    chart_data = {
        "labels": [item["batch_name"] for item in paginated_combined_data],
        "master_job_data": [item["master_job_count"] for item in paginated_combined_data],
        "dqc_data": [item["dqc_count"] for item in paginated_combined_data],
        "flag_data": [item["flag_count"] for item in paginated_combined_data],  # Add Flag = 1 counts
        "total_pages": math.ceil(len(combined_data) / items_per_page)
    }
    return jsonify(chart_data)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/record-counts')
def record_counts():
    """Fetch total record counts from master_job.csv and DataQuality_Config.csv."""
    # Load data from master_job.csv
    master_job_data = get_config_data(CONFIG_FILEPATH)
    master_job_count = len(master_job_data)

    # Load data from DataQuality_Config.csv
    dqc_data = get_dqc_config_data(get_config_filepath())
    dqc_count = len(dqc_data)

    #schema load
    schema_files = [f for f in os.listdir(SCHEMA_DIR) if f.endswith('.csv')]
    schema_count = len(schema_files)

    # Return the counts as JSON
    return jsonify({
        "master_job_count": master_job_count,
        "dqc_count": dqc_count,
        "schema_count": schema_count
    })

@app.route('/application-stacks')
def appstacks():
    return render_template('appstacks.html')

@app.route('/schema', methods=['GET'])
def schema():
    """Display the list of schema files with pagination and search."""
    search_query = request.args.get('search', '').lower()  # Get the search query
    page = int(request.args.get('page', 1))  # Get the current page number
    per_page = 15  # Default number of items per page

    try:
        # Get all schema files
        all_files = [f for f in os.listdir(SCHEMA_DIR) if f.endswith('.csv')]

        # Filter files based on the search query
        if search_query:
            filtered_files = [f for f in all_files if search_query in f.lower()]
        else:
            filtered_files = all_files

        # Paginate the filtered files
        total_files = len(filtered_files)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_files = filtered_files[start:end]

        # Calculate total pages
        total_pages = (total_files + per_page - 1) // per_page

        # Calculate the pagination range (limit to 5 pages at a time)
        start_page = max(1, page - 2)
        end_page = min(total_pages, start_page + 4)
        pagination_range = range(start_page, end_page + 1)
    except FileNotFoundError:
        paginated_files = []
        total_pages = 0
        pagination_range = range(0)

    return render_template(
        'schema.html',
        files=paginated_files,
        selected_file=None,
        headers=None,
        rows=None,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        pagination_range=pagination_range
    )

@app.route('/schema/<filename>', methods=['GET', 'POST'])
def schema_file(filename):
    """Display and modify the content of a selected schema file."""
    filepath = os.path.join(SCHEMA_DIR, filename)
    if not os.path.exists(filepath):
        return f"File {filename} not found.", 404

    try:
        # Read the CSV file with the correct delimiter
        with open(filepath, 'r', newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter='|')  # Use '|' as the delimiter
            headers = next(reader, [])  # Get the header row
            rows = [row for row in reader]  # Keep rows as lists for easier manipulation
    except Exception as e:
        return f"Error reading file {filename}: {e}", 500

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            # Add a new row
            new_row = [request.form.get(header, '') for header in headers]
            rows.append(new_row)
        elif action == 'edit':
            # Edit an existing row
            row_index = int(request.form.get('row_index'))
            rows[row_index] = [request.form.get(header, '') for header in headers]

        # Save the updated rows back to the CSV file
        try:
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter='|')  # Use '|' as the delimiter
                writer.writerow(headers)  # Write the header row
                writer.writerows(rows)  # Write all rows
        except Exception as e:
            return f"Error writing to file {filename}: {e}", 500

        return redirect(url_for('schema_file', filename=filename))

    # Pagination logic for the list of schema files
    search_query = request.args.get('search', '').lower()
    page = int(request.args.get('page', 1))
    per_page = 15

    try:
        all_files = [f for f in os.listdir(SCHEMA_DIR) if f.endswith('.csv')]
        if search_query:
            filtered_files = [f for f in all_files if search_query in f.lower()]
        else:
            filtered_files = all_files

        total_files = len(filtered_files)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_files = filtered_files[start:end]

        total_pages = (total_files + per_page - 1) // per_page
        start_page = max(1, page - 2)
        end_page = min(total_pages, start_page + 4)
        pagination_range = range(start_page, end_page + 1)
    except FileNotFoundError:
        paginated_files = []
        total_pages = 0
        pagination_range = range(0)

    # Render the rows with headers and split data
    parsed_rows = [{"ColumnName": row[0], "DataType": row[1]} for row in rows if len(row) >= 2]

    return render_template(
        'schema.html',
        files=paginated_files,
        selected_file=filename,
        headers=headers,
        rows=parsed_rows,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        pagination_range=pagination_range
    )

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    if file:
        filepath = os.path.join(SCHEMA_DIR, file.filename)
        file.save(filepath)

        # Reuse the logic from the `schema` route to pass the required context
        search_query = request.args.get('search', '').lower()
        page = int(request.args.get('page', 1))
        per_page = 15

        try:
            all_files = [f for f in os.listdir(SCHEMA_DIR) if f.endswith('.csv')]
            if search_query:
                filtered_files = [f for f in all_files if search_query in f.lower()]
            else:
                filtered_files = all_files

            total_files = len(filtered_files)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_files = filtered_files[start:end]

            total_pages = (total_files + per_page - 1) // per_page
            start_page = max(1, page - 2)
            end_page = min(total_pages, start_page + 4)
            pagination_range = range(start_page, end_page + 1)
        except FileNotFoundError:
            paginated_files = []
            total_pages = 0
            pagination_range = range(0)

        return render_template(
            'schema.html',
            files=paginated_files,
            selected_file=None,
            headers=None,
            rows=None,
            search_query=search_query,
            page=page,
            total_pages=total_pages,
            pagination_range=pagination_range,
            success_message="File has been uploaded successfully!"
        )

if __name__ == '__main__':
    app.run(debug=True)