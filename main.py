import os
import csv
import time
import subprocess
import shutil
import requests
import re
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"

API_KEY = os.getenv("API_KEY", "None")
BAZARR_URL = os.getenv("BAZARR_URL", "http://localhost:6767")
SUBCLEANER = os.getenv("SUBCLEANER", "false").lower() == "true"
SLEEP = os.getenv("SLEEP", "300")
WINDOW_SIZE = os.getenv("WINDOW_SIZE", "1800")

def run_command(command, sub_file):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    raw_output = process.communicate()
    
    output = raw_output[0].decode('utf-8')
    
    filename = extract_filename(sub_file)
    
    # Remove the filename from the output
    cleaned_output = output.replace(sub_file, '').replace(filename, '')
    output = output.replace("/dev/shm/tmp.srt", sub_file)
    
    if "can't open multimedia file: No such file or directory" in cleaned_output:
        return output, 'extension'
    
    if "Select reference language first" in cleaned_output:
        return output, True

    return output, False

def log_output(sub_file, command, output, reason):
    if 'subsync' in command:
        log_folder = '/subsync-bazarr/logs/subsync'
    elif 'subcleaner' in command:
        log_folder = '/subsync-bazarr/logs/subcleaner'
    else:
        log_folder = '/subsync-bazarr/logs'
        
    timestamp = datetime.now().strftime('%Y-%m-%d %H.%M.%S')
        
    os.makedirs(log_folder, exist_ok=True)
    cleaned_sub_file = re.sub(r'[\\/*?:"<>|]', " - ", sub_file)
    filename = f"{timestamp}{cleaned_sub_file}.log"
    log_path = os.path.join(log_folder, filename)
    
    with open(log_path, 'w', encoding="utf-8") as log_file:
        log_file.write(f"Command: {command}\n\n")
        if reason:
            log_file.write(f"Error: {reason}\n\n")
        log_file.write("Output:\n")
        log_file.write(output)
        
    time.sleep(0.1)
    
def srt_lang_detect(command, sub_file):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    raw_output = process.communicate()
    output = raw_output[0].decode('utf-8')
    
    filename = extract_filename(sub_file)
    
    cleaned_output = output.replace(sub_file, '').replace(filename, '')
    
    if "Would rename" in cleaned_output:
        return False
    else:
        return True

def replace_language_code(file_path, match):
    base, ext = os.path.splitext(file_path)
    new_base = re.sub(r'\.([a-z]{2})(\.(hi|cc|sdh))?$', '', base)
    
    if not match:
        en_path = f"{new_base}.en{ext}"
        en_hi_path = f"{new_base}.en.hi{ext}"
        en_cc_path = f"{new_base}.en.cc{ext}"
        en_sdh_path = f"{new_base}.en.sdh{ext}"
        
        if os.path.exists(en_path):
            return en_path
        elif os.path.exists(en_hi_path):
            return en_hi_path
        elif os.path.exists(en_cc_path):
            return en_cc_path
        elif os.path.exists(en_sdh_path):
            return en_sdh_path
        else:
            return None
    
    if match:
        directory = os.path.dirname(file_path)
        
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")
        all_files = os.listdir(directory)
        
        pattern = re.compile(f"^{re.escape(os.path.basename(new_base))}\.([a-z]{{2}})(\.(hi|cc|sdh))?{re.escape(ext)}$")
        
        non_english_subs = []
        for file in all_files:
            match = pattern.match(file)
            if match and match.group(1) != 'en':
                non_english_subs.append(os.path.join(directory, file))
                
        return non_english_subs
    
def extract_filename(sub_file):
    filename = os.path.basename(sub_file)
    filename = os.path.splitext(filename)[0]
    
    filename = re.sub(r'\.([a-z]{2})(\.(hi|cc|sdh))?$', '', filename)
    
    return filename
    
def create_csv_file(csv_file):
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'episode', 'subtitles', 'subtitle_language_code2', 'subtitle_language_code3', 'episode_language_code3', 'subtitle_id', 'provider', 'series_id', 'episode_id'])
    
def create_retry_file(retry_file):
    os.makedirs(os.path.dirname(retry_file), exist_ok=True)
    with open(retry_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'episode', 'subtitles', 'subtitle_language_code2', 'subtitle_language_code3', 'episode_language_code3', 'subtitle_id', 'provider', 'series_id', 'episode_id'])

