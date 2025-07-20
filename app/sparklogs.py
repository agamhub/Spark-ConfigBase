import os
from datetime import datetime

LOGS_DIR = "/app/logs"  # Replace with the actual path to your logs directory

def get_log_statuses():
    """Get the status and modification date of log files."""
    logs = []
    try:
        # Get all log files with their modification times
        log_files = [
            {
                "filename": f,
                "modified_time": os.path.getmtime(os.path.join(LOGS_DIR, f)),
                "status": "Not Started"  # Default status
            }
            for f in os.listdir(LOGS_DIR) if f.endswith(".log")
        ]

        # Sort log files by modification time (latest first)
        log_files.sort(key=lambda x: x["modified_time"], reverse=True)

        # Determine the status of each log file
        for log in log_files:
            filepath = os.path.join(LOGS_DIR, log["filename"])
            with open(filepath, "r") as file:
                lines = file.readlines()
                # Check for specific keywords to determine the status
                for line in reversed(lines):  # Read from the end for efficiency
                    if "RUNNING" in line.upper():
                        log["status"] = "Running"
                        break
                    elif "COMPLETED" in line.upper():
                        log["status"] = "Completed"
                        break
                    elif "ERROR" in line.upper() or "FAILED" in line.upper():
                        log["status"] = "Error"
                        break
            # Format the modification time for display
            log["modified_time"] = datetime.fromtimestamp(log["modified_time"]).strftime("%Y-%m-%d %H:%M:%S")
            logs.append(log)
    except Exception as e:
        print(f"Error reading logs: {e}")
    return logs