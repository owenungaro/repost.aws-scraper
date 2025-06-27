import os
import shutil
import time

def filter_accepted_pages(saved_dir='saved_pages', filtered_dir='filtered_pages'):
    os.makedirs(filtered_dir, exist_ok=True)
    count = 0
    for folder in os.listdir(saved_dir):
        folder_path = os.path.join(saved_dir, folder)
        filter_path = os.path.join(folder_path, 'accepted_answer.json')

        if os.path.isdir(folder_path) and os.path.exists(filter_path):
            destination = os.path.join(filtered_dir, folder)
            shutil.copytree(folder_path, destination, dirs_exist_ok=True)
            print(f"[+] Copied: {folder}")
            count+=1
    return count

if __name__ == "__main__":
    start_time = time.time()
    count = filter_accepted_pages()
    end_time = time.time()
    print(f"Copied {count} folders in {end_time - start_time:.2f} seconds.")