def has_error(output, sub_file):
    filename = extract_filename(sub_file)
    
    cleaned_output = output.replace(sub_file, '').replace(filename, '')
    
    if "couldn't synchronize!" in cleaned_output:
        if "progress 100%, 0 points" in cleaned_output:
            return 'nosync'
        return True
    elif "recognition model is missing" in cleaned_output:
        return 'nosync', 'missmodel'
    else:
        return None
    
def add_to_failed_list(sub_file):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data = f"{timestamp}: {sub_file}\n"

    try:
        with open(failed_file, 'a', encoding='utf-8') as f:
            f.write(data)
            
        time.sleep(0.1)
    except Exception as e:
        print(f"\u2022ERROR: {str(e)}")
    
def add_to_csv_list(csv_file, reference_file, sub_file, sub_code2, sub_code3, ep_code3, sub_id, provider, series_id, episode_id):
    data = [
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        reference_file,
        sub_file,
        sub_code2,
        sub_code3,
        ep_code3,
        sub_id,
        provider,
        series_id,
        episode_id
    ]

    try:
        if not os.path.isfile(csv_file):
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'episode', 'subtitles', 'subtitle_language_code2', 'subtitle_language_code3', 'episode_language_code3', 'subtitle_id', 'provider', 'series_id', 'episode_id'])

        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(data)
            
        time.sleep(0.1)
    except Exception as e:
        print(f"\u2022ERROR: {str(e)}")

