#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect("instance/certigenius.db")
cursor = conn.cursor()

# Get the list of tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)

# Get the batches
cursor.execute("SELECT id, name, status, total_count, generated_count, sent_count, failed_count, error_message FROM certificate_batches;")
print("\nBatches:")
for row in cursor.fetchall():
    print(row)

# Get the certificates that failed or have any status
cursor.execute("SELECT id, batch_id, participant_id, status, error_message FROM certificates;")
print("\nCertificates:")
for row in cursor.fetchall():
    print(row)

conn.close()
