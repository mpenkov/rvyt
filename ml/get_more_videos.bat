@echo off
python top_20.py > video_ids.txt
for /f %%a in ( video_ids.txt ) do (
    if not exist data\%%a.* (
        python youtube-dl.py --output "data/%%(id)s.%%(ext)s" -- %%a 
        python fetch_entry.py -- %%a -- data\%%a.pickle
    )
)
