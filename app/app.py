from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, stream_with_context, flash
from dqcPage import get_paginated_dqc_data, save_dqc_config_data, get_dqc_config_data, get_config_filepath
from sparklogs import get_log_statuses
from sparkdb import get_data
import csv
import os
import math
import time

app = Flask(__name__)

app.secret_key = os.urandom(24) # Replace with a strong, static key in production

# CONFIG_DIR = 'E:/Repo/Spark-ConfigBase/app/config'
CONFIG_DIR = '/app/config'
CONFIG_FILE = 'master_job.csv'
CONFIG_FILEPATH = os.path.join(CONFIG_DIR, CONFIG_FILE)
ROWS_PER_PAGE = 10
SCHEMA_DIR = '/app/schema'
STORED_PROCEDURES_DIR = '/app/SP'
LOGS_DIR = "/app/logs"

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
    
def get_config_data_unique(filepath):
    """Reads all config data from the CSV file."""
    config_data = []
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
            # Use DictReader for easier data manipulation
            reader = csv.DictReader(csvfile, delimiter='|', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            # Add a unique row index to each dictionary
            for i, row in enumerate(reader):
                row['_row_index'] = i # Add index for identification
                config_data.append(row)
            return config_data
    except FileNotFoundError:
         print(f"Warning: File not found at {filepath}. Returning empty data.")
         # Optionally create the file with headers if it doesn't exist
         # headers = ['BatchName', 'JobName', 'SourceDirectory', 'FileName', 'FileType', 'Flag', 'Delimiter', 'Backdated', 'Refreshment', 'Reformat']
         # save_config_data(filepath, [], headers) # Save empty file with headers
         return []
    except Exception as e:
        print(f"Error reading config data from CSV ({filepath}): {e}")
        return []
    
def save_config_data_unique(filepath, data, fieldnames):
    """Writes config data to the CSV file."""
    if not fieldnames:
        print("Error: Cannot save CSV without fieldnames (headers).")
        return
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            # Ensure '_row_index' is not written to the file if it exists
            writer_fieldnames = [h for h in fieldnames if h != '_row_index']
            writer = csv.DictWriter(csvfile, fieldnames=writer_fieldnames, delimiter='|', quotechar='"', quoting=csv.QUOTE_MINIMAL, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
        print(f"Successfully saved data to {filepath}")
    except Exception as e:
        print(f"Error writing CSV ({filepath}): {e}")

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

@app.route('/welcome')
def index():
    """Basic index route."""
    return "Welcome! Go to /bulk_update to edit the CSV."

@app.route('/bulk_update', methods=['GET', 'POST'])
def bulk_update():
    """Route to display and handle bulk updates, now with filtering."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILEPATH):
        default_headers = ['BatchName', 'JobName', 'SourceDirectory', 'FileName', 'FileType', 'Flag', 'Delimiter', 'Backdated',
                           'Refreshment', 'Reformat']
        print(f"CSV file not found at {CONFIG_FILEPATH}. Creating it with headers.")
        save_config_data_unique(CONFIG_FILEPATH, [], default_headers)

    headers = get_headers_from_csv(CONFIG_FILEPATH)
    all_data = get_config_data_unique(CONFIG_FILEPATH)
    PAGINATION_RANGE = 5

    if request.method == 'POST':
        try:
            filter_column = request.form.get('filter_column')
            filter_value = request.form.get('filter_value')
            column_to_update = request.form.get('column_name')
            new_value = request.form.get('new_value')

            if not filter_column or not filter_value:
                flash('Error: Filter column and value are required.', 'error')
                return redirect(url_for('bulk_update'))

            if not column_to_update or column_to_update not in headers:
                flash(f'Error: Invalid or missing column name "{column_to_update}".', 'error')
                return redirect(url_for('bulk_update'))

            if new_value is None:
                flash('Error: New value cannot be missing.', 'error')
                return redirect(url_for('bulk_update'))

            updated_count = 0
            for row in all_data:
                if row.get(filter_column) == filter_value:
                    if column_to_update in row:
                        row[column_to_update] = new_value
                        updated_count += 1
                    else:
                        print(
                            f"Warning: Column '{column_to_update}' not found in row, though it's in headers.")

            if updated_count > 0:
                save_config_data_unique(CONFIG_FILEPATH, all_data, headers)
                flash(f'Successfully updated {updated_count} rows in column "{column_to_update}".', 'success')
            else:
                flash('No rows matched the filter criteria for update.', 'warning')

        except Exception as e:
            flash(f'An error occurred during update: {e}', 'error')
            print(f"Error during POST processing: {e}")

        return redirect(url_for('bulk_update'))

    page = request.args.get('page', 1, type=int)
    start_index = (page - 1) * ROWS_PER_PAGE
    end_index = start_index + ROWS_PER_PAGE
    data = all_data[start_index:end_index]

    total_rows = len(all_data)
    total_pages = (total_rows + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
    start_page = max(1, page - PAGINATION_RANGE // 2)
    end_page = min(total_pages, start_page + PAGINATION_RANGE - 1)

    return render_template('bulk_update.html', headers=headers, data=data,
                           current_page=page, total_pages=total_pages,
                           pages_range=range(start_page, end_page + 1),
                           config_filepath=CONFIG_FILEPATH)

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
        if action == 'delete':
                row_index = int(request.form.get('row_index'))
                rows.pop(row_index)  # Remove the row at the specified index
        elif action == 'edit':
            # Edit an existing row
            row_index = int(request.form.get('row_index'))
            rows[row_index] = [request.form.get(header, '') for header in headers]
        elif action == 'add':
            # Add a new row
            new_row = [request.form.get(header, '') for header in headers]
            rows.append(new_row)

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
    
@app.route('/delete-file', methods=['POST'])
def delete_file():
    """Delete a schema file."""
    filename = request.form.get('filename')
    if not filename:
        return "No file specified", 400

    filepath = os.path.join(SCHEMA_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return redirect(url_for('schema'))
    else:
        return f"File {filename} not found.", 404

@app.route('/stored-procedures', methods=['GET'])
def stored_procedures():
    """Display the list of stored procedures with pagination and search."""
    search_query = request.args.get('search', '').lower()  # Get the search query
    page = int(request.args.get('page', 1))  # Get the current page number
    per_page = 10  # Default number of items per page

    try:
        # Get all stored procedure files
        all_files = [f for f in os.listdir(STORED_PROCEDURES_DIR) if f.endswith('.sql')]

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
        'stored_procedure.html',
        files=paginated_files,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        pagination_range=pagination_range
    )

@app.route('/stored-procedure/<filename>', methods=['GET', 'POST'])
def stored_procedure_view(filename):
    """Display and edit the content of a stored procedure file."""
    filepath = os.path.join(STORED_PROCEDURES_DIR, filename)
    if not os.path.exists(filepath):
        return f"File {filename} not found.", 404

    if request.method == 'POST':
        # Save the updated content back to the file
        updated_content = request.form.get('content')
        try:
            with open(filepath, 'w') as file:
                file.write(updated_content)
            return redirect(url_for('stored_procedures'))
        except Exception as e:
            return f"Error saving file {filename}: {e}", 500

    try:
        # Read the content of the file
        with open(filepath, 'r') as file:
            content = file.read()
    except Exception as e:
        return f"Error reading file {filename}: {e}", 500

    return render_template('stored_procedure_edit.html', filename=filename, content=content)

@app.route('/delete-stored-procedure', methods=['POST'])
def delete_stored_procedure():
    """Delete a stored procedure file."""
    filename = request.form.get('filename')
    if not filename:
        return "No file specified", 400

    filepath = os.path.join(STORED_PROCEDURES_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return redirect(url_for('stored_procedures'))
    else:
        return f"File {filename} not found.", 404
    
@app.route('/delete-multiple-stored-procedures', methods=['POST'])
def delete_multiple_stored_procedures():
    """Delete multiple stored procedure files."""
    selected_files = request.form.getlist('selected_files')
    if not selected_files:
        return "No files selected", 400

    for filename in selected_files:
        filepath = os.path.join(STORED_PROCEDURES_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    return redirect(url_for('stored_procedures'))
    
@app.route('/upload-stored-procedure', methods=['POST'])
def upload_stored_procedure():
    """Upload a new stored procedure file."""
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    if file and file.filename.endswith('.sql'):
        filepath = os.path.join(STORED_PROCEDURES_DIR, file.filename)
        file.save(filepath)
        return redirect(url_for('stored_procedures'))
    else:
        return "Invalid file type. Only .sql files are allowed.", 400
    
@app.route('/logs', methods=['GET'])
def logs():
    """Display the log file statuses."""
    logs = get_log_statuses()
    return render_template('logs.html', logs=logs)

@app.route('/logs/preview/<filename>', methods=['GET'])
def preview_log(filename):
    """Open and display the content of a log file."""
    filepath = os.path.join(LOGS_DIR, filename)
    if not os.path.exists(filepath):
        return f"Log file {filename} not found.", 404

    try:
        with open(filepath, "r") as file:
            content = file.read()
        return render_template('log_preview.html', filename=filename, content=content)
    except Exception as e:
        return f"Error reading log file {filename}: {e}", 500

@app.route('/spark', methods=['GET'])
def spark():
    """API endpoint to fetch data from the database."""
    try:
        batchdate = request.args.get('batchdate')
        data = get_data(batchdate)
        return render_template('dashboard.html', spark=data, batchdate=batchdate or "")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True)