def add_to_retry_list(retry_file, reference_file, sub_file, sub_code2, sub_code3, ep_code3, sub_id, provider, series_id, episode_id):
    data = [
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        reference_file,
        sub_file,
        sub_code2,
        sub_code3,
        ep_code3,
        sub_id,
        provider,
        series_id,
        episode_id
    ]

    try:
        if not os.path.isfile(retry_file):
            with open(retry_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'episode', 'subtitles', 'subtitle_language_code2', 'subtitle_language_code3', 'episode_language_code3', 'subtitle_id', 'provider', 'series_id', 'episode_id'])

        with open(retry_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(data)
            
        time.sleep(0.1)
    except Exception as e:
        print(f"\u2022ERROR: {str(e)}")

def blacklist_subtitle(is_movie, series_id, episode_id, provider, sub_id, sub_code2, sub_file):
    if is_movie:
        url = f"{BAZARR_URL}/api/movies/blacklist?radarrid={episode_id}"
    else:
        url = f"{BAZARR_URL}/api/episodes/blacklist?seriesid={series_id}&episodeid={episode_id}"
    
    headers = {
        "X-API-KEY": f"{API_KEY}",
        "Content-Type": "application/json"
        }
    payload = {
        "provider": provider,
        "subs_id": sub_id,
        "language": sub_code2,
        "subtitles_path": sub_file
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [404, 500]:
            return 'remove'
        if response.status_code not in [204]:
            response.raise_for_status()
            
        time.sleep(5)
        return True
    except requests.RequestException as e:
        print(f"\u2022ERROR, API-request failed: {str(e)}")
        return False

def download_new_subtitle(is_movie, series_id, episode_id, sub_code2):
    if is_movie:
        url = f"{BAZARR_URL}/api/movies/subtitles?radarrid={episode_id}"
    else:
        url = f"{BAZARR_URL}/api/episodes/subtitles?seriesid={series_id}&episodeid={episode_id}"
    
    payload = {
        "language": sub_code2,
        "forced": False,
        "hi": False
    }
    
    headers = {
        "X-API-KEY": f"{API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.patch(url, json=payload, headers=headers)
        if response.status_code not in [200]:
            response.raise_for_status()
            
        time.sleep(5)
        return True
    except requests.RequestException as e:
        print(f"\u2022ERROR, API-request failed: {str(e)}")
        return False
                
def find_non_english_counterpart(csv_file, original_subtitle, move_to_failed):
    original_subtitle = [None] + original_subtitle
    
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        subtitles = list(reader)
                 
    if move_to_failed == 'doprocess':
        non_english_subs = replace_language_code(original_subtitle[2], True)
        if non_english_subs:
            index = 0
            message = True
            
            while index < len(non_english_subs):
                non_english_sub = non_english_subs[index]
                if not [sub for sub in subtitles[1:] if sub[2] == non_english_sub]:
                    if message:
                        print("Looking for non-English subtitles to redownload...")
                        message = False
                        
                    match = re.search(r'\.([a-z]{2})(\.(hi|cc|sdh))?\.', non_english_sub)
                    if match:
                        sub_code2 = match.group(1)
                        print(f"Found match: \"{sub_code2}\", requesting redownload...")
                        download_new_subtitle(original_subtitle[8] == "", original_subtitle[8], original_subtitle[9], sub_code2)
                        time.sleep(1)
                    non_english_subs.pop(index)
                else:
                    index += 1
    else:  
        for subtitle in subtitles[1:]:
            if subtitle[1] == original_subtitle[1]:
                while True:
                    non_english_subs = [sub for sub in subtitles[1:] if sub[1] == subtitle[1] and sub[2] != original_subtitle[2]]
                    
                    if not non_english_subs:
                        break
                    
                    for non_english_sub in non_english_subs:
                        remove_from_list(csv_file, non_english_sub[6])
                        
                        if move_to_failed:
                            lang_command = f"/usr/bin/python3 -u /opt/srt-lang-detect/srtlangdetect.py \"{non_english_sub[2]}\""
                            if srt_lang_detect(lang_command, non_english_sub[2]):
                                if SUBCLEANER:
                                    print(f"Running subcleaner for \"{non_english_sub[3]}\"-subtitle...")
                                    subcleaner_command = f"/usr/bin/python3 -u /opt/subcleaner/subcleaner.py --language \"{non_english_sub[3]}\" \"{non_english_sub[2]}\""
                                    output, fail = run_command(subcleaner_command, non_english_sub[2])
                                    log_output(non_english_sub[2], subcleaner_command, output, False)
                            
                                add_to_failed_list(non_english_sub[2])
                                time.sleep(0.5)
                            
                                print(f"Removed \"{non_english_sub[3]}\"-subtitle from list and added it to failed.txt!")
                        
                            else:
                                print(f"ERROR: Wrong language detected in \"{non_english_sub[3]}\"-subtitle...")
                                is_movie = non_english_sub[8] == ""
                                blacklist_result = blacklist_subtitle(is_movie, non_english_sub[8], non_english_sub[9], non_english_sub[7], non_english_sub[6], non_english_sub[3], non_english_sub[2])
                                if blacklist_result == True:
                                    print("Successfully blacklisted subtitle, requesting new subtitle!\n")
                                    remove_from_list(csv_file, non_english_sub[6])
                                    find_non_english_counterpart(csv_file, non_english_sub[1:10], False)
                                elif blacklist_result == 'remove':
                                    print("Subtitle not found, removing from list...\n")
                                    remove_from_list(csv_file, non_english_sub[6])
                                else:
                                    print("ERROR: Failed to blacklist subtitle...")
                                    add_to_retry_list(retry_file, non_english_sub[1], non_english_sub[2], non_english_sub[3], non_english_sub[4], non_english_sub[5], non_english_sub[6], non_english_sub[7], non_english_sub[8], non_english_sub[9])
                                    remove_from_list(csv_file, non_english_sub[6])
                                    
                                    print("Moving subtitle entry to logs/retry.csv!\n")                                
                        elif move_to_failed == 'retry':
                            add_to_retry_list(retry_file, *non_english_sub[1:10])
                            print(f"Moved \"{non_english_sub[3]}\"-subtitle entry to logs/retry.csv!")
                        else:
                            add_to_csv_list(csv_file, *non_english_sub[1:10])
                            
                        subtitles.remove(non_english_sub)
                    
    if move_to_failed == True:
        data = "\n"
        try:
            with open(failed_file, 'a', encoding='utf-8') as f:
                f.write(data)
                
            time.sleep(0.1)
        except Exception as e:
            print(f"\u2022ERROR: {str(e)}")
        time.sleep(0.5)

def remove_from_list(csv_file, sub_id):
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        subtitles = list(reader)
    
    header = subtitles[0]
    subtitles = [sub for sub in subtitles[1:] if sub[6] != sub_id]

    with open(csv_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(subtitles)
        
    time.sleep(0.5)
    
def remove_from_retry_list(retry_file, sub_id):
    with open(retry_file, 'r') as file:
        reader = csv.reader(file)
        retry_list = list(reader)
        
    header = retry_list[0]
    retry_list = [sub for sub in retry_list[1:] if sub[6] != sub_id]

    with open(retry_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(retry_list)
        
    time.sleep(0.5)
    
def process_subtitles(csv_file, retry_file):
    processed_count = 0 
    
    while True:
        with open(csv_file, 'r') as file:
            reader = csv.reader(file)
            next(reader)
            subtitles = list(reader)
            
        if not subtitles:  
            while True:  
                with open(retry_file, 'r') as file:
                    reader = csv.reader(file)
                    next(reader) 
                    retry_list = list(reader)
                    
                if not retry_list:
                    break
                
                print()
                
                subtitle = retry_list[0]
                             
                current_count = len(retry_list)
                processed_count += 1
                
                english_sub_path = replace_language_code(subtitle[2], False)
                english_subtitle = next((sub for sub in retry_list if sub[2] == english_sub_path), None)
                
                if subtitle[3] != 'en':
                    if english_subtitle:
                         subtitle[1:10] = english_subtitle[1:10]
                
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] Processed: {processed_count}, Remaining: {current_count}")
                time.sleep(0.1)
                print(f"Processing subtitle: {subtitle[2]}")
                time.sleep(0.1)
                
                blacklist_result = blacklist_subtitle(subtitle[8] == "", subtitle[8], subtitle[9], subtitle[7], subtitle[6], subtitle[3], subtitle[2])
                if blacklist_result == True:
                    print("Successfully blacklisted subtitle, requesting new subtitle!")
                    
                    remove_from_retry_list(retry_file, subtitle[6])
                    
                    non_english_subs = [sub for sub in retry_list if sub[1] == subtitle[1] and sub[3] != 'en']
                    for non_english_sub in non_english_subs:
                        remove_from_retry_list(retry_file, non_english_sub[6])
                        print(f"Moving \"{non_english_sub[3]}\"-subtitle entry back to unsynced.csv!")
                        with open(csv_file, 'a', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow(non_english_sub)
                    print()
                        
                elif blacklist_result == 'remove':
                    print("Subtitle not found, removing from logs/retry.csv...")
                    remove_from_retry_list(retry_file, subtitle[6])
                    non_english_subs = [sub for sub in retry_list if sub[1] == subtitle[1] and sub[3] != 'en']
                    for non_english_sub in non_english_subs:
                        remove_from_retry_list(retry_file, non_english_sub[6])
                        print(f"Removing \"{non_english_sub[3]}\"-subtitle from logs/retry.csv...")
                    print()
                else:
                    print("ERROR: Failed to blacklist subtitle, keeping in logs/retry.csv...\n")
                    
                time.sleep(0.1)
            
            with open(csv_file, 'r') as file:
                reader = csv.reader(file)
                header = next(reader) 
                subtitles = list(reader)
                
            if not subtitles:
                break
        print()    
        
        current_count = len(subtitles)
        
        subtitle = subtitles[0] 
        reference_file, sub_file, sub_code2, sub_code3, ep_code3, sub_id, provider, series_id, episode_id = subtitle[1:10]
        is_movie = series_id == "" 
        
        english_sub_path = replace_language_code(sub_file, False)
        english_subtitle = next((sub for sub in subtitles if sub[2] == english_sub_path), None)
        
        time.sleep(1)
        processed_count += 1
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] Processed: {processed_count}, Remaining: {current_count}")
        time.sleep(0.1)

        if sub_code2 != 'en':
            if english_subtitle:
                process_subtitle(english_subtitle[8] == "", english_subtitle[1:10], csv_file, None)
            elif english_sub_path:
                process_subtitle(is_movie, subtitle[1:10], csv_file, english_sub_path)
            else:
                print("No English subtitle found. Processing with subsync...")
                process_subtitle(is_movie, subtitle[1:10], csv_file, None)
        else:
            process_subtitle(is_movie, subtitle[1:10], csv_file, None)

        time.sleep(0.1)

def process_subtitle(is_movie, subtitle, csv_file, english_sub_path):
    subtitle = [None] + subtitle
    _, reference_file, sub_file, sub_code2, sub_code3, ep_code3, sub_id, provider, series_id, episode_id = subtitle
    
    if sub_code2 != 'en':
        print(f"Processing non-English subtitle: {sub_file}") 
    else:
        print(f"Processing subtitle: {sub_file}")
    time.sleep(0.1)
    
    if not os.path.isfile(sub_file):
        print("Subtitle not found in path, removing from list!\n")
        remove_from_list(csv_file, sub_id)
        time.sleep(1)
    else:
        lang_command = f"/usr/bin/python3 -u /opt/srt-lang-detect/srtlangdetect.py \"{sub_file}\""
        if srt_lang_detect(lang_command, sub_file):
            if SUBCLEANER:
                print("Running subcleaner...")
                subcleaner_command = f"/usr/bin/python3 -u /opt/subcleaner/subcleaner.py --language \"{sub_code2}\" \"{sub_file}\""
                output, fail = run_command(subcleaner_command, sub_file)
                log_output(sub_file, subcleaner_command, output, False)
            
            if not english_sub_path:
                print("Running subsync...")
    
                subsync_command = f"/usr/bin/python3 -u /usr/local/bin/subsync --cli --window-size \"{int(WINDOW_SIZE)}\" --min-points-no \"50\" --max-point-dist \"1\" --effort \"1\" sync --sub \"{sub_file}\" --sub-lang \"{sub_code3}\" --ref \"{reference_file}\" --ref-stream-by-type \"audio\" --out \"/dev/shm/tmp.srt\" --overwrite"
                log_command = f"/usr/bin/python3 -u /usr/local/bin/subsync --cli --window-size \"{int(WINDOW_SIZE)}\" --min-points-no \"50\" --max-point-dist \"1\" --effort \"1\" sync --sub \"{sub_file}\" --sub-lang \"{sub_code3}\" --ref \"{reference_file}\" --ref-stream-by-type \"audio\" --out \"{sub_file}\" --overwrite"
                output, fail = run_command(subsync_command, sub_file)
            
                if fail == True:
                    print(f"Audio track language unknown, trying again with \"{ep_code3}\" as reference language...")
                    time.sleep(0.1)
                        
                    subsync_command = f"/usr/bin/python3 -u /usr/local/bin/subsync --cli --window-size \"{int(WINDOW_SIZE)}\" --min-points-no \"50\" --max-point-dist \"1\" --effort \"1\" sync --sub \"{sub_file}\" --sub-lang \"{sub_code3}\" --ref \"{reference_file}\" --ref-stream-by-type \"audio\" --ref-lang \"{ep_code3}\" --out \"/dev/shm/tmp.srt\" --overwrite"
                    log_command = f"/usr/bin/python3 -u /usr/local/bin/subsync --cli --window-size \"{int(WINDOW_SIZE)}\" --min-points-no \"50\" --max-point-dist \"1\" --effort \"1\" sync --sub \"{sub_file}\" --sub-lang \"{sub_code3}\" --ref \"{reference_file}\" --ref-stream-by-type \"audio\" --ref-lang \"{ep_code3}\" --out \"{sub_file}\" --overwrite"
                    output, fail = run_command(subsync_command, sub_file)    
                if fail == 'extension':
                    print("ERROR: Can't open multimedia file: No such file or directory, moving to failed.txt...")
                
                    add_to_failed_list(sub_file)
                    remove_from_list(csv_file, sub_id)
                    find_non_english_counterpart(csv_file, subtitle[1:10], True)
                    print("Moved successfully, proceeding!!!\n")
                    
                    return False        
            else:
                print("Running subsync for non-English subtitle...")
                
                subsync_command = f"/usr/bin/python3 -u /usr/local/bin/subsync --cli --window-size \"300\" --min-points-no \"200\" --max-point-dist \"1\" --effort \"1\" sync --sub \"{sub_file}\" --sub-lang \"{sub_code3}\" --ref \"{english_sub_path}\" --ref-stream-by-type \"sub\" --ref-lang \"eng\" --out \"/dev/shm/tmp.srt\" --overwrite"
                log_command = f"/usr/bin/python3 -u /usr/local/bin/subsync --cli --window-size \"300\" --min-points-no \"200\" --max-point-dist \"1\" --effort \"1\" sync --sub \"{sub_file}\" --sub-lang \"{sub_code3}\" --ref \"{english_sub_path}\" --ref-stream-by-type \"sub\" --ref-lang \"eng\" --out \"{sub_file}\" --overwrite"
                output, fail = run_command(subsync_command, sub_file)
                
            if has_error(output, sub_file) is not None:    
                if has_error(output, sub_file) == True:
                    print("ERROR: Couldn't synchronize...")
                    log_output(sub_file, log_command, output, "couldn't synchronize!")
                    blacklist_result = blacklist_subtitle(is_movie, series_id, episode_id, provider, sub_id, sub_code2, sub_file)
                    if blacklist_result == True:
                        print("Successfully blacklisted subtitle, requesting new subtitle!\n")
                        remove_from_list(csv_file, sub_id)
                        find_non_english_counterpart(csv_file, subtitle[1:10], False)      
                    elif blacklist_result == 'remove':
                        print("Subtitle not found, removing from list...\n")
                        remove_from_list(csv_file, sub_id)
                    else:
                        print("ERROR: Failed to blacklist subtitle...")
                        add_to_retry_list(retry_file, reference_file, sub_file, sub_code2, sub_code3, ep_code3, sub_id, provider, series_id, episode_id)
                        remove_from_list(csv_file, sub_id)
                        
                        print("Moving subtitle entry to logs/retry.csv!")
                        
                        if sub_code2 == 'en':
                            find_non_english_counterpart(csv_file, subtitle[1:10], 'retry')
                        print()
                            
                elif has_error(output, sub_file)[0] == 'nosync' or has_error(output, sub_file) == 'nosync':
                    print("Couldn't synchronize to media file...")
                    
                    if has_error(output, sub_file)[1] == 'missmodel':
                        log_output(sub_file, log_command, output, "recognition model is missing")
                    else:
                        log_output(sub_file, log_command, output, "progress 100%, 0 points")
                    
                    add_to_failed_list(sub_file)
                    remove_from_list(csv_file, sub_id)
                    
                    if sub_code2 == 'en':
                        print("Removed English subtitle from list and added it to failed.txt!")
                    else:
                        print(f"Removed \"{sub_code2}\"-subtitle from list and added it to failed.txt!")
                    
                    find_non_english_counterpart(csv_file, subtitle[1:10], True)
                    print()
            else:
                try:
                    log_output(sub_file, log_command, output, False)
                    
                    shutil.copy2('/dev/shm/tmp.srt', sub_file)
                    if sub_code2 == 'en':
                        print("Successfully synced English subtitle, removing from list!")
                    else:
                        print(f"Successfully synced \"{sub_code2}\"-subtitle, removing from list!")
                        
                    remove_from_list(csv_file, sub_id)
                    
                    if sub_code2 == 'en':
                        find_non_english_counterpart(csv_file, subtitle[1:10], 'doprocess')
                    print()
                        
                except Exception as e:
                    print(f"\u2022ERROR: {str(e)}")
                    if sub_code2 == 'en':
                        remove_from_list(csv_file, sub_id)
                        add_to_csv_list(csv_file, *subtitle[1:10])
                    else:
                        find_non_english_counterpart(csv_file, subtitle[1:10], False)                 
        else:
            print("ERROR: Wrong language detected in subtitle...")
            blacklist_result = blacklist_subtitle(is_movie, series_id, episode_id, provider, sub_id, sub_code2, sub_file)
            if blacklist_result == True:
                print("Successfully blacklisted subtitle, requesting new subtitle!\n")
                remove_from_list(csv_file, sub_id)
                find_non_english_counterpart(csv_file, subtitle[1:10], False)
            elif blacklist_result == 'remove':
                print("Subtitle not found, removing from list...\n")
                remove_from_list(csv_file, sub_id)
            else:
                print("ERROR: Failed to blacklist subtitle...")
                add_to_retry_list(retry_file, reference_file, sub_file, sub_code2, sub_code3, ep_code3, sub_id, provider, series_id, episode_id)
                remove_from_list(csv_file, sub_id)
                
                print("Moving subtitle entry to logs/retry.csv!")
                
                if sub_code2 == 'en':
                    find_non_english_counterpart(csv_file, subtitle[1:10], 'retry')
                print()
                
if __name__ == "__main__":
    csv_file = '/subsync-bazarr/unsynced.csv'
    retry_file = '/subsync-bazarr/logs/retry.csv'
    failed_file = '/subsync-bazarr/failed.txt'
    
    if not os.path.isfile(csv_file):
        create_csv_file(csv_file)
        
    if not os.path.isfile(retry_file):
        create_retry_file(retry_file)
        
    while True:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{timestamp}: Checking for subtitles...")
        time.sleep(0.1)
        
        process_subtitles(csv_file, retry_file)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{timestamp}: List is clear, checking again in {SLEEP} seconds!\n")
        time.sleep(int(SLEEP))