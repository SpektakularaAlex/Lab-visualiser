Duoplasmatron SQLite logging

Logging is automatic when S1.py or S2.py is started.

Log folder:
/home/s1s2/Documents/duoplasmatron_logs

Monthly database files:
S1_YYYY_MM.db
S2_YYYY_MM.db

Inspect example:
cd /home/s1s2/Documents
python3 duo_sqlite_logger.py --inspect --db /home/s1s2/Documents/duoplasmatron_logs/S2_2026_08.db

Emergency disable for one run:
DUO_LOG_DISABLE=1 python3 S2.py

To disable persistently:
rename duo_logging_config.json to duo_logging_config.disabled

The logger is read-only with respect to the source. It only records existing last_names, last_ctrl, last_ret, item status, and timing values.