import os
import datetime
import subprocess
import logging
from typing import Dict

class BackupManager:
    def __init__(self):
        self.config = {
            "backup_dir": "/var/backups/revenue",
            "retention_days": 30,
            "pg_dump_path": "/usr/bin/pg_dump",
            "db_name": "revenue_db",
            "db_user": "user",
            "db_host": "localhost"
        }

    def create_backup(self) -> Dict[str, Any]:
        """Create database backup."""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(
                self.config["backup_dir"],
                f"revenue_{timestamp}.sql"
            )

            os.makedirs(self.config["backup_dir"], exist_ok=True)

            command = [
                self.config["pg_dump_path"],
                "-h", self.config["db_host"],
                "-U", self.config["db_user"],
                "-F", "c",
                "-b",
                "-v",
                "-f", backup_file,
                self.config["db_name"]
            ]

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={"PGPASSWORD": "password"}
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                raise Exception(f"Backup failed: {stderr.decode()}")

            return {
                "success": True,
                "file": backup_file,
                "size": os.path.getsize(backup_file)
            }
        except Exception as e:
            logging.error(f"Backup failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def cleanup_old_backups(self):
        """Remove backups older than retention period."""
        try:
            cutoff = datetime.datetime.now() - datetime.timedelta(
                days=self.config["retention_days"]
            )

            for filename in os.listdir(self.config["backup_dir"]):
                file_path = os.path.join(self.config["backup_dir"], filename)
                file_time = datetime.datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                )
                if file_time < cutoff:
                    os.remove(file_path)
                    logging.info(f"Removed old backup: {filename}")
        except Exception as e:
            logging.error(f"Failed to clean up old backups: {str(e)}")